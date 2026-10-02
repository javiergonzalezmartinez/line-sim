"""Batch-flow simulation of a whole (fictitious) oral-solid-dose plant, warehouse receipt to dispatch.

Generic public process knowledge only. Time is in hours from Monday 00:00.
Each batch visits the stages in order. A stage has N parallel resources. A resource can have a
working calendar (days/hours), changeover+cleaning time when the product changes, a chance of a
breakdown per batch, and a QC-style retest chance. There are NO finite buffers between stages
(batches wait in unlimited queues unless a stage declares `buffer`, which switches to the event-driven engine with blocking) and no shift handovers or material shortages.
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
    pm_every_h: Optional[float] = None   # preventive maintenance after this many run-hours (event-driven engine only)
    pm_hours: float = 0.0           # duration of one preventive maintenance (h)
    wear_per_100h: float = 0.0      # relative rise of breakdown_p per 100 run-hours since the last preventive maintenance (0 = constant, as before)
    window: Optional[tuple] = None  # (open_hour, close_hour) on working days, None = 24/7
    workdays: int = 7               # 5 = Monday-Friday only
    retest_p: float = 0.0           # probability that the step has to be repeated (e.g. OOS investigation)
    waves: Optional[List[float]] = None  # for kind "wave": hours of the day when a dispatch leaves
    loc: Optional[str] = None       # location id on the layout where the batch sits during this stage
    pool: Optional[str] = None      # shared resource pool (e.g. forklifts); stages with the same pool share servers
    p: float = 1.0                  # kind "hold": probability that a lot is held (e.g. a deviation investigation)
    reject_p: float = 0.0           # kind "hold": probability that a held lot is rejected (leaves the plant)
    buffer: Optional[int] = None    # max lots waiting in front of a process/move stage (None = unlimited). With a limit, a finished lot stays in its resource (blocked) until there is room
    capacity: Optional[int] = None  # kind "wait": max lots resting at once (e.g. quarantine rack positions). None = unlimited. A wait with a capacity is modelled as a process stage with that many resources (no changeover, no breakdowns)
    breaks: Optional[list] = None   # daily gaps [[from_hour, to_hour], ...] (lunch, shift handover): no NEW lot starts inside a gap; a lot already running is not interrupted
    shortage_p: float = 0.0         # process stages: chance that the material for a lot is not there when its turn comes (the resource then waits, idle, not counted as working)
    shortage_hours: float = 0.0     # mean wait for the missing material (h)
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
    dispatch: str = "fifo"            # queue rule of the event-driven engine: "fifo" or "same_product_first" (avoid changeovers)
    hours_factor: object = None       # {product: factor} multiplies the process time of process stages in the event-driven engine (placeholder values; lets SPT and CR differ from FIFO/EDD)
    sync_streams: bool = False        # one random stream per (lot, stage, purpose) so scenarios share draws (event-driven engine only)
    conwip: Optional[int] = None      # release control: at most this many lots in the plant at once; a new lot is admitted when one finishes (event-driven engine only)
    due_h: object = None              # due date = release + due_h (hours); a number for all products or {product: hours}. Placeholder values only
    dispatch_max_wait_h: Optional[float] = None   # same_product_first: a lot that has waited longer than this goes first (guard against starvation)

    def __post_init__(self):
        if not self.stages or not self.products:
            raise ValueError("need stages and products")
        if self.dispatch not in ("fifo", "same_product_first", "edd", "spt", "cr"):
            raise ValueError("dispatch must be fifo, same_product_first, edd, spt or cr")
        if self.dispatch in ("edd", "cr") and self.due_h is None:
            raise ValueError("dispatch edd and cr need due_h")
        if self.conwip is not None and self.conwip < 1:
            raise ValueError("conwip must be >= 1")
        if self.hours_factor is not None and (any(p not in self.hours_factor for p in self.products) or any(v <= 0 for v in self.hours_factor.values())):
            raise ValueError("hours_factor must be > 0 and cover every product")
        if self.due_h is not None:
            dv = self.due_h.values() if isinstance(self.due_h, dict) else [self.due_h]
            if any(v <= 0 for v in dv) or (isinstance(self.due_h, dict) and any(p not in self.due_h for p in self.products)):
                raise ValueError("due_h must be > 0 (and cover every product when a dict)")
        if self.dispatch_max_wait_h is not None and self.dispatch_max_wait_h <= 0:
            raise ValueError("dispatch_max_wait_h must be > 0")
        if self.release_every <= 0:
            raise ValueError("release_every must be > 0")
        for s in self.stages:
            if s.capacity is not None:
                if s.kind != "wait" or s.capacity < 1:
                    raise ValueError(f"{s.name}: capacity must be >= 1 and only applies to wait stages")
                s.kind, s.servers = "process", s.capacity
            if not 0 <= s.shortage_p <= 1 or s.shortage_hours < 0 or (s.shortage_p > 0 and s.kind != "process"):
                raise ValueError(f"{s.name}: shortage_p must be 0..1, shortage_hours >= 0, and only applies to process stages")
            if s.servers < 1:
                raise ValueError(f"{s.name}: servers must be >= 1")
            if s.buffer is not None and (s.buffer < 0 or s.kind not in ("process", "move")):
                raise ValueError(f"{s.name}: buffer must be >= 0 and only applies to process/move stages")
            for a, b in (s.breaks or []):
                if not 0 <= a < b <= 24:
                    raise ValueError(f"{s.name}: each break must satisfy 0 <= from < to <= 24")
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

    def factor(self, product) -> float:
        return 1.0 if self.hours_factor is None else self.hours_factor[product]

    def remaining_work(self, k, product) -> float:
        """Nominal process hours still to do from stage k on (process stages only; no queues, changeovers, moves or waits)."""
        return sum(s.hours for s in self.stages[k:] if s.kind == "process") * self.factor(product)

    def due_date(self, b) -> float:
        d = self.due_h[b.product] if isinstance(self.due_h, dict) else self.due_h
        return b.released + d

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
    entered: Optional[float] = None   # time the lot entered the plant (differs from `released` only with conwip)
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
    pm: float = 0.0
    wait: float = 0.0
    batches: int = 0
    max_queue_wait: float = 0.0
    blocked: float = 0.0           # resource-hours spent holding a finished lot because the next stage's buffer was full
    short_lots: int = 0            # lots that had to wait for material (inside the window)
    short_hours: float = 0.0       # resource-hours spent waiting for material (inside the window)
    max_queue: int = 0             # largest number of lots waiting in front of the stage (event-driven engine only)


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
    """Earliest time >= t at which the stage may start a batch (calendar window, then daily break gaps)."""
    for _ in range(50):
        t = _next_window(t, s)
        moved = False
        for a, b in (s.breaks or []):
            h = t - int(t // 24) * 24
            if a <= h < b:
                t += b - h
                moved = True
        if not moved:
            return t
    return t


def _next_window(t: float, s: Stage) -> float:
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
    if plant.dispatch in ("edd", "spt", "cr") or plant.hours_factor is not None or plant.conwip is not None or plant.sync_streams or any(s.buffer is not None or s.pm_every_h for s in plant.stages):
        return simulate_des(plant)
    return simulate_fifo(plant)


def simulate_fifo(plant: Plant) -> Result:
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
            if s.shortage_p and rng.random() < s.shortage_p:
                m = _gamma(rng, s.shortage_hours, 0.5)
                if w0 <= cur < w1:
                    st.short_lots += 1
                    st.short_hours += m
                cur += m
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


def simulate_des(plant: Plant) -> Result:
    """Event-driven engine with finite buffers and blocking-after-service.

    `buffer` on a process/move stage = how many lots may wait in front of it (lots in service do not count).
    When the next stage is full, a finished lot stays in its resource (the resource is blocked) until a slot opens;
    blocked lots are released first-come first-served. Delay-only stages (wait without `capacity`, wave, hold) have no capacity.
    Same stage semantics as simulate_fifo (calendars, changeovers, breakdowns, retests, holds, shared pools)."""
    rng = random.Random(plant.seed)
    streams: Dict[tuple, random.Random] = {}

    def rs(i, k, tag):
        """Random stream for one purpose. With `sync_streams` each (lot, stage, purpose) has its own stream derived from the seed, so two scenarios
        that differ in something else still draw the same numbers for the same lot, stage and purpose (common random numbers)."""
        if not plant.sync_streams:
            return rng
        key = (i, k, tag)
        r = streams.get(key)
        if r is None:
            r = streams[key] = random.Random(f"{plant.seed}|{i}|{k}|{tag}")
        return r

    S, n = plant.stages, len(plant.stages)
    keys = [s.pool or str(k) for k, s in enumerate(S)]
    units: Dict[str, list] = {}
    for k, key in enumerate(keys):
        if S[k].kind in ("process", "move") and key not in units:
            units[key] = [{"state": "idle", "last": None, "batch": None, "free_at": 0.0, "k": None} for _ in range(S[k].servers)]
    stats = [StageStat(s.name, s.servers) for s in S]
    w0, w1 = plant.warmup, plant.horizon
    batches: List[Batch] = []
    queue = [[] for _ in S]            # (enqueue time, batch id)
    blocked = [[] for _ in S]          # lots waiting to enter stage k: (since, batch id, unit or None, from stage or -1)
    heap: list = []
    seq = [0]
    cur_trace: Dict[int, list] = {}    # batch id -> open trace record [k, arrive, start, end, leave]

    def push(t, kind, *a):
        seq[0] += 1
        heapq.heappush(heap, (t, seq[0], kind, a))

    def credit(kind, k, a, b):
        a, b = max(a, w0), min(b, w1)
        if b > a:
            setattr(stats[k], kind, getattr(stats[k], kind) + (b - a))

    t, bid = 0.0, 0
    while t < plant.horizon:
        batches.append(Batch(bid, plant.products[bid % len(plant.products)], t))
        push(t, "release", bid)
        bid += 1
        t += plant.release_every

    def has_room(k, now):
        s = S[k]
        if s.buffer is None or s.kind not in ("process", "move"):
            return True
        if len(queue[k]) < s.buffer:
            return True
        return not queue[k] and any(u["state"] == "idle" for u in units[keys[k]]) and _next_open(now, s) <= now

    def enter(i, k, now):
        """Lot i arrives at stage k at `now` (room already checked)."""
        b, s = batches[i], S[k]
        rec = [k, now, now, now, now]
        b.trace.append(rec)
        cur_trace[i] = rec
        if s.kind in ("process", "move"):
            queue[k].append((now, i))
            stats[k].max_queue = max(stats[k].max_queue, len(queue[k]))
            dispatch(keys[k], now)
            return
        if s.kind == "hold":
            if rs(i, k, "hold_p").random() >= s.p:
                rec[2] = rec[3] = now
                push(now, "leave", i, k, None)
                return
            start = _next_open(now, s)
            end = start + _gamma(rs(i, k, "hold_h"), s.hours, s.cv)
            if rs(i, k, "reject").random() < s.reject_p:
                b.rejected = True
            b.waits[s.name] = start - now
            rec[2], rec[3] = start, end
            if w0 <= now < w1:
                stats[k].wait += start - now
                stats[k].batches += 1
                stats[k].max_queue_wait = max(stats[k].max_queue_wait, start - now)
                credit("busy", k, start, end)
            push(end, "leave", i, k, None)
            return
        if s.kind == "wave":
            end = _next_wave(now, s.waves)
            b.waits[s.name] = end - now
            rec[3] = end
        else:
            end = now + _gamma(rs(i, k, "delay"), s.hours, s.cv)
            b.waits[s.name] = 0.0
            rec[3] = end
        if w0 <= now < w1:
            stats[k].wait += end - now if s.kind == "wave" else 0.0
            stats[k].batches += 1
        push(end, "leave", i, k, None)

    def dispatch(key, now):
        us = units[key]
        ks = [k for k in range(n) if keys[k] == key and S[k].kind in ("process", "move")]
        while True:
            idle = [u for u in us if u["state"] == "idle"]
            if not idle:
                return
            cand, retry = [], None
            for k in ks:
                if queue[k]:
                    op = _next_open(now, S[k])
                    if op <= now:
                        cand.append((queue[k][0][0], k))
                    else:
                        retry = op if retry is None else min(retry, op)
            if not cand:
                if retry is not None:
                    push(retry, "open", key)
                return
            _, k = min(cand)
            u = min(idle, key=lambda x: x["free_at"])        # the resource idle the longest (same choice as the FIFO engine)
            pos = 0
            old = queue[k][0][0]
            if plant.dispatch == "same_product_first" and u["last"] is not None and S[k].changeover > 0 \
                    and not (plant.dispatch_max_wait_h is not None and now - old > plant.dispatch_max_wait_h):
                for j, (_t, bi) in enumerate(queue[k]):      # oldest waiting lot of the product this unit last made
                    if batches[bi].product == u["last"]:
                        pos = j
                        break
            if plant.dispatch == "edd":                    # earliest due date first (Suri, UCSB notes: EDD minimises maximum lateness on one machine)
                pos = min(range(len(queue[k])), key=lambda j: (plant.due_date(batches[queue[k][j][1]]), queue[k][j][0]))
            elif plant.dispatch == "spt":                  # shortest processing time at this stage first
                pos = min(range(len(queue[k])), key=lambda j: (S[k].hours * plant.factor(batches[queue[k][j][1]].product), queue[k][j][0]))
            elif plant.dispatch == "cr":                   # smallest critical ratio first: (due - now) / remaining nominal work
                pos = min(range(len(queue[k])), key=lambda j: ((plant.due_date(batches[queue[k][j][1]]) - now) / max(plant.remaining_work(k, batches[queue[k][j][1]].product), 1e-9), queue[k][j][0]))
            _, i = queue[k].pop(pos)
            b, s = batches[i], S[k]
            rec = cur_trace[i]
            start = now
            wait = start - rec[1]
            cur = start
            if s.pm_every_h and u.get("since_pm", 0.0) >= s.pm_every_h:
                credit("pm", k, cur, cur + s.pm_hours)       # preventive maintenance before the next lot
                cur += s.pm_hours
                u["since_pm"] = 0.0
            if u["last"] is not None and u["last"] != b.product and s.changeover > 0:
                credit("setup", k, cur, cur + s.changeover)
                cur += s.changeover
            u["last"] = b.product
            if s.shortage_p and rs(i, k, "shortage").random() < s.shortage_p:
                m = _gamma(rs(i, k, "shortage_h"), s.shortage_hours, 0.5)
                if w0 <= cur < w1:
                    stats[k].short_lots += 1
                    stats[k].short_hours += m
                cur += m
            rec[2] = cur
            dur = _gamma(rs(i, k, "dur"), s.hours * plant.factor(b.product), s.cv)
            while True:
                credit("busy", k, cur, cur + dur)
                cur += dur
                u["since_pm"] = u.get("since_pm", 0.0) + dur
                if s.breakdown_p and rs(i, k, "breakdown").random() < min(1.0, s.breakdown_p * (1.0 + s.wear_per_100h * u["since_pm"] / 100.0)):
                    r = _gamma(rs(i, k, "repair"), s.repair, 0.5)
                    credit("repair", k, cur, cur + r)
                    cur += r
                if s.retest_p and rs(i, k, "retest").random() < s.retest_p:
                    dur = _gamma(rs(i, k, "dur"), s.hours * plant.factor(b.product), s.cv)
                    continue
                break
            rec[3] = rec[4] = cur
            b.waits[s.name] = wait
            if w0 <= rec[1] < w1:
                stats[k].wait += wait
                stats[k].batches += 1
                stats[k].max_queue_wait = max(stats[k].max_queue_wait, wait)
            u["state"], u["batch"], u["k"] = "busy", i, k
            push(cur, "done", i, k, u)
            release_blocked(k, now)

    def release_blocked(k, now):
        """A slot in front of stage k may have opened: let waiting lots in, oldest first."""
        while blocked[k] and has_room(k, now):
            since, i, u, frm = blocked[k].pop(0)
            if u is not None:
                credit("blocked", frm, since, now)
                u["state"], u["batch"], u["free_at"] = "idle", None, now
            cur_trace[i][4] = now
            enter(i, k, now)
            if u is not None:
                dispatch(keys[frm], now)

    def advance(i, k, u, now):
        """Lot i has finished stage k (service or delay) at `now` and wants to go to k+1."""
        b = batches[i]
        if b.rejected or k + 1 >= n:
            b.done = now
            cur_trace[i][4] = now
            if u is not None:
                u["state"], u["batch"], u["free_at"] = "idle", None, now
                dispatch(keys[k], now)
            if plant.conwip is not None:                 # a card comes back: admit the oldest waiting lot
                inside[0] -= 1
                if card_wait:
                    inside[0] += 1
                    admit(card_wait.pop(0), now)
            return
        if has_room(k + 1, now) and not blocked[k + 1]:
            cur_trace[i][4] = now
            if u is not None:
                u["state"], u["batch"], u["free_at"] = "idle", None, now
            enter(i, k + 1, now)
            if u is not None:
                dispatch(keys[k], now)
        else:
            blocked[k + 1].append((now, i, u, k))
            if u is not None:
                u["state"] = "blocked"

    inside = [0]          # lots in the plant (conwip)
    card_wait: List[int] = []

    def admit(i, now):
        batches[i].entered = now
        if has_room(0, now) and not blocked[0]:
            enter(i, 0, now)
        else:
            cur_trace[i] = [0, now, now, now, now]
            blocked[0].append((now, i, None, -1))

    while heap:
        now, _, kind, a = heapq.heappop(heap)
        if kind == "release":
            i = a[0]
            if plant.conwip is not None and inside[0] >= plant.conwip:
                card_wait.append(i)                      # no card free: the order waits outside the plant
            else:
                inside[0] += 1
                admit(i, now)
        elif kind == "done":
            advance(a[0], a[1], a[2], now)
        elif kind == "leave":
            advance(a[0], a[1], a[2], now)
        elif kind == "open":
            dispatch(a[0], now)
        # a freed queue slot or unit may let blocked lots in
        for k in range(n):
            if blocked[k]:
                release_blocked(k, now)
    return Result(batches, stats, w1 - w0, w1)
