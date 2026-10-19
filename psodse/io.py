"""Readers for the two input files: the application DFG and the module library.

DFG file  : a flat comma separated list, 4 fields per operation
            <op>,<operand1>,<operand2>,<op number>     e.g.  *,0,0,1,+,1,2,5
            operand 0 means "primary input" (a fresh value read from outside),
            operand k > 0 means "the result of operation k".

Library   : one line per hardware resource, e.g.
            adder(16),0.739pj,18.8744um,66.2428ps,18.6um,70.0ps,1
            -> name, power, area (um^2), latency (ps), ..., max instances available
"""
import re
from dataclasses import dataclass, field

# Which library resource executes which DFG operator
OP_TO_FU = {"+": "adder", "-": "subtractor", "*": "multiplier"}
OP_SYMBOL = {"+": "+", "-": "−", "*": "×"}


@dataclass
class Operation:
    op_id: int
    op_type: str          # '+', '-' or '*'
    operand1: int         # 0 = primary input, else id of the producing operation
    operand2: int

    @property
    def fu_type(self):
        return OP_TO_FU[self.op_type]

    @property
    def predecessors(self):
        return sorted({o for o in (self.operand1, self.operand2) if o != 0})


@dataclass
class DFG:
    name: str
    ops: dict                                   # op_id -> Operation (insertion ordered)
    successors: dict = field(default_factory=dict)

    def __post_init__(self):
        self.successors = {i: [] for i in self.ops}
        for op in self.ops.values():
            for p in op.predecessors:
                self.successors[p].append(op.op_id)

    @property
    def fu_types_used(self):
        return sorted({op.fu_type for op in self.ops.values()})


@dataclass
class FUType:
    name: str
    area: float           # um^2
    latency: float        # ps
    max_count: int
    power: float = 0.0    # pJ


@dataclass
class Library:
    fus: dict             # name -> FUType (adder, subtractor, multiplier)
    register_area: float
    register_latency: float
    mux_area: float = 0.0
    mux_latency: float = 0.0


def read_dfg(path, name=None):
    with open(path) as f:
        text = f.read()
    if name is None:
        name = re.sub(r"(_bechmark|_benchmark)?\.txt$", "", path.split("/")[-1])
    return parse_dfg(text, name, source=path)


def parse_dfg(text, name="application", source="DFG"):
    path = source
    tokens = [t for t in re.split(r"[,\s]+", text) if t]
    if len(tokens) % 4:
        raise ValueError(f"{path}: expected groups of 4 fields, got {len(tokens)} tokens")
    ops = {}
    for i in range(0, len(tokens), 4):
        typ, a, b, oid = tokens[i], int(tokens[i + 1]), int(tokens[i + 2]), int(tokens[i + 3])
        if typ not in OP_TO_FU:
            raise ValueError(f"{path}: unknown operation '{typ}' (op {oid})")
        if oid in ops:
            raise ValueError(f"{path}: duplicate operation number {oid}")
        for operand in (a, b):
            if operand and operand not in ops:
                raise ValueError(f"{path}: op {oid} uses op {operand} before it is defined")
        ops[oid] = Operation(oid, typ, a, b)
    if not ops:
        raise ValueError(f"{path}: no operations found")
    return DFG(name, ops)


def _num(token, unit):
    return float(token[: -len(unit)])


def read_library(path):
    with open(path) as f:
        return parse_library(f.read(), source=path)


def parse_library(text, source="library"):
    path = source
    fus, reg, mux = {}, None, (0.0, 0.0)
    for line in text.splitlines():
        tokens = [t for t in re.split(r"[,\s]+", line.strip()) if t]
        if not tokens:
            continue
        m = re.match(r"[A-Za-z]+", tokens[0])
        if not m:
            raise ValueError(f"{path}: cannot read line '{line.strip()}'")
        name = m.group().lower()
        area = next((_num(t, "um") for t in tokens[1:] if t.endswith("um")), 0.0)
        lat = next((_num(t, "ps") for t in tokens[1:] if t.endswith("ps")), 0.0)
        power = next((_num(t, "pj") for t in tokens[1:] if t.endswith("pj")), 0.0)
        count = int(tokens[-1]) if len(tokens) > 1 and tokens[-1].isdigit() else 0
        if name == "register":
            reg = (area, lat)
        elif name == "mux":
            mux = (area, lat)
        else:
            fus[name] = FUType(name, area, lat, count, power)
    if reg is None:
        raise ValueError(f"{path}: no register line in library")
    return Library(fus, reg[0], reg[1], mux[0], mux[1])
