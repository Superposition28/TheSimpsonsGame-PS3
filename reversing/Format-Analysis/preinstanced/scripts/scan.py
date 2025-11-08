#!/usr/bin/env python3
import argparse
import csv
import json
import mmap
import os
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_EXTS = {".rws.ps3.preinstanced", ".dff.ps3.preinstanced"}

def is_target_file(p: Path, exts):
    name = p.name.lower()
    for ext in exts:
        if name.endswith(ext):
            return True
    return False

def printable_ascii(b: bytes) -> str:
    # Map bytes to ASCII if safe; else dot
    return "".join(chr(x) if 32 <= x <= 126 else "." for x in b)

def scan_file_for_patterns(fp: Path, lengths, strides, mode, max_bytes=None):
    """
    Returns:
      per_key_occurs: dict[(L, stride, pattern[, offset])] -> total hits in THIS file
      per_key_once: set of keys -> indicates pattern occurred at least once in this file
    mode:
      - "any": key = (L, stride, pattern)
      - "offset": key = (L, stride, pattern, offset)
    """
    per_key_occurs = Counter()
    per_key_once = set()

    with open(fp, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        n = len(mm)
        if max_bytes is not None:
            n = min(n, max_bytes)

        for L in lengths:
            if L <= 0 or L > n:
                continue
            for s in strides:
                if s <= 0:
                    continue
                # iterate offsets with given stride
                end = n - L
                off = 0
                while off <= end:
                    pat = mm[off:off+L]
                    if mode == "offset":
                        key = (L, s, pat, off)
                    else:
                        key = (L, s, pat)
                    per_key_occurs[key] += 1
                    per_key_once.add(key)
                    off += s
    return per_key_occurs, per_key_once

def main():
    ap = argparse.ArgumentParser(
        description="Scan .rws.ps3.preinstanced / .dff.ps3.preinstanced for recurring byte patterns."
    )
    ap.add_argument("root", nargs="+", help="Root folder(s) to scan")
    ap.add_argument("--lengths", "-l", type=str, default="4,8,12",
                    help="Comma-separated pattern lengths in bytes (>=4). Default: 4,8,12")
    ap.add_argument("--strides", "-s", type=str, default="4,8,12",
                    help="Comma-separated stride (jump) sizes in bytes. Default: 4,8,12")
    ap.add_argument("--mode", choices=["any", "offset"], default="any",
                    help="Count patterns anywhere in a file (any) or only when found at the same absolute offset (offset). Default: any")
    ap.add_argument("--min-files", type=int, default=10,
                    help="Only report patterns that appear in at least this many different files. Default: 10")
    ap.add_argument("--topk", type=int, default=200,
                    help="Limit output to top-K patterns per (length,stride) by file-count (then total hits). Default: 200 (per group)")
    ap.add_argument("--max-bytes", type=int, default=None,
                    help="If set, only scan this many bytes from the start of each file (speeds things up).")
    ap.add_argument("--exts", type=str, default=",".join(sorted(DEFAULT_EXTS)),
                    help=f"Comma-separated file endings to include. Default: {','.join(sorted(DEFAULT_EXTS))}")
    ap.add_argument("--csv-out", type=str, default=None, help="Write results to CSV path")
    ap.add_argument("--json-out", type=str, default=None, help="Write results to JSON path")
    ap.add_argument("--examples-per-pattern", type=int, default=5,
                    help="How many example (file, offset) pairs to keep per pattern. Default: 5")
    args = ap.parse_args()

    lengths = sorted({int(x) for x in args.lengths.split(",") if x.strip()})
    strides = sorted({int(x) for x in args.strides.split(",") if x.strip()})
    exts = {"." + e.lstrip(".") for e in args.exts.split(",") if e.strip()}
    if any(L < 4 for L in lengths):
        raise SystemExit("All pattern lengths must be >= 4.")

    # Collect all candidate files
    files = []
    for r in args.root:
        rp = Path(r)
        if rp.is_file():
            if is_target_file(rp, exts):
                files.append(rp)
        else:
            for p in rp.rglob("*"):
                if p.is_file() and is_target_file(p, exts):
                    files.append(p)
    if not files:
        print("No matching files found.")
        return

    # Global aggregations
    # per_key_files: counts in how many distinct files the key appears
    per_key_files = Counter()
    # per_key_hits: total occurrences across all files
    per_key_hits = Counter()
    # examples: key -> list of (file, offset) examples
    examples = defaultdict(list)

    # To avoid huge memory, we don't store per-file details beyond examples.
    for idx, fp in enumerate(files, 1):
        try:
            per_occurs, per_once = scan_file_for_patterns(
                fp, lengths, strides, args.mode, max_bytes=args.max_bytes
            )
        except Exception as e:
            print(f"[WARN] Failed {fp}: {e}")
            continue

        # Update totals
        for key, hits in per_occurs.items():
            per_key_hits[key] += hits

        # For file-counts and examples, we only need to note presence once per file
        for key in per_once:
            per_key_files[key] += 1
            # capture a few example offsets for reporting
            # Determine an offset to store (if in 'any' mode, just store -1 as placeholder; we can’t know which occurrence without re-scan)
            if args.mode == "offset":
                offset = key[-1]  # explicit offset in key
            else:
                # put -1 to indicate "varies"; still store file path
                offset = -1
            if len(examples[key]) < args.examples_per_pattern:
                examples[key].append((str(fp), offset))

        if idx % 100 == 0:
            print(f"[Info] Scanned {idx}/{len(files)} files...", flush=True)

    # Prepare results grouped by (length, stride)
    grouped = defaultdict(list)
    for key, filecnt in per_key_files.items():
        if filecnt < args.min_files:
            continue
        L, s = key[0], key[1]
        pat = key[2]
        pat_hex = pat.hex()
        pat_ascii = printable_ascii(pat)
        total_hits = per_key_hits[key]
        if args.mode == "offset":
            offset = key[3]
        else:
            offset = None
        grouped[(L, s)].append({
            "length": L,
            "stride": s,
            "pattern_hex": pat_hex,
            "pattern_ascii": pat_ascii,
            "files_count": filecnt,
            "total_hits": total_hits,
            "offset": offset,
            "examples": examples.get(key, [])
        })

    # Sort within each (L,s) by files_count desc, then total_hits desc
    for k in grouped:
        grouped[k].sort(key=lambda r: (r["files_count"], r["total_hits"]), reverse=True)
        if args.topk:
            grouped[k] = grouped[k][:args.topk]

    # Print summary to stdout
    for (L, s), rows in sorted(grouped.items()):
        print(f"\n=== Length {L}, Stride {s} ===")
        header = "files  hits   offset   pattern(hex)                               ascii"
        print(header)
        print("-" * len(header))
        for r in rows:
            off_str = f"{r['offset']:>8}" if r["offset"] is not None else "   (any)"
            print(f"{r['files_count']:>5}  {r['total_hits']:>5}  {off_str}  {r['pattern_hex'][:40]:<40}  {r['pattern_ascii']}")

    # Optional CSV/JSON outputs
    if args.csv_out:
        with open(args.csv_out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["length","stride","files_count","total_hits","offset","pattern_hex","pattern_ascii","examples"])
            for rows in grouped.values():
                for r in rows:
                    w.writerow([
                        r["length"], r["stride"], r["files_count"], r["total_hits"],
                        r["offset"] if r["offset"] is not None else "",
                        r["pattern_hex"], r["pattern_ascii"],
                        "; ".join(f"{fp}@{off}" for fp, off in r["examples"])
                    ])
        print(f"\n[OK] Wrote CSV: {args.csv_out}")

    if args.json_out:
        flat = []
        for rows in grouped.values():
            flat.extend(rows)
        with open(args.json_out, "w") as f:
            json.dump(flat, f, indent=2)
        print(f"[OK] Wrote JSON: {args.json_out}")

if __name__ == "__main__":
    main()
