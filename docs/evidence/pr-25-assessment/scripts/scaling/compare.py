#!/usr/bin/env python3
"""Compare two probe result files: structural fields must match exactly, timings are shown as % deltas."""
import json
import sys

a_path, b_path = sys.argv[1], sys.argv[2]
a, b = json.load(open(a_path)), json.load(open(b_path))
STRUCT = ("budget_limit", "budget_used", "included", "omitted", "unacc_included",
          "unacc_omitted", "history_revisions_read", "projection_bytes")
bad = 0
rows = []
for series in ("drops", "resolved"):
    for n in sorted(set(a["series"][series]) & set(b["series"][series]), key=int):
        ca, cb = a["series"][series][n], b["series"][series][n]
        for recv in ("carry_large", "carry_small"):
            sa, sb = ca[recv].get("shape", {}), cb[recv].get("shape", {})
            for key in STRUCT:
                if sa.get(key) != sb.get(key):
                    bad += 1
                    print(f"STRUCT MISMATCH {series} N={n} {recv}.{key}: {sa.get(key)} vs {sb.get(key)}")
        for key in ("revision_count", "unaccounted_in_status", "verify_valid"):
            if ca["sanity"][key] != cb["sanity"][key]:
                bad += 1
                print(f"SANITY MISMATCH {series} N={n} {key}")
        if ca["db_bytes_built"] != cb["db_bytes_built"]:
            print(f"note: db_bytes_built differs {series} N={n}: {ca['db_bytes_built']} vs {cb['db_bytes_built']}")
        def med(c, path):
            for p in path:
                c = c[p]
            return c["median_ms"]
        metrics = {
            "ckpt": ("checkpoint",),
            "carryL": ("carry_large", "timing"),
            "carryS": ("carry_small", "timing"),
            "status": ("status",),
            "verify": ("parts", "verify_store"),
        }
        cells = []
        for name, path in metrics.items():
            x, y = med(ca, path), med(cb, path)
            cells.append(f"{name} {x:.1f}/{y:.1f} ({(y - x) / x * 100:+.0f}%)")
        rows.append(f"{series:8} N={n:>4}: " + "  ".join(cells))
print("\n".join(rows))
print("structural/sanity mismatches:", bad)
