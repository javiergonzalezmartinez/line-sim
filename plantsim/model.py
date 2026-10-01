"""Batch-flow simulation of a whole (fictitious) oral-solid-dose plant, warehouse receipt to dispatch.

Generic public process knowledge only. Time is in hours from Monday 00:00.
Each batch visits the stages in order. A stage has N parallel resources. A resource can have a
working calendar (days/hours), changeover+cleaning time when the product changes, a chance of a
breakdown per batch, and a QC-style retest chance. There are NO finite buffers between stages
(batches wait in unlimited queues) and no shift handovers or material shortages.
"""
from __future__ import annotations

import heapq
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Stage:
    name: str
    kind: str                       # "process" | "move" | "wait" | "wave" | "hold"
    servers: int = 1
    hours: float = 0.0              # mean process time per batch (process/wait)
    cv: float = 0.1                 # variability of the process time (lognormal-ish via gamma)
    changeover: float = 0.0         # cleaning + changeover when product differs from the last one
    breakdown_p: float = 0.0        # probability of a breakdown during a batch
    repair: float = 0.0             # mean repair time (h)
    window: Optional[tuple] = None  # (open_hour, close_hour) on working days, None = 24/7
    workdays: int = 7               # 5 = Monday-Friday only
    retest_p: float = 0.0           # probability that the step has to be repeated (e.g. OOS investigation)
    waves: Optional[List[float]] = None  # for kind "wave": hours of the day when a dispatch leaves
    loc: Optional[str] = None       # location id on the layout where the batch sits during this stage
    pool: Optional[str] = None      # shared resource pool (e.g. forklifts); stages with the same pool share servers
    p: float = 1.0                  # kind "hold": probability that a lot is held (e.g. a deviation investigation)
    reject_p: float = 0.0           # kind "hold": probability that a held lot is rejected (leaves the plant)
    events: Optional[list] = None   # signal/transaction templates for the event layer (used by the browser view)


@dataclass
class Plant:
    stages: List[Stage]
    products: List[str]
    release_every: float            # hours between batch releases to the floor
    horizon: float = 24 * 7 * 12    # simulated hours
    warmup: float = 24 * 7 * 2
    seed: int = 1
    layout: Optional[list] = None   # [{id, name, x, y, w, h}] floor plan for the animated view
    m_per_px: float = 0.0           # >0: transport time of move stages = Manhattan distance on the layout / speed + handling
    speed_kmh: float = 6.0
    handling_min: float = 6.0

    def __post_init__(self):
        if not self.stages or not self.products:
            raise ValueError("need stages and products")
        if self.release_every <= 0:
            raise ValueError("release_every must be > 0")
        for s in self.stages:
            if s.servers < 1:
                raise ValueError(f"{s.name}: servers must be >= 1")
            if s.kind not in ("process", "move", "wait", "wave", "hold"):
                raise ValueError(f"{s.name}: unknown kind {s.kind}")
            if s.kind == "wave" and not s.waves:
                raise ValueError(f"{s.name}: wave stage needs waves")
        pools = {}
        for s in self.stages:
            if s.pool:
                if pools.setdefault(s.pool, s.servers) != s.servers:
                    raise ValueError(f"pool {s.pool}: all stages of a pool must declare the same servers")
        if self.layout is not None:
            ids = {l["id"] for l in self.layout}
            for i, s in enumerate(self.stages):
                if s.kind == "move":
                    if i == 0 or i == len(self.stages) - 1:
                        raise ValueError(f"{s.name}: a move cannot be the first or last stage")
                elif s.kind != "move" and s.loc not in ids:
                    raise ValueError(f"{s.name}: loc {s.loc!r} is not in the layout")
        self.resolve_moves()

    def resolve_moves(self):
        if not (self.layout and self.m_per_px > 0):
            return
        pos = {l['id']: (l['x'] + l['w'] / 2, l['y'] + l['h'] / 2) for l in self.layout}
        for i, s in enumerate(self.stages):
            if s.kind == 'move':
                a, b = pos[self.stages[i - 1].loc], pos[self.stages[i + 1].loc]
                metres = (abs(a[0] - b[0]) + abs(a[1] - b[1])) * self.m_per_px
                s.hours = (metres / (self.speed_kmh * 1000 / 60) + self.handling_min) / 60.0


@dataclass
class Batch:
    id: int
    product: str
    released: float
    done: Optional[float] = None
    rejected: bool = False
    waits: Dict[str, float] = field(default_factory=dict)
    trace: list = field(default_factory=list)   # (stage index, arrive, start, end)


@dataclass
class StageStat:
    name: str
    servers: int
    busy: float = 0.0
    setup: float = 0.0
    repair: float = 0.0
    wait: float = 0.0
    batches: int = 0
    max_queue_wait: float = 0.0


@dataclass
class Result:
    batches: List[Batch]
    stats: List[StageStat]
    window: float
    horizon: float

    @property
    def rejected(self) -> int:
        return sum(1 for b in self.batches if b.rejected and self.horizon - self.window <= b.done <= self.horizon)

    @property
    def finished(self) -> List[Batch]:
        return [b for b in self.batches if b.done is not None and not b.rejected]

    @property
    def throughput_per_week(self) -> float:
        n = sum(1 for b in self.finished if self.horizon - self.window <= b.done <= self.horizon)
        return n / (self.window / 168.0)

    @property
    def lead_times(self) -> List[float]:
        return [b.done - b.released for b in self.finished if self.horizon - self.window <= b.done <= self.horizon]

    @property
    def mean_lead_time_days(self) -> float:
        lt = self.lead_times
        return sum(lt) / len(lt) / 24.0 if lt else 0.0

    def utilisation(self, st: StageStat) -> dict:
        cap = st.servers * self.window
        return {"process": st.busy / cap, "setup": st.setup / cap, "repair": st.repair / cap}

    def pool_utilisation(self, plant: "Plant") -> dict:
        """Busy share of each shared pool (e.g. forklifts) over the window."""
        out = {}
        for name in {s.pool for s in plant.stages if s.pool}:
            sts = [(s, st) for s, st in zip(plant.stages, self.stats) if s.pool == name]
            n = sts[0][0].servers
            out[name] = sum(st.busy + st.repair for _, st in sts) / (n * self.window)
        return out

    @property
    def bottleneck(self) -> str:
        best, name = -1.0, ""
        for st in self.stats:
            u = self.utilisation(st)
            tot = u["process"] + u["setup"] + u["repair"]
            if tot > best:
                best, name = tot, st.name
        return name


def _gamma(rng: random.Random, mean: float, cv: float) -> float:
    if mean <= 0:
        return 0.0
    if cv <= 0:
        return mean
    k = 1.0 / (cv * cv)
    return rng.gammavariate(k, mean / k)


def _next_open(t: float, s: Stage) -> float:
    """Earliest time >= t at which the stage may start a batch."""
    if s.window is None and s.workdays >= 7:
        return t
    o, c = s.window if s.window else (0.0, 24.0)
    for _ in range(14):
        day = int(t // 24)
        h = t - day * 24
        if (day % 7) < s.workdays:
            if h < o:
                return day * 24 + o
            if h < c:
                return t
        t = (day + 1) * 24
    return t


def _next_wave(t: float, waves: List[float]) -> float:
    day = int(t // 24)
    for d in range(day, day + 8):
        for w in sorted(waves):
            if d * 24 + w >= t:
                return d * 24 + w
    return t


def simulate(plant: Plant) -> Result:
    rng = random.Random(plant.seed)
    keys = [s.pool or k for k, s in enumerate(plant.stages)]
    free = {key: [0.0] * plant.stages[keys.index(key)].servers for key in keys}
    last = {key: [None] * plant.stages[keys.index(key)].servers for key in keys}
    stats = [StageStat(s.name, s.servers) for s in plant.stages]
    w0, w1 = plant.warmup, plant.horizon
    batches: List[Batch] = []
    heap: list = []
    t, bid = 0.0, 0
    while t < plant.horizon:
        b = Batch(bid, plant.products[bid % len(plant.products)], t)
        batches.append(b)
        heapq.heappush(heap, (t, bid, 0))
        bid += 1
        t += plant.release_every

    def credit(kind: str, st: StageStat, a: float, b: float):
        a, b = max(a, w0), min(b, w1)
        if b > a:
            setattr(st, kind, getattr(st, kind) + (b - a))

    while heap:
        at, i, k = heapq.heappop(heap)
        b = batches[i]
        s, st = plant.stages[k], stats[k]
        if s.kind == "hold":
            if rng.random() >= s.p:                      # no deviation: the lot passes straight through
                if k + 1 < len(plant.stages):
                    heapq.heappush(heap, (at, i, k + 1))
                else:
                    b.done = at
                continue
            start = _next_open(at, s)
            wait = start - at
            end = start + _gamma(rng, s.hours, s.cv)
            pstart = start
            if rng.random() < s.reject_p:
                b.rejected = True
            if True:
                b.waits[s.name] = wait
                b.trace.append((k, at, pstart, end))
                if w0 <= at < w1:
                    st.wait += wait
                    st.batches += 1
                    st.max_queue_wait = max(st.max_queue_wait, wait)
                    credit("busy", st, start, end)
            if b.rejected or k + 1 >= len(plant.stages):
                b.done = end
            else:
                heapq.heappush(heap, (end, i, k + 1))
            continue
        if s.kind == "wave":
            end = _next_wave(at, s.waves)
            wait = end - at
            pstart = at
        elif s.kind == "wait":
            end = at + _gamma(rng, s.hours, s.cv)
            wait = 0.0
            pstart = at
        else:
            key = keys[k]
            j = min(range(s.servers), key=lambda x: free[key][x])
            start = _next_open(max(at, free[key][j]), s)
            wait = start - at
            cur = start
            if last[key][j] is not None and last[key][j] != b.product and s.changeover > 0:
                credit("setup", st, cur, cur + s.changeover)
                cur += s.changeover
            last[key][j] = b.product
            pstart = cur
            dur = _gamma(rng, s.hours, s.cv)
            while True:
                credit("busy", st, cur, cur + dur)
                cur += dur
                if s.breakdown_p and rng.random() < s.breakdown_p:
                    r = _gamma(rng, s.repair, 0.5)
                    credit("repair", st, cur, cur + r)
                    cur += r
                if s.retest_p and rng.random() < s.retest_p:
                    dur = _gamma(rng, s.hours, s.cv)
                    continue
                break
            end = cur
            free[key][j] = end
        b.waits[s.name] = wait
        b.trace.append((k, at, pstart, end))
        if w0 <= at < w1:
            st.wait += wait
            st.batches += 1
            st.max_queue_wait = max(st.max_queue_wait, wait)
        if k + 1 < len(plant.stages):
            heapq.heappush(heap, (end, i, k + 1))
        else:
            b.done = end
    return Result(batches, stats, w1 - w0, w1)
