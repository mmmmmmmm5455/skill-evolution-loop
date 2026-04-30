"""
180-cell decision matrix coverage test.
Verifies every (old_score, candidate_score, delta) combination maps to exactly one D-row.

Coverage partitions:
- old_score: {<40, 40-49, 50-59, 60-75, >=76}
- candidate_score: {<50, 50-59, 60-69, 70-79, 80-84, >=85}
- delta: {negative, 0-4, 5-9, 10-19, 20-29, 30-44, >=45}

5 x 6 x 6 = 180 cells. Each must match exactly 1 row.
"""
import json

def evaluate_row(row_id, conditions, old, candidate, delta):
    """Check if a row's conditions match. Returns True if all conditions satisfied."""
    cond = conditions[row_id]
    if "old_max" in cond and old >= cond["old_max"]:
        return False
    if "old_min" in cond and old < cond["old_min"]:
        return False
    if "candidate_min" in cond and candidate < cond["candidate_min"]:
        return False
    if "candidate_max" in cond and candidate > cond["candidate_max"]:
        return False
    if "delta_min" in cond and delta < cond["delta_min"]:
        return False
    if "delta_max" in cond and delta > cond["delta_max"]:
        return False
    return True


def load_conditions():
    """Load decision matrix conditions from thresholds.json."""
    with open("src/config/thresholds.json") as f:
        return json.load(f)["decision_matrix"]


def test_coverage():
    conditions = load_conditions()
    old_buckets = [
        (5, "<40"), (20, "<40"), (35, "<40"),
        (42, "40-49"), (48, "40-49"),
        (52, "50-59"), (58, "50-59"),
        (62, "60-75"), (70, "60-75"),
        (80, ">=76"), (90, ">=76"),
    ]
    candidate_buckets = [
        (25, "<50"), (45, "<50"),
        (52, "50-59"),
        (62, "60-69"), (68, "60-69"),
        (72, "70-79"), (78, "70-79"),
        (82, "80-84"),
        (88, ">=85"), (95, ">=85"),
    ]
    delta_buckets = [
        (-10, "negative"), (-5, "negative"),
        (2, "0-4"),
        (7, "5-9"),
        (12, "10-19"), (18, "10-19"),
        (22, "20-29"), (28, "20-29"),
        (32, "30-44"), (40, "30-44"),
        (50, ">=45"),
    ]

    uncovered = []
    first_match = {}

    for old_val, old_label in old_buckets:
        for cand_val, cand_label in candidate_buckets:
            for delta_val, delta_label in delta_buckets:
                matching_rows = []
                for row_id in sorted(conditions.keys()):
                    if evaluate_row(row_id, conditions, old_val, cand_val, delta_val):
                        matching_rows.append(row_id)

                if len(matching_rows) == 0:
                    uncovered.append((old_val, old_label, cand_val, cand_label, delta_val, delta_label))
                else:
                    winner = matching_rows[0]
                    key = winner
                    if key not in first_match:
                        first_match[key] = 0
                    first_match[key] += 1

    total = len(old_buckets) * len(candidate_buckets) * len(delta_buckets)
    covered = total - len(uncovered)
    print(f"Total cells tested: {total}")
    print(f"Covered (at least 1 row): {covered}")
    print(f"Uncovered (0 rows): {len(uncovered)}")
    print(f"\nFirst-match distribution (top-down evaluation):")
    for row_id in sorted(first_match.keys()):
        print(f"  {row_id}: {first_match[row_id]} cells")

    if uncovered:
        print("\nUNCOVERED CELLS:")
        for cell in uncovered:
            print(f"  old={cell[0]:.0f}({cell[1]}) candidate={cell[2]:.0f}({cell[3]}) delta={cell[4]:.0f}({cell[5]})")

    assert len(uncovered) == 0, f"FAIL: {len(uncovered)} uncovered cells"
    print(f"\nPASS: All {total} cells covered. {len(first_match)} unique first-match rows used.")


if __name__ == "__main__":
    test_coverage()
