"""
validate_annex_c.py
Re-validates the committed Annex C R32 third-place assignment table.
Run as a unit test in the WorldCupPredictor repo. Exits non-zero on any failure.

Checks:
  1. Exactly 495 rows, numbered 1..495 (via distinct keys + row ids).
  2. Every key is a sorted 8-subset of groups A..L; all C(12,8)=495 present, no dups.
  3. Bijection: each row's 8 assignments cover exactly its 8 qualifying groups.
  4. No-rematch: a group winner never hosts the third-placed team from its OWN group.
  5. Winner-slot set is exactly {A,B,D,E,G,I,K,L} (the 8 winners that receive a third).
"""
import json, sys
from itertools import combinations

ALL = [chr(ord('A') + i) for i in range(12)]            # A..L
EXPECTED_SLOTS = {'A', 'B', 'D', 'E', 'G', 'I', 'K', 'L'}

def main(path="annex_c_r32.json"):
    data = json.load(open(path))
    table = data["table"]
    errors = []

    # 1 / 2: completeness + all subsets
    keys = set(table)
    all_subsets = {''.join(sorted(c)) for c in combinations(ALL, 8)}
    if len(table) != 495:
        errors.append(f"row count {len(table)} != 495")
    if keys != all_subsets:
        errors.append(f"key set != all C(12,8); missing {len(all_subsets-keys)} extra {len(keys-all_subsets)}")

    row_ids = set()
    for key, r in table.items():
        row_ids.add(r["row"])
        groups = r["thirds"]
        assign = r["assign"]
        # group set sanity
        if ''.join(sorted(groups)) != key or len(set(groups)) != 8:
            errors.append(f"{key}: thirds/key mismatch")
        # 5: slot set
        if set(assign) != EXPECTED_SLOTS:
            errors.append(f"{key}: winner-slot set {set(assign)} != {EXPECTED_SLOTS}")
        # 3: bijection
        if set(assign.values()) != set(groups) or len(set(assign.values())) != 8:
            errors.append(f"{key}: bijection fail {sorted(assign.values())} vs {sorted(groups)}")
        # 4: no-rematch
        for slot, third in assign.items():
            if slot == third:
                errors.append(f"{key}: REMATCH winner {slot} vs 3{third}")

    if row_ids != set(range(1, 496)):
        errors.append("row ids not exactly 1..495")

    if errors:
        print(f"FAIL: {len(errors)} error(s)")
        for e in errors[:20]:
            print("  -", e)
        sys.exit(1)
    print("PASS: 495 rows, all C(12,8) combos, bijection holds, no same-group rematches.")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "annex_c_r32.json")
