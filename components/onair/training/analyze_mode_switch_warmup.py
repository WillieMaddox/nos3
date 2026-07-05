"""NOS3-303 — measure the mode-switch transient decay to size the IF warmup.

The IF plugin re-arms an N-frame warmup (`ModeSwitchWarmupFrames`, default 600 ≈
124 s at ~4.83 fps) on every routing scenario switch, suppressing ALERT/CLEAR
during it. An attack in a mode held shorter than the warmup is never flagged.

This reads an IF side-file (iforest_out_*.csv: frame_idx, scenario, score,
threshold, is_anomaly, alert, cleared), aligns every frame to its
frames-since-last-switch, and reports the raw anomaly rate vs that offset. Where
the rate decays to the steady-state baseline = the warmup the transient actually
needs; anything beyond that is avoidable operational blind time.

    python3 analyze_mode_switch_warmup.py <iforest_out_*.csv> [--fps 4.83] [--bin 25]

Provenance: a single session gives few switches — treat as suggestive. Re-run
over a dedicated nominal mode-cycling soak before changing the live setting.
"""
import argparse
import csv
from collections import defaultdict


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("side_file")
    p.add_argument("--fps", type=float, default=4.83, help="frames/sec (for s labels)")
    p.add_argument("--bin", type=int, default=25, help="bin width in frames")
    p.add_argument("--max-offset", type=int, default=700)
    p.add_argument("--settle-pct", type=float, default=3.0,
                   help="anomaly-rate %% at/below which the transient is 'settled'")
    args = p.parse_args()

    rows = list(csv.DictReader(open(args.side_file)))
    scn = [r["scenario"] for r in rows]
    anom = [r["is_anomaly"] in ("1", "True", "true") for r in rows]
    switches = [i for i in range(1, len(rows)) if scn[i] != scn[i - 1]]

    fss, last = [0] * len(rows), 0
    for i in range(len(rows)):
        if i and scn[i] != scn[i - 1]:
            last = i
        fss[i] = i - last

    # steady-state baseline = anomaly rate for frames well past any warmup
    tail = [anom[i] for i in range(len(rows)) if fss[i] >= args.max_offset]
    baseline = 100.0 * sum(tail) / len(tail) if tail else 0.0

    agg = defaultdict(lambda: [0, 0])
    for i in range(len(rows)):
        b = fss[i] // args.bin
        agg[b][0] += anom[i]
        agg[b][1] += 1

    print(f"{len(rows)} frames, {len(switches)} scenario switches; "
          f"steady-state baseline anomaly rate = {baseline:.1f}%")
    print(f"\nframes-since-switch → raw anomaly rate (bin={args.bin}f ≈ "
          f"{args.bin/args.fps:.0f}s):")
    settled_at = None
    for b in sorted(agg):
        lo, hi = b * args.bin, (b + 1) * args.bin - 1
        if lo > args.max_offset:
            break
        a, n = agg[b]
        rate = 100.0 * a / n if n else 0.0
        if settled_at is None and lo > 0 and rate <= args.settle_pct:
            settled_at = lo
        bar = "█" * int(rate / 2)
        print(f"  {lo:4d}-{hi:4d}f ({lo/args.fps:4.0f}s) n={n:6d}  {rate:5.1f}%  {bar}")

    if settled_at is not None:
        print(f"\ntransient settles (≤{args.settle_pct}%) by ~frame {settled_at} "
              f"(~{settled_at/args.fps:.0f}s). A warmup of ~{settled_at} frames "
              f"(+margin) covers it; frames beyond that are avoidable blind time.")
    else:
        print("\ntransient did not settle within max-offset — need longer-dwell data.")


if __name__ == "__main__":
    main()
