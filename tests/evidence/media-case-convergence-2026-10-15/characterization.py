"""Characterize the restatement check on hand-written faithful rewordings, including ones built to trip it."""
import sys
sys.path.insert(0, ".")
from greg.cognition.evidence import distortions

FAITHFUL = [  # (claim, supporting span): every claim says what its span says
    ("Delays may fall by 12% with the new routing method.", "the new routing method may reduce delays by 12%"),
    ("Fuel costs were not lowered.", "It did not lower fuel costs."),
    ("Twelve percent fewer delays may follow.", "may reduce delays by 12%"),
    ("The method may cut delays by 12 percent.", "the new routing method may reduce delays by 12%"),
    ("Northgate drivers reported fewer missed windows.", "Drivers at Northgate reported fewer missed windows."),
    ("Revenue rose 4% in March.", "In March, revenue rose by 4%."),
    ("The trial failed to show a benefit.", "The trial did not show a benefit."),
    ("Costs went up 3%.", "Costs increased by 3%."),
    ("Results suggest the drug might help some patients.", "The results suggest that the drug may help some patients."),
    ("Each depot used the method.", "All depots used the method."),
    ("The policy is likely to lower emissions.", "The policy will probably lower emissions."),
    ("The vote passed 7-2.", "The council approved the measure by a 7-2 vote."),
]
DISTORTED = [  # (claim, supporting span, the change a careful reader would object to)
    ("Delays fell by 12% with the new routing method.", "the new routing method may reduce delays by 12%", "certainty"),
    ("Fuel costs were lowered.", "It did not lower fuel costs.", "negation"),
    ("The method cuts delays by 21%.", "the method may cut delays by 12%", "figure"),
    ("Every patient benefited.", "The results suggest that the drug may help some patients.", "scope/certainty"),
    ("Costs fell 3%.", "Costs increased by 3%.", "direction"),
    ("Southgate drivers reported fewer missed windows.", "Drivers at Northgate reported fewer missed windows.", "named term"),
    ("The drug cured the patients.", "The results suggest that the drug may help some patients.", "certainty"),
    ("Twenty percent fewer delays may follow.", "may reduce delays by 12%", "spelled-out figure (added after the first run)"),
    ("The trial showed a large benefit.", "The trial showed a small benefit.", "magnitude (not a checked class)"),
    ("The city council rejected the measure.", "The council approved the measure by a 7-2 vote.", "polarity by antonym (not checked)"),
]
fp = 0
print("faithful rewordings (a flag here is a false positive):")
for claim, span in FAITHFUL:
    found = [d["class"] for d in distortions(claim, [span])]
    fp += bool(found)
    print(f"  {'FLAG ' if found else 'ok   '} {found or ''} | {claim!r} <- {span!r}")
caught = 0
print("distortions (no flag here is a miss):")
for claim, span, kind in DISTORTED:
    found = [d["class"] for d in distortions(claim, [span])]
    caught += bool(found)
    print(f"  {'caught' if found else 'MISSED'} {found or ''} [{kind}] | {claim!r} <- {span!r}")
print(f"false positives: {fp} of {len(FAITHFUL)} faithful; caught: {caught} of {len(DISTORTED)} distorted")
print("These cases were written by the author of the check, after it was built: a characterization, not a benchmark.")
