from sat_explainer import load_dimacs, explain_with_mus
cnf = load_dimacs("out.cnf")

assumptions = [81, 97, 15]        # customer selections
core_hint_literals = [15] # optional hints from core dump

report = explain_with_mus(cnf, assumptions, core_hint_literals=core_hint_literals)
import json
print(json.dumps(report, indent=2))
