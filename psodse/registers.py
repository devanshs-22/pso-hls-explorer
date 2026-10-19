"""Storage variables, Register Allocation Table (RAT) and interconnect (mux/demux).

Variables
    every primary input (operand 0) is its own variable V0, V1, ...;
    every operation result is a variable too (numbered after the inputs),
    so for DCT-4pt: V0..V7 are the 8 inputs, V8..V14 are the results of op1..op7.

Lifetime
    A value must sit in a register across every CS *boundary* between the step
    that produces it and the last step that reads it. Boundary b is the
    register write at the end of CS b (b = 0 is "inputs loaded before CS1").
    A final output is stored once, at the boundary after the step producing it.

Register sharing / colouring
    Two variables whose lifetimes do not overlap may share one register.
    Lifetimes are intervals, so the left-edge algorithm colours them with the
    minimum possible number of registers (= max number of values alive at once).
"""
from dataclasses import dataclass


# Register colours in the order used by Table 1 of the paper (name, abbreviation, hex).
# Each physical register gets one colour; a colour holding different values over the
# control steps is register reuse, which is what "register colouring" means.
REGISTER_COLOURS = [
    ("Red", "R", "#d64545"), ("Green", "G", "#2e9e5b"), ("Indigo", "I", "#4b3fa8"),
    ("Blue", "BL", "#2a78d6"), ("Yellow", "Y", "#d9a400"), ("Black", "B", "#3a3a38"),
    ("Violet", "V", "#8e5cd9"), ("Pink", "P", "#e87ba4"), ("Lime", "LI", "#7cb82f"),
    ("Olive", "O", "#7a7a12"), ("Aqua", "A", "#1aa9b0"), ("Teal", "T", "#13807d"),
    ("Gray", "G", "#8a8984"), ("Maroon", "M", "#8a1c1c"), ("Silver", "S", "#a3a39e"),
    ("Khaki", "K", "#b3a95a"), ("Lavender", "L", "#a996e6"), ("Crimson", "C", "#c81d42"),
    ("Wheat", "W", "#cfa968"), ("Beige", "B", "#bfae86"), ("Magenta", "M", "#c2187a"),
    ("Orange", "O", "#eb6834"),
]


def register_colour(r):
    """(name, abbreviation, hex) of register r; names repeat with a suffix after 22."""
    name, abbr, hx = REGISTER_COLOURS[r % len(REGISTER_COLOURS)]
    lap = r // len(REGISTER_COLOURS)
    return (f"{name}-{lap + 1}", f"{abbr}{lap + 1}", hx) if lap else (name, abbr, hx)


@dataclass
class Variable:
    name: str
    producer: int         # 0 for primary inputs
    birth: int            # first boundary it occupies
    last: int             # last boundary it occupies
    register: int = -1


@dataclass
class RegisterAllocation:
    variables: dict       # name -> Variable
    op_inputs: dict       # op_id -> (var name, var name)
    op_output: dict       # op_id -> var name
    n_registers: int
    table: list           # table[boundary][register] = var name or None

    def describe(self, name):
        v = self.variables[name]
        return "primary input" if v.producer == 0 else f"output of op {v.producer}"


def build_variables(dfg):
    op_inputs, op_output, order = {}, {}, []
    n = 0
    for op in dfg.ops.values():
        names = []
        for operand in (op.operand1, op.operand2):
            if operand == 0:
                names.append(f"V{n}")
                order.append((f"V{n}", 0))
                n += 1
            else:
                names.append(None)            # filled below once outputs are named
        op_inputs[op.op_id] = names
    for op in dfg.ops.values():
        op_output[op.op_id] = f"V{n}"
        order.append((f"V{n}", op.op_id))
        n += 1
    for op in dfg.ops.values():
        ins = op_inputs[op.op_id]
        for k, operand in enumerate((op.operand1, op.operand2)):
            if operand:
                ins[k] = op_output[operand]
        op_inputs[op.op_id] = tuple(ins)
    return order, op_inputs, op_output


def allocate_registers(dfg, schedule):
    order, op_inputs, op_output = build_variables(dfg)
    readers = {}
    for oid, ins in op_inputs.items():
        for v in set(ins):
            readers.setdefault(v, []).append(schedule.op_step[oid])

    variables = {}
    for name, producer in order:
        birth = 0 if producer == 0 else schedule.op_step[producer]
        last = max(readers[name]) - 1 if name in readers else birth
        variables[name] = Variable(name, producer, birth, last)

    # Left-edge algorithm: sort by start, drop each value in the first free register
    reg_free_after = []                     # last occupied boundary of each register
    for v in sorted(variables.values(), key=lambda v: (v.birth, v.last, int(v.name[1:]))):
        for r, busy_until in enumerate(reg_free_after):
            if busy_until < v.birth:
                v.register = r
                reg_free_after[r] = v.last
                break
        else:
            v.register = len(reg_free_after)
            reg_free_after.append(v.last)

    n_regs = len(reg_free_after)
    table = [[None] * n_regs for _ in range(schedule.n_steps + 1)]
    for v in variables.values():
        for b in range(v.birth, v.last + 1):
            table[b][v.register] = v.name
    return RegisterAllocation(variables, op_inputs, op_output, n_regs, table)


def fu_label(fu, idx):
    return f"{fu[0].upper()}{idx + 1}"       # adder 0 -> A1, multiplier 1 -> M2


def interconnect(dfg, schedule, regs):
    """Multiplexers in front of FU ports / registers and demuxes after them.

    Returns (list of (location, 'k:1 mux' | '1:k demux'), number of equivalent 2:1 muxes).
    A k:1 mux is built from k-1 two-input muxes (the library only lists mux2:1).
    """
    port_src, reg_src, fu_dst, reg_dst = {}, {}, {}, {}
    for oid, (fu, idx) in schedule.binding.items():
        unit = fu_label(fu, idx)
        for port, v in enumerate(regs.op_inputs[oid]):
            r = regs.variables[v].register
            port_src.setdefault(f"{unit}.in{port + 1}", set()).add(r)
            reg_dst.setdefault(r, set()).add(f"{unit}.in{port + 1}")
        r_out = regs.variables[regs.op_output[oid]].register
        reg_src.setdefault(r_out, set()).add(unit)
        fu_dst.setdefault(unit, set()).add(r_out)
    for v in regs.variables.values():
        if v.producer == 0:
            reg_src.setdefault(v.register, set()).add("IN")

    items, mux2 = [], 0
    for loc, src in sorted(port_src.items()):
        if len(src) > 1:
            items.append((loc, f"{len(src)}:1 mux"))
            mux2 += len(src) - 1
    for r, src in sorted(reg_src.items()):
        if len(src) > 1:
            items.append((f"R-{r}.in", f"{len(src)}:1 mux"))
            mux2 += len(src) - 1
    for unit, dst in sorted(fu_dst.items()):
        if len(dst) > 1:
            items.append((f"{unit}.out", f"1:{len(dst)} demux"))
    for r, dst in sorted(reg_dst.items()):
        if len(dst) > 1:
            items.append((f"R-{r}.out", f"1:{len(dst)} demux"))
    return items, mux2
