#!/usr/bin/env python3
"""Fit constant / linear / quadratic growth models to the median timings in probe results files.

Usage: fit.py results.json [results_r3.json ...]   (medians are averaged over the files given)
Models (least squares on the raw ms values, N in revisions):
  const  t = a
  linear t = a + b*N
  quad   t = a + c*N^2        (pure quadratic growth on top of a fixed cost)
Reports RMS relative residual for each model; the lowest wins.
"""
import json
import math
import statistics
import sys

files = [json.load(open(p)) for p in sys.argv[1:]]


def median_of(cell, path):
    for key in path:
        cell = cell[key]
    return cell["median_ms"]


METRICS = {
    "checkpoint": ("checkpoint",),
    "carry large": ("carry_large", "timing"),
    "carry small": ("carry_small", "timing"),
    "status": ("status",),
    "verify_store": ("parts", "verify_store"),
}


def lsq(xs, ys):
    """Fit y = a + b*x; return a, b."""
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    return my - b * mx, b


def rms_rel(pred, ys):
    return math.sqrt(statistics.fmean(((p - y) / y) ** 2 for p, y in zip(pred, ys)))


for series in ("drops", "resolved"):
    ns = sorted(set.intersection(*(set(f["series"][series]) for f in files)), key=int)
    if len(ns) < 3:
        continue
    xs = [int(n) for n in ns]
    print(f"== {series}  N={xs}  ({len(files)} file(s) averaged)")
    for name, path in METRICS.items():
        ys = [statistics.fmean(median_of(f["series"][series][n], path) for f in files) for n in ns]
        const = statistics.fmean(ys)
        a1, b1 = lsq(xs, ys)
        a2, c2 = lsq([x * x for x in xs], ys)
        slope = math.log(ys[-1] / ys[0]) / math.log(xs[-1] / xs[0])
        loglog = lsq([math.log(x) for x in xs], [math.log(y) for y in ys])[1]
        print(
            f"{name:12} ys={[round(y, 1) for y in ys]}  rel-RMS const {rms_rel([const] * len(ys), ys):.2f}"
            f"  linear {rms_rel([a1 + b1 * x for x in xs], ys):.2f} (a={a1:.1f} ms, b={b1 * 1000:.1f} us/rev)"
            f"  quad {rms_rel([a2 + c2 * x * x for x in xs], ys):.2f}  | log-log p={loglog:.2f}"
        )
