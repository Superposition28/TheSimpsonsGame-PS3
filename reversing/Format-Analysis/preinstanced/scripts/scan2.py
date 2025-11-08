#!/usr/bin/env python3
import argparse
import os
from pathlib import Path
from collections import Counter, defaultdict
import mmap
import math
import json
import sys
import time

TARGET_EXTS = {".rws.ps3.preinstanced", ".dff.ps3.preinstanced"}

def is_target(p: Path, exts):
    n = p.name.lower()
    return any(n.endswith(e) for e in exts)

def chunk4_iter(mm, limit=None, stride=4):
    n = len(mm) if limit is None else min(len(mm), limit)
    end = n - (n % 4)  # align down
    for off in range(0, end, stride):
        yield off, bytes(mm[off:off+4])

def load_files(roots, exts, progress=True):
    files = []
    start = time.time()
    for r in roots:
        p = Path(r)
        if p.is_file():
            if is_target(p, exts):
                files.append(p)
        else:
            # We don't know how many in advance; print periodic heartbeats.
            cnt = 0
            for q in p.rglob("*"):
                if q.is_file() and is_target(q, exts):
                    files.append(q)
                cnt += 1
                if progress and cnt % 5000 == 0:
                    print(f"[scan] walking '{p}' ... seen ~{cnt:,} paths, matched {len(files):,} files", file=sys.stderr)
    if progress:
        dur = time.time() - start
        print(f"[scan] found {len(files):,} target files in {dur:.2f}s", file=sys.stderr)
    return files

def mmap_bytes(p: Path):
    f = open(p, "rb")
    return f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

def hex4(b: bytes) -> str:
    return b.hex()

def wildcard():
    return "????"

def consensus_by_size(files, max_bytes, stride, min_support, min_files, topk_per_size, progress=True):
    """Build a whole-file consensus pattern for same-size files, 4-byte tokenized."""
    # Group by size (or truncated size if max_bytes is set)
    groups = defaultdict(list)
    for fp in files:
        size = fp.stat().st_size
        if max_bytes is not None:
            size = min(size, max_bytes)
            size -= (size % 4)
        else:
            size -= (size % 4)
        if size <= 0:
            continue
        groups[size].append(fp)

    results = []

    for size, fps in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if len(fps) < max(2, min_files):
            continue

        # For each position i (4-byte index), count tokens across files
        pos_counters = [Counter() for _ in range(size // 4)]
        participating = 0
        if progress:
            print(f"[consensus] size={size} bytes, files={len(fps)} -> counting tokens", file=sys.stderr)

        every = max(1, len(fps)//20)  # ~20 updates
        for idx, fp in enumerate(fps, 1):
            try:
                f, mm = mmap_bytes(fp)
            except Exception:
                continue
            participating += 1
            end = size
            i = 0
            for off in range(0, end, 4):
                tok = bytes(mm[off:off+4])
                pos_counters[i][tok] += 1
                i += 1
            mm.close(); f.close()
            if progress and (idx % every == 0 or idx == len(fps)):
                print(f"[consensus] processed {idx}/{len(fps)} files for size={size}", file=sys.stderr)

        if participating < max(2, min_files):
            continue

        # Build consensus sequence with wildcards for low support
        pattern = []
        concrete_count = 0
        for i, cnt in enumerate(pos_counters):
            if not cnt:
                pattern.append(wildcard())
                continue
            tok, c = cnt.most_common(1)[0]
            support = c / participating
            if support >= min_support:
                pattern.append(hex4(tok))
                concrete_count += 1
            else:
                pattern.append(wildcard())

        # Compress to keep output readable: collapse consecutive wildcards counts (optional leave expanded)
        # Here we keep expanded (one token per 4 bytes) so you can map offsets easily.
        coverage = concrete_count / max(1, len(pattern))
        results.append({
            "mode": "consensus_by_size",
            "size_bytes": size,
            "files_in_group": participating,
            "min_support": min_support,
            "coverage": round(coverage, 4),
            "pattern_tokens": pattern[:topk_per_size*1000000]  # no-op cap
        })
        if progress:
            print(f"[consensus] done size={size} (coverage={coverage:.2%})", file=sys.stderr)
    return results

def anchor_growth(files, max_bytes, stride, min_files, min_support, anchor_topk, max_grow_tokens, left_context=0, progress=True):
    """
    1) Count global token frequencies (4-byte tokens) across files.
       - support = number of distinct files containing the token.
    2) Pick top-K anchors.
    3) For each anchor:
       - find every occurrence (file, offset).
       - grow to the right token-by-token:
         next token = majority among occurrences that have a following token;
         if support >= min_support (by files, not occurrences), lock it;
         else place wildcard and keep going.
       - stop when fewer than min_files files still participate, or reach max_grow_tokens.
    """
    token_files = defaultdict(set)  # token -> set(files)
    # First pass: collect tokens per file
    if progress:
        print(f"[anchor] first pass: counting token support across {len(files)} files", file=sys.stderr)
    every = max(1, len(files)//20)
    for idx, fp in enumerate(files, 1):
        try:
            f, mm = mmap_bytes(fp)
        except Exception:
            continue
        seen = set()
        nlimit = len(mm)
        if max_bytes is not None:
            nlimit = min(nlimit, max_bytes - (max_bytes % 4))
        for off, tok in chunk4_iter(mm, limit=nlimit, stride=stride):
            seen.add(tok)
        for t in seen:
            token_files[t].add(fp)
        mm.close(); f.close()
        if progress and (idx % every == 0 or idx == len(files)):
            print(f"[anchor] first pass: processed {idx}/{len(files)} files", file=sys.stderr)

    # Rank anchors by how many distinct files contain them
    ranked = sorted(token_files.items(), key=lambda kv: -len(kv[1]))
    anchors = ranked[:anchor_topk]

    patterns = []

    for rank, (anchor_tok, files_with) in enumerate(anchors, 1):
        # Collect occurrences (file, offset) where this token appears
        occurrences = []
        if progress:
            print(f"[anchor] ({rank}/{len(anchors)}) anchor={hex4(anchor_tok)} appears in {len(files_with)} files -> locating occurrences", file=sys.stderr)
        fw = list(files_with)
        every_fw = max(1, len(fw)//20)
        for jdx, fp in enumerate(fw, 1):
            try:
                f, mm = mmap_bytes(fp)
            except Exception:
                continue
            nlimit = len(mm)
            if max_bytes is not None:
                nlimit = min(nlimit, max_bytes - (max_bytes % 4))
            for off, tok in chunk4_iter(mm, limit=nlimit, stride=stride):
                if tok == anchor_tok:
                    occurrences.append((fp, off))
            mm.close(); f.close()
            if progress and (jdx % every_fw == 0 or jdx == len(fw)):
                print(f"[anchor] anchor={hex4(anchor_tok)}: scanned {jdx}/{len(fw)} files, occ={len(occurrences)}", file=sys.stderr)

        # If too few files, skip
        occ_files = {fp for fp, _ in occurrences}
        if len(occ_files) < min_files:
            continue

        # Grow right
        pattern = [hex4(anchor_tok)]
        active = occurrences[:]  # list of (fp, off)
        step = 1
        if progress:
            print(f"[anchor] anchor={hex4(anchor_tok)}: growing right (start occurrences={len(active)})", file=sys.stderr)
        while step < max_grow_tokens:
            # For all active occurrences, try to read next token at off + 4*step
            next_tokens_by_file = {}
            for fp, off in active:
                try:
                    f, mm = mmap_bytes(fp)
                except Exception:
                    continue
                pos = off + 4*step
                if max_bytes is not None and pos+4 > max_bytes:
                    mm.close(); f.close()
                    continue
                if pos+4 <= len(mm):
                    next_tok = bytes(mm[pos:pos+4])
                    next_tokens_by_file.setdefault(next_tok, set()).add(fp)
                mm.close(); f.close()

            if not next_tokens_by_file:
                break

            # Majority by distinct file support
            cand_tok, cand_support_files = max(
                next_tokens_by_file.items(), key=lambda kv: len(kv[1])
            )
            support_ratio = len(cand_support_files) / len(occ_files)

            if support_ratio >= min_support and len(cand_support_files) >= min_files:
                # lock this token
                pattern.append(hex4(cand_tok))
                # reduce active occurrences to those files supporting the majority next token
                occ_files = cand_support_files
                active = [(fp, off) for fp, off in active if fp in occ_files]
            else:
                # insert wildcard and keep everyone (unless so few files remain that we should stop)
                pattern.append(wildcard())

            # Prune if we’ve fallen below min_files of participating files
            if len(occ_files) < min_files and pattern[-1] == wildcard():
                break

            step += 1
            if progress and step % 128 == 0:
                print(f"[anchor] anchor={hex4(anchor_tok)}: grown {step} tokens, participants={len(occ_files)}", file=sys.stderr)

        # Optional: left growth (disabled by default, can add symmetric logic)
        patterns.append({
            "mode": "anchor_growth",
            "anchor": hex4(anchor_tok),
            "files_with_anchor": len(files_with),
            "min_support": min_support,
            "min_files": min_files,
            "pattern_tokens": pattern
        })
        if progress:
            print(f"[anchor] done anchor={hex4(anchor_tok)} (length={len(pattern)} tokens)", file=sys.stderr)

    return patterns

def main():
    ap = argparse.ArgumentParser(description="Pattern miner for .rws/.dff PS3 preinstanced files (4-byte tokens, wildcards where variance).")
    ap.add_argument("roots", nargs="+", help="Root folder(s)")
    ap.add_argument("--exts", default=",".join(sorted(TARGET_EXTS)), help="Comma-separated endings")
    ap.add_argument("--max-bytes", type=int, default=None, help="Only scan first N bytes per file (rounded down to /4).")
    ap.add_argument("--stride", type=int, default=4, help="Tokenization stride (default 4).")
    ap.add_argument("--min-support", type=float, default=0.8, help="Consensus threshold (0..1). Default 0.8")
    ap.add_argument("--min-files", type=int, default=20, help="Minimum files required to report a pattern. Default 20")
    ap.add_argument("--anchor-topk", type=int, default=20, help="Try top-K most common 4-byte tokens as anchors. Default 20")
    ap.add_argument("--max-grow", type=int, default=8192, help="Max growth length (tokens) for anchor patterns. Default 8192")
    ap.add_argument("--topk-per-size", type=int, default=1, help="No-op (kept for symmetry).")
    ap.add_argument("--json-out", type=str, default=None, help="Write results JSON")
    ap.add_argument("--no-progress", action="store_true", help="Disable progress output")
    ap.add_argument("--no-consensus", action="store_true", help="Disable consensus-by-size pass")
    ap.add_argument("--no-anchor", action="store_true", help="Disable anchor-growth pass")
    args = ap.parse_args()

    exts = {"." + e.lstrip(".").lower() for e in args.exts.split(",") if e.strip()}
    files = load_files(args.roots, exts, progress=(not args.no_progress))
    if not files:
        print("No target files found.")
        return

    all_results = []

    if not args.no_consensus:
        if not args.no_progress:
            print("[pass] starting consensus-by-size", file=sys.stderr)
        res1 = consensus_by_size(
            files=files,
            max_bytes=args.max_bytes,
            stride=args.stride,
            min_support=args.min_support,
            min_files=args.min_files,
            topk_per_size=args.topk_per_size,
            progress=(not args.no_progress)
        )
        for r in res1:
            print(f"\n== CONSENSUS (size={r['size_bytes']} bytes, files={r['files_in_group']}, "
                  f"support>={r['min_support']}, coverage={r['coverage']}) ==")
            # Print first 64 tokens to keep console readable
            preview = r["pattern_tokens"][:64]
            print(" ".join(preview) + (" ..." if len(r['pattern_tokens']) > 64 else ""))
        all_results.extend(res1)

    if not args.no_anchor:
        if not args.no_progress:
            print("[pass] starting anchor-growth", file=sys.stderr)
        res2 = anchor_growth(
            files=files,
            max_bytes=args.max_bytes,
            stride=args.stride,
            min_files=args.min_files,
            min_support=args.min_support,
            anchor_topk=args.anchor_topk,
            max_grow_tokens=args.max_grow,
            progress=(not args.no_progress)
        )
        for r in res2:
            print(f"\n== ANCHOR '{r['anchor']}' (files_with={r['files_with_anchor']}, "
                  f"support>={r['min_support']}, min_files={r['min_files']}) ==")
            # Show first 40 tokens
            preview = r["pattern_tokens"][:40]
            print(" ".join(preview) + (" ..." if len(r['pattern_tokens']) > 40 else ""))
        all_results.extend(res2)

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\n[OK] Wrote JSON to {args.json_out}")

if __name__ == "__main__":
    main()
