SAT Explainer – Debugging UNSAT with Clear Explanations and Minimal Cores

This Python library helps you debug unsatisfiable (UNSAT) results in SAT-based systems by showing exactly why the conflict happened.
It traces the chain of reasoning from your assumptions to the clause that failed, lists all the rules that participated, and can shrink the conflict down to a minimal unsatisfiable subset (MUS) for easy human inspection.

When you are building a constraint-based solver, this tool will help you answer the critical question:
        “Why am I getting UNSAT, and what’s the smallest set of clauses that cause it?”

Why You Might Need This
When a SAT solver returns UNSAT, the cause isn’t always obvious. This library bridges that gap by:
    1. Pinpointing the conflict clause.
    2. Showing the exact assumptions that led to the contradiction.
    3. Listing all involved clauses with their rule IDs and notes for human-friendly interpretation.
    4. Optionally shrinking the problem to a subset-minimal UNSAT core, removing noise and making it easier to debug.


What It Does
    The tool reads a CNF file where each clause can have a rule_id and a human-readable note.
    It then runs a DPLL-style search with reason tracking.
    When it encounters UNSAT for the given assumptions, it will:

        1. Identify the precise conflict clause that was violated.

        2. Trace back to the exact assumptions that ultimately caused the conflict.

        3. List all clauses (and their rules) that took part in the contradiction, using a reason graph.

        4. Optionally shrink the conflict set to a minimal unsatisfiable subset (MUS) so you only see the clauses that truly matter for the conflict.

How It Works

1. Reason Tracking
    Every time a variable is forced to a value through unit propagation, the tool records which clause caused that decision.
    When a conflict happens, it walks these “reason links” backwards to the original assumptions. This gives a clear cause-and-effect chain for the failure.

    The DPLL process works like this:

        1. Apply unit propagation until either a conflict appears or no further units exist.
        2. If all variables are assigned, you have a SAT model.
        3. Otherwise, choose an unassigned variable, try assigning it true; if that fails, backtrack and try false.
        4. For every forced assignment from unit propagation, record the clause that forced it.
        5. Assumptions and direct decisions have no “reason” clause — they are roots in the chain.
        6. On conflict, follow the links from the conflict clause back through the falsifying literals until you reach the assumptions.

    This approach explains how the conflict arose, not just the fact that it did.

2. MUS Shrinking
    When the set of clauses causing the conflict is identified, the tool can attempt to shrink it for easier debugging.
    It works by trying to remove each clause and checking if UNSAT still holds:

        1. If removing a clause still leaves the set UNSAT, that clause is not essential and is discarded.
        2. If removing it makes the set SAT, that clause is essential and kept.

    The result is subset-minimal: you can’t remove any more clauses without breaking the UNSAT property.
    It’s not guaranteed to be the smallest possible MUS, but it’s enough for human debugging.
    Because this is computationally expensive, it’s meant for offline debugging rather than runtime.

3. Extra Features Beyond Standard DPLL
    Reason Tracking: Unlike plain DPLL, this implementation always stores the reason for each assignment, enabling clear conflict explanations.

    Conflict Explanation: For UNSAT results, the tool:

        1. Shows the conflict clause.
        2. Traces the assumptions that led there.
        3. Lists all involved clauses and rules.

    Greedy MUS Shrinking: An extra step to reduce the conflict to a minimal relevant set for human reading.

4. Core-Hint Literals
    If you have an UNSAT core dump from a production solver, you can pass those literals as hints:

        1. Branching order: Variables from the hint are tried first, making it more likely to follow the same failure path the solver saw.
        2. MUS shrink focus: The shrink process can start from only clauses containing those literals, expanding if needed. This can significantly reduce MUS time for large CNFs.

File Overview
    sat_explainer.py — Core library for CNF reasoning, UNSAT explanation, and MUS shrinking.

    invoke_sat_explainer.py — CLI script to load CNF, assumptions, and optional core hints, then produce the explanation.

    out.cnf — Example converted CNF to be passed to the explainer.

    sample_debug_output.json — Example explanation output.

    README.md — This file.

How to Use
    1. Prepare your assumptions (signed integers for literals):
       assumptions = [101, -202, 303]

    2. Optionally, add core-hint literals (signs are ignored for hinting):
       core_hint_literals = [101, -202]
    
    3. Run the explainer:
       uv run invoke_sat_explainer.py

Output
The result is a JSON object containing:

    type: either sat or unsat_with_core
    primary_explanation:
        conflict_clause — The clause directly falsified.
        falsified_literals — The specific literals that were false.
        assumption_causes — Which assumptions triggered the problem.
        involved_rules — List of rules/clauses that participated.
    mus_size, mus_clauses, mus_rules — The subset-minimal UNSAT core.
    hints_used — Any hints you passed in.

Notes
    a. This tool is designed for clarity and insight, not maximum performance.
    b. MUS shrinking is deletion-based and intended for offline use.
    c. If the hinted subset of clauses turns out SAT, the MUS step falls back to the full CNF.
    d. If you want human-friendly variable names in the output, map your IDs outside this library.