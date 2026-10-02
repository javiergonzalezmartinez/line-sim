"""Discrete-event simulation of a serial production line with finite buffers.

Pure standard library. Station i takes a part from buffer i-1 (station 0 always has material),
processes it, and puts it into buffer i. If buffer i is full the station keeps the part and is
BLOCKED until space appears. If buffer i-1 is empty the station is STARVED.
Failures are operation-dependent: a station can only break while it is processing.
"""
from __future__ import annotations

import heapq
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

IDLE, BUSY, BLOCKED = "idle", "busy", "blocked"


@dataclass
class Station:
    name: str
    cycle_time: float                 # seconds per part (mean)
    cv: float = 0.0                   # coefficient of variation of the cycle time (0 = deterministic)
    mtbf: Optional[float] = None      # mean operating time between failures (s); None = never fails
    mttr: float = 0.0                 # mean time to repair (s)


@dataclass
class Config:
    stations: List[Station]
    buffers: List[int]                # capacity between station i and i+1 (len = stations - 1); 0 = direct hand-off
    duration: float = 8 * 3600.0
    warmup: float = 3600.0
    seed: int = 1

    def __post_init__(self) -> None:
        if len(self.buffers) != len(self.stations) - 1:
            raise ValueError("buffers must have one entry between each pair of stations")
        if any(b < 0 for b in self.buffers):
            raise ValueError("buffer capacities must be >= 0 (0 = direct hand-off, the finished part waits in the station)")
        if self.warmup >= self.duration:
            raise ValueError("warmup must be shorter than duration")


@dataclass
class StationStats:
    name: str
    busy: float = 0.0
    down: float = 0.0
    blocked: float = 0.0
    starved: float = 0.0
    parts: int = 0

    def shares(self, window: float) -> Dict[str, float]:
        return {k: getattr(self, k) / window for k in ("busy", "down", "blocked", "starved")}


@dataclass
class Result:
    window: float
    throughput: float                 # parts per hour, measured after warmup
    parts: int
    stations: List[StationStats]
    mean_wip: List[float] = field(default_factory=list)   # mean level of each buffer

    @property
    def bottleneck(self) -> str:
        """Station with the highest share of time actually working or repairing."""
        return max(self.stations, key=lambda s: s.busy + s.down).name


def _gamma(rng: random.Random, mean: float, cv: float) -> float:
    if mean <= 0:
        return 0.0
    if cv <= 0:
        return mean
    k = 1.0 / (cv * cv)
    return rng.gammavariate(k, mean / k)


def simulate(cfg: Config) -> Result:
    rng = random.Random(cfg.seed)
    n = len(cfg.stations)
    state = [IDLE] * n
    since = [0.0] * n                 # time the current state began
    buf = [0] * (n - 1)
    ttf = [None if s.mtbf is None else rng.expovariate(1.0 / s.mtbf) for s in cfg.stations]
    stats = [StationStats(s.name) for s in cfg.stations]
    wip_area = [0.0] * (n - 1)
    last_t = 0.0
    parts_out = 0
    heap: list = []
    seq = 0
    warm = cfg.warmup
    t = 0.0

    def credit(i: int, kind: str, a: float, b: float) -> None:
        a, b = max(a, warm), min(b, cfg.duration)
        if b > a:
            setattr(stats[i], kind, getattr(stats[i], kind) + (b - a))

    def set_state(i: int, new: str, now: float) -> None:
        if state[i] == IDLE:
            # idle with nothing to do: starved (station 0 is never idle for lack of parts)
            credit(i, "starved", since[i], now)
        elif state[i] == BLOCKED:
            credit(i, "blocked", since[i], now)
        state[i] = new
        since[i] = now

    def start(i: int, now: float) -> None:
        nonlocal seq
        st = cfg.stations[i]
        work = _gamma(rng, st.cycle_time, st.cv)
        down = 0.0
        if st.mtbf is not None:
            left = work
            while ttf[i] < left:                       # breaks down during this part
                left -= ttf[i]
                down += rng.expovariate(1.0 / st.mttr) if st.mttr > 0 else 0.0
                ttf[i] = rng.expovariate(1.0 / st.mtbf)
            ttf[i] -= left
        set_state(i, BUSY, now)
        credit(i, "busy", now, now + work)
        credit(i, "down", now + work, now + work + down)   # repair time is booked after the work
        seq += 1
        heapq.heappush(heap, (now + work + down, seq, i))

    def settle(now: float) -> None:
        changed = True
        while changed:
            changed = False
            for i in range(n - 1, -1, -1):             # downstream first so space frees upstream
                if state[i] == BLOCKED and i < n - 1 and cfg.buffers[i] == 0:
                    if state[i + 1] == IDLE:           # no buffer: hand the part straight to a waiting station
                        set_state(i, IDLE, now)
                        start(i + 1, now)
                        changed = True
                elif state[i] == BLOCKED:
                    if i == n - 1 or buf[i] < cfg.buffers[i]:
                        if i < n - 1:
                            buf[i] += 1
                        set_state(i, IDLE, now)
                        changed = True
                if state[i] == IDLE:
                    if i == 0 or buf[i - 1] > 0:
                        if i > 0:
                            buf[i - 1] -= 1
                        start(i, now)
                        changed = True

    settle(0.0)
    while heap:
        t, _, i = heapq.heappop(heap)
        if t > cfg.duration:
            t = cfg.duration
            break
        for j in range(n - 1):                          # integrate buffer levels over the window
            wip_area[j] += buf[j] * max(0.0, t - max(last_t, warm))
        last_t = t
        stats[i].parts += 1 if t >= warm else 0
        if i == n - 1:
            parts_out += 1 if t >= warm else 0
            set_state(i, IDLE, t)
        else:
            set_state(i, BLOCKED, t)                   # holds the part until settle() places it
        settle(t)
    else:
        t = cfg.duration
    # close open intervals at the end of the run
    for i in range(n):
        if state[i] == IDLE:
            credit(i, "starved", since[i], cfg.duration)
        elif state[i] == BLOCKED:
            credit(i, "blocked", since[i], cfg.duration)
    for j in range(n - 1):
        wip_area[j] += buf[j] * max(0.0, cfg.duration - max(last_t, warm))
    window = cfg.duration - warm
    return Result(window=window, throughput=parts_out / window * 3600.0, parts=parts_out,
                  stations=stats, mean_wip=[a / window for a in wip_area])


def sweep_buffer(cfg: Config, sizes: List[int], seeds: int = 5) -> List[dict]:
    """Throughput (parts/h, mean over seeds) when every buffer has the same capacity."""
    out = []
    for size in sizes:
        vals = []
        for s in range(seeds):
            c = Config(cfg.stations, [size] * len(cfg.buffers), cfg.duration, cfg.warmup, cfg.seed + s)
            vals.append(simulate(c).throughput)
        out.append({"buffer": size, "throughput": sum(vals) / len(vals), "min": min(vals), "max": max(vals)})
    return out
