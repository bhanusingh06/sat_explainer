from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set

@dataclass
class RuleMeta:
    rule_id: str
    description: str = ""

@dataclass
class Clause:
    lits: List[int]
    rule_id: str = ""
    note: str = ""
    def __post_init__(self):
        # Normalize: unique literals, sorted for stable output
        self.lits = sorted(set(self.lits), key=lambda x: (abs(x), x))

@dataclass
class CNF:
    num_vars: int
    clauses: List[Clause]
    rules: Dict[str, RuleMeta] = field(default_factory=dict)

Assignment = Dict[int, bool]

def lit_is_true(lit: int, assign: Assignment):
    v = abs(lit)
    if v not in assign:
        return None
    val = assign[v]
    return val if lit > 0 else (not val)

def clause_status(clause: Clause, assign: Assignment):
    """Return (is_satisfied, is_conflict, unit_lit)."""
    trues = 0
    unassigned = []
    for lit in clause.lits:
        val = lit_is_true(lit, assign)
        if val is True:
            trues += 1
            break
        elif val is None:
            unassigned.append(lit)
    if trues > 0:
        return True, False, None
    if len(unassigned) == 0:
        return False, True, None
    if len(unassigned) == 1:
        return False, False, unassigned[0]
    return False, False, None

def unit_propagate(cnf: CNF, assign: Assignment, reasons: Dict[int, Clause]):
    """Classic UP with reason tracking. Returns (ok, conflict_clause)."""
    changed = True
    while changed:
        changed = False
        for cl in cnf.clauses:
            sat, conflict, unit_lit = clause_status(cl, assign)
            if sat:
                continue
            if conflict:
                return False, cl
            if unit_lit is not None:
                v = abs(unit_lit)
                val = (unit_lit > 0)
                if v in assign:
                    if assign[v] != val:
                        return False, cl
                    else:
                        continue
                assign[v] = val
                reasons[v] = cl
                changed = True
    return True, None

def _preferred_var_order(num_vars: int, assign: Assignment, core_hint_literals: Optional[List[int]]):
    """Prefer variables present in core_hint_literals (sign ignored)."""
    hinted = []
    if core_hint_literals:
        seen = set()
        for l in core_hint_literals:
            v = abs(l)
            if v not in seen and v not in assign:
                hinted.append(v)
                seen.add(v)
    rest = [v for v in range(1, num_vars + 1) if v not in assign and v not in hinted]
    return hinted + rest

def collect_assumption_causes(var: int, reasons: Dict[int, Clause], assumptions_set: Set[int], assign: Assignment):
    """Trace reason graph from var back to assumptions; return set of signed assumption literals."""
    frontier = [var]
    seen_vars = set()
    contributing_assumptions: Set[int] = set()
    while frontier:
        v = frontier.pop()
        if v in seen_vars:
            continue
        seen_vars.add(v)
        if v not in reasons:
            lit = v if assign.get(v, False) else -v
            if lit in assumptions_set or -lit in assumptions_set:
                contributing_assumptions.add(lit)
            continue
        cl = reasons[v]
        for lit in cl.lits:
            u = abs(lit)
            if u == v:
                continue
            if u in assign:
                frontier.append(u)
    return contributing_assumptions

def build_explanation(cnf: CNF, assign: Assignment, reasons: Dict[int, Clause], conflict_clause: Clause, assumptions: List[int]):
    """Human-usable UNSAT explanation with clause/rule mapping."""
    assumptions_set = set(assumptions)
    falsified_lits = []
    for lit in conflict_clause.lits:
        v = abs(lit)
        if v in assign:
            val = assign[v]
            is_true = val if lit > 0 else (not val)
            if not is_true:
                falsified_lits.append(lit)
    # Which assumptions ultimately caused those falsifications?
    assumption_causes: Set[int] = set()
    for lit in falsified_lits:
        v = abs(lit)
        assumption_causes |= collect_assumption_causes(v, reasons, assumptions_set, assign)
    # Which rules (clauses) participated via the reason graph?
    involved_rules: Set[str] = set()
    def walk_reasons(v: int, visited_vars: Set[int]):
        if v in visited_vars:
            return
        visited_vars.add(v)
        if v not in reasons:
            return
        cl = reasons[v]
        involved_rules.add(cl.rule_id)
        for lit in cl.lits:
            u = abs(lit)
            if u != v:
                walk_reasons(u, visited_vars)
    visited = set()
    for lit in falsified_lits:
        walk_reasons(abs(lit), visited)
    rules_info = []
    for rid in sorted(involved_rules):
        meta = cnf.rules.get(rid, RuleMeta(rid, ""))
        rules_info.append({
            "rule_id": meta.rule_id,
            "description": meta.description
        })
    return {
        "type": "unsat_explanation",
        "conflict_clause": {
            "lits": conflict_clause.lits,
            "rule_id": conflict_clause.rule_id,
            "note": conflict_clause.note,
        },
        "falsified_literals": falsified_lits,
        "assumption_causes": sorted(assumption_causes, key=lambda x: (abs(x), x)),
        "involved_rules": rules_info,
    }

def dpll_explain(cnf: CNF, assumptions: List[int], core_hint_literals: Optional[List[int]] = None):
    """DPLL with unit prop + backtracking; enhanced with hinted decision order."""
    assign: Assignment = {}
    reasons: Dict[int, Clause] = {}
    # Seed assumptions
    for a in assumptions:
        v = abs(a)
        val = (a > 0)
        if v in assign and assign[v] != val:
            return False, assign, {
                "type": "assumption_conflict",
                "conflicting_assumptions": list(sorted(set([a, -(a)]))),
            }
        assign[v] = val
    ok, confl = unit_propagate(cnf, assign, reasons)
    if not ok:
        return False, assign, build_explanation(cnf, assign, reasons, confl, assumptions)
    # Decisions
    stack = []
    while True:
        order = _preferred_var_order(cnf.num_vars, assign, core_hint_literals)
        v = order[0] if order else None
        if v is None:
            return True, assign, {"type": "model"}
        stack.append((assign.copy(), reasons.copy(), v, False))
        assign[v] = True
        ok, confl = unit_propagate(cnf, assign, reasons)
        if ok:
            continue
        # Backtrack / try False
        while True:
            if not stack:
                return False, assign, build_explanation(cnf, assign, reasons, confl, assumptions)
            prev_assign, prev_reasons, v_dec, tried_neg = stack.pop()
            assign, reasons = prev_assign, prev_reasons
            if not tried_neg:
                stack.append((assign.copy(), reasons.copy(), v_dec, True))
                assign[v_dec] = False
                ok, confl = unit_propagate(cnf, assign, reasons)
                if ok:
                    break
                else:
                    continue

def check_unsat_under_assumptions(cnf: CNF, assumptions: List[int], core_hint_literals: Optional[List[int]] = None):
    sat, _, _ = dpll_explain(cnf, assumptions, core_hint_literals=core_hint_literals)
    return not sat

def _clauses_with_hint_vars(cnf: CNF, core_hint_literals: List[int]):
    if not core_hint_literals:
        return []
    hint_vars = {abs(l) for l in core_hint_literals}
    return [c for c in cnf.clauses if any(abs(l) in hint_vars for l in c.lits)]

def mus_deletion_based(cnf: CNF, assumptions: List[int], core_hint_literals: Optional[List[int]] = None):
    """Greedy subset-minimal UNSAT core under assumptions; focused by hint vars if provided."""
    # Start from hinted subset if it is already UNSAT; else fall back to full CNF
    if core_hint_literals:
        focused = _clauses_with_hint_vars(cnf, core_hint_literals)
        if focused:
            test_cnf = CNF(cnf.num_vars, focused, cnf.rules)
            if check_unsat_under_assumptions(test_cnf, assumptions, core_hint_literals=core_hint_literals):
                core = focused
            else:
                core = cnf.clauses.copy()
        else:
            core = cnf.clauses.copy()
    else:
        core = cnf.clauses.copy()

    i = 0
    while i < len(core):
        test_clauses = core[:i] + core[i+1:]
        test_cnf = CNF(cnf.num_vars, test_clauses, cnf.rules)
        if check_unsat_under_assumptions(test_cnf, assumptions, core_hint_literals=core_hint_literals):
            core = test_clauses
        else:
            i += 1
    return core

def explain_with_mus(cnf: CNF, assumptions: List[int], core_hint_literals: Optional[List[int]] = None):
    """Top-level API: SAT model or UNSAT explanation + (subset-minimal) MUS."""
    sat, assign, info = dpll_explain(cnf, assumptions, core_hint_literals=core_hint_literals)
    if sat:
        return {"type": "sat", "model": assign, "note": "SAT under assumptions; no conflict to explain."}
    core = mus_deletion_based(cnf, assumptions, core_hint_literals=core_hint_literals)
    core_rules = sorted(set(c.rule_id for c in core if c.rule_id))
    return {
        "type": "unsat_with_core",
        "primary_explanation": info,
        "mus_size": len(core),
        "mus_clauses": [
            {"lits": c.lits, "rule_id": c.rule_id, "note": c.note} for c in core
        ],
        "mus_rules": [
            {"rule_id": rid, "description": cnf.rules.get(rid, RuleMeta(rid, "")).description}
            for rid in core_rules
        ],
        "hints_used": list(core_hint_literals) if core_hint_literals else []
    }

def load_dimacs(path: str) -> CNF:
    """Load plain DIMACS CNF (no metadata)."""
    clauses: List[Clause] = []
    max_var = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("c") or s.startswith("p"):
                continue
            lits = [int(x) for x in s.split() if x]
            if lits and lits[-1] == 0:
                lits = lits[:-1]
            for l in lits:
                max_var = max(max_var, abs(l))
            if lits:
                clauses.append(Clause(lits=lits))
    return CNF(num_vars=max_var, clauses=clauses, rules={})
