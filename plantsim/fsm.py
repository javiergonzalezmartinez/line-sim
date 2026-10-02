"""State machines from the spec tables (spec/state_machines.json).

A transition is allowed only if the table has a row (machine, from-state, event). Anything else raises
IllegalTransition and is not applied. The tables are generic (OPC UA / ISA-95 / ISA-88 style); guards
written in the spec are descriptive text and are NOT evaluated here.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(HERE, "..", "spec", "state_machines.json")


class IllegalTransition(Exception):
    pass


class Spec:
    def __init__(self, path: str = SPEC):
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)["records"]
        self.table: Dict[Tuple[str, str, str], str] = {}
        self.states: Dict[str, set] = {}
        for r in rows:
            self.table[(r["Máquina"], r["Origen"], r["Evento"])] = r["Destino"]
            self.states.setdefault(r["Máquina"], set()).update([r["Origen"], r["Destino"]])

    def machines(self) -> List[str]:
        return sorted(self.states)


_SPEC: Optional[Spec] = None


def spec() -> Spec:
    global _SPEC
    if _SPEC is None:
        _SPEC = Spec()
    return _SPEC


def state_hash(machine: str, state: str) -> str:
    return hashlib.sha256(f"{machine}:{state}".encode()).hexdigest()


class Machine:
    def __init__(self, name: str, initial: str, owner: str = "", sp: Optional[Spec] = None):
        self.sp = sp or spec()
        if initial not in self.sp.states.get(name, ()):
            raise ValueError(f"{name}: unknown state {initial}")
        self.name, self.state, self.owner = name, initial, owner
        self.history: List[tuple] = []     # (event, before, after)
        self.rejected: List[tuple] = []    # (event, state at the time)

    def fire(self, event: str) -> Tuple[str, str]:
        """Apply an event. Returns (before, after). Raises IllegalTransition (state unchanged, attempt logged)."""
        nxt = self.sp.table.get((self.name, self.state, event))
        if nxt is None:
            self.rejected.append((event, self.state))
            raise IllegalTransition(f"{self.name}{' ' + self.owner if self.owner else ''}: event {event!r} not allowed in state {self.state}")
        before, self.state = self.state, nxt
        self.history.append((event, before, nxt))
        return before, nxt
