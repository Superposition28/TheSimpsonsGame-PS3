#!/usr/bin/env python3
import argparse
import json
import mmap
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

TARGET_EXTS = {".rws.ps3.preinstanced", ".dff.ps3.preinstanced"}

def is_target(p: Path, exts):
    n = p.name.lower()
    return any(n.endswith(e) for e in exts)

def hex2(b: int) -> str:
    return f"{b:02x}"

def wildcard_byte() -> str:
    return "??"

def chunk_bytes_to_4byte_strings(byte_tokens):
    """byte_tokens: list[str] each either '??' or 2-hex; return list[str] of 8 chars per 4 bytes."""
    out = []
    for i in range(0, len(byte_tokens), 4):
        quad = byte_tokens[i:i+4]
        if len(quad) < 4:
            quad += [wildcard_byte()] * (4 - len(quad))
        out.append("".join(quad))
    return out

def load_files(roots, exts, progress=True):
    files = []
    start = time.time()
    for r in roots:
        p = Path(r)
        if p.is_file():
            if is_target(p, exts):
                files.append(p)
        else:
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

def aligned(n, k=4):
    return n - (n % k)

def build_per_file_byte_consensus(files, max_bytes, min_support, min_bytes, progress=True):
    """
    Byte-wise consensus for groups of same (truncated) size.
    Returns list of dicts; pattern emitted as 4-byte strings with per-byte '??'.
    """
    groups = defaultdict(list)
    for fp in files:
        size = fp.stat().st_size
        if max_bytes is not None:
            size = min(size, max_bytes)
        size = aligned(size, 4)
        if size <= 0:
            continue
        groups[size].append(fp)

    results = []
    for size, fps in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if len(fps) < max(2, min_bytes):  # “min_bytes” here is min files; kept name parity with CLI
            continue

        byte_counters = [Counter() for _ in range(size)]
        participating = 0
        if progress:
            print(f"[consensus-bytes] size={size} bytes, files={len(fps)} -> counting", file=sys.stderr)

        every = max(1, len(fps)//20)
        for idx, fp in enumerate(fps, 1):
            try:
                f, mm = mmap_bytes(fp)
            except Exception:
                continue
            participating += 1
            n = min(len(mm), size)
            b = mm[:n]
            for i in range(n):
                byte_counters[i][b[i]] += 1
            mm.close(); f.close()
            if progress and (idx % every == 0 or idx == len(fps)):
                print(f"[consensus-bytes] processed {idx}/{len(fps)}", file=sys.stderr)

        if participating < max(2, min_bytes):
            continue

        token_bytes = []
        concrete = 0
        for cnt in byte_counters:
            if not cnt:
                token_bytes.append(wildcard_byte())
                continue
            val, c = cnt.most_common(1)[0]
            support = c / participating
            if support >= min_support:
                token_bytes.append(hex2(val))
                concrete += 1
            else:
                token_bytes.append(wildcard_byte())

        coverage = concrete / max(1, len(token_bytes))
        pattern_tokens = chunk_bytes_to_4byte_strings(token_bytes)
        results.append({
            "mode": "consensus_by_bytes",
            "size_bytes": size,
            "files_in_group": participating,
            "min_support": min_support,
            "coverage": round(coverage, 4),
            "pattern_tokens": pattern_tokens
        })
        if progress:
            print(f"[consensus-bytes] done size={size} (coverage={coverage:.2%})", file=sys.stderr)
    return results

def find_anchors(files, max_bytes, topk, progress=True):
    """
    Returns:
      - global_rank: list[(4b_token, support_files)]
      - per_file_rank: dict[file_path] -> Counter(4b_token -> occurrences)
    """
    token_files = defaultdict(set)   # 4-byte token -> set(files)
    per_file_occ = {}                # file -> Counter(token -> count)

    if progress:
        print(f"[anchors] scanning {len(files)} file(s)", file=sys.stderr)

    every = max(1, len(files)//20)
    for idx, fp in enumerate(files, 1):
        try:
            f, mm = mmap_bytes(fp)
        except Exception:
            continue
        nlimit = len(mm) if max_bytes is None else min(len(mm), aligned(max_bytes, 4))
        cnt = Counter()
        seen = set()
        end = aligned(nlimit, 4)
        # count 4-byte *occurrences* for per-file ranking
        for off in range(0, end, 4):
            tok = bytes(mm[off:off+4])
            cnt[tok] += 1
            seen.add(tok)
        per_file_occ[fp] = cnt
        for t in seen:
            token_files[t].add(fp)
        mm.close(); f.close()
        if progress and (idx % every == 0 or idx == len(files)):
            print(f"[anchors] processed {idx}/{len(files)}", file=sys.stderr)

    global_rank = sorted(token_files.items(), key=lambda kv: -len(kv[1]))[:topk]
    return global_rank, per_file_occ

def grow_from_anchor_bytewise(anchor_tok, files, files_with_anchor, max_bytes, min_support, min_files, pad_cut, progress=True, single_file_bias=False):
    """
    Byte-wise right growth from a 4-byte anchor.
    - support by distinct files (multi-file) or by occurrences (single-file mode).
    - stops when a padding run of zeros would continue (>= pad_cut) with enough support.
    Returns dict with pattern_tokens (4-byte strings with per-byte '??').
    """
    # Cache mmaps for the subset of files containing the anchor for this pass
    mm_cache = {}
    def get_mm(fp):
        if fp in mm_cache:
            return mm_cache[fp]
        f = open(fp, "rb")
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        mm_cache[fp] = (f, mm)
        return mm_cache[fp]

    try:
        # Locate all (file, offset) occurrences of the 4-byte anchor
        occurrences = []
        fw = list(files_with_anchor)
        every = max(1, len(fw)//20) if fw else 1
        for jdx, fp in enumerate(fw, 1):
            try:
                f, mm = get_mm(fp)
            except Exception:
                continue
            nlimit = len(mm) if max_bytes is None else min(len(mm), aligned(max_bytes, 4))
            end = aligned(nlimit, 4)
            for off in range(0, end, 4):
                if bytes(mm[off:off+4]) == anchor_tok:
                    occurrences.append((fp, off))
            if progress and (jdx % every == 0 or jdx == len(fw)):
                print(f"[grow] anchor {anchor_tok.hex()}: located {len(occurrences)} occurrences in {jdx}/{len(fw)} files", file=sys.stderr)

        occ_files = {fp for fp, _ in occurrences}
        if not occurrences:
            return None
        if len(files) > 1 and len(occ_files) < min_files:
            return None

        # Pattern starts as the 4 bytes of the anchor (all concrete)
        pattern_bytes = [hex2(b) for b in anchor_tok]
        step = 4  # number of bytes currently in pattern
        consecutive_zeroes = 0

        # Active occurrences are precise (file, off)
        active = occurrences[:]

        while True:
            # Gather next byte candidates from all active occurrences
            next_byte_support_files = defaultdict(set)   # byte -> set(files)
            next_byte_occ = defaultdict(list)            # byte -> list[(fp, off)]
            next_byte_count = Counter()                  # byte -> occurrences (for single-file mode)

            for fp, off in active:
                try:
                    f, mm = get_mm(fp)
                except Exception:
                    continue
                pos = off + step
                if max_bytes is not None and pos + 1 > max_bytes:
                    continue
                if pos < len(mm):
                    b = mm[pos]
                    next_byte_support_files[b].add(fp)
                    next_byte_occ[b].append((fp, off))
                    next_byte_count[b] += 1

            if not next_byte_support_files:
                break  # nothing more to grow

            # Choose candidate by support
            if single_file_bias:
                cand_byte, _ = next_byte_count.most_common(1)[0]
                denom = sum(next_byte_count.values())
                support_ratio = next_byte_count[cand_byte] / max(1, denom)
                min_ok = 1  # in single-file, occurrences >=1
                enough_support = (support_ratio >= min_support) and (next_byte_count[cand_byte] >= min_ok)
            else:
                cand_byte, cand_files = max(next_byte_support_files.items(), key=lambda kv: len(kv[1]))
                support_ratio = len(cand_files) / max(1, len(occ_files))
                enough_support = (support_ratio >= min_support) and (len(cand_files) >= min_files)

            # Padding-aware cut: if chosen byte is 0x00, and continuing would make a long run of zeros,
            # consider stopping instead of bloating the pattern with padding.
            would_be_zeros = (cand_byte == 0x00)
            zero_run_len = consecutive_zeroes + (1 if would_be_zeros else 0)

            if would_be_zeros and zero_run_len >= pad_cut:
                # stop before absorbing the padding
                break

            if enough_support:
                # Lock concrete byte
                pattern_bytes.append(hex2(cand_byte))
                step += 1
                if cand_byte == 0x00:
                    consecutive_zeroes += 1
                else:
                    consecutive_zeroes = 0

                # Narrow active set precisely to occurrences that matched this byte
                if single_file_bias:
                    active = next_byte_occ[cand_byte]
                    occ_files = set(fp for fp, _ in active)
                else:
                    active = next_byte_occ[cand_byte]
                    occ_files = set(fp for fp, _ in active)

                # If too few files remain (multi-file), stop
                if not single_file_bias and len(occ_files) < min_files:
                    break
            else:
                # Insert wildcard byte and continue (don’t filter active)
                pattern_bytes.append(wildcard_byte())
                step += 1
                consecutive_zeroes = 0  # treat wildcard as break in zero run

        # Emit as 4-byte strings
        pattern_tokens = chunk_bytes_to_4byte_strings(pattern_bytes)
        return {
            "mode": "anchor_growth_bytewise",
            "anchor": anchor_tok.hex(),
            "files_with_anchor": len(occ_files),
            "min_support": min_support,
            "min_files": min_files,
            "pad_cut": pad_cut,
            "pattern_tokens": pattern_tokens
        }
    finally:
        # close caches
        for f, mm in mm_cache.values():
            try: mm.close()
            except: pass
            try: f.close()
            except: pass

def main():
    ap = argparse.ArgumentParser(description="Byte-wise pattern miner with per-byte wildcards and padding-aware growth.")
    ap.add_argument("roots", nargs="+", help="Root file(s)/folder(s)")
    ap.add_argument("--exts", default=",".join(sorted(TARGET_EXTS)), help="Comma-separated endings to include")
    ap.add_argument("--max-bytes", type=int, default=None, help="Only scan first N bytes per file.")
    ap.add_argument("--min-support", type=float, default=0.8, help="Consensus/support threshold (0..1)")
    ap.add_argument("--min-files", type=int, default=2, help="Min files for multi-file anchor acceptance")
    ap.add_argument("--anchor-topk", type=int, default=20, help="Top-K anchors to try (by file support)")
    ap.add_argument("--pad-cut", type=int, default=32, help="Cut pattern if a zero run would reach this many bytes")
    ap.add_argument("--json-out", type=str, default=None, help="Write results JSON")
    ap.add_argument("--no-progress", action="store_true", help="Disable progress output")
    ap.add_argument("--no-consensus", action="store_true", help="Disable consensus-bytes pass")
    ap.add_argument("--no-anchor", action="store_true", help="Disable anchor-growth pass")
    args = ap.parse_args()

    exts = {"." + e.lstrip(".").lower() for e in args.exts.split(",") if e.strip()}
    files = load_files(args.roots, exts, progress=(not args.no_progress))
    if not files:
        print("No target files found.")
        return

    # Detect whether we’re effectively in single-file mode
    single_file_mode = (len(files) == 1)

    all_results = {
        "per_file_patterns": {},
        "global_patterns": []
    }

    # 1) Byte-wise consensus by same-size groups (multi-file only; still okay with single, but less useful)
    if not args.no_consensus:
        if not args.no_progress:
            print("[pass] starting consensus-bytes", file=sys.stderr)
        res1 = build_per_file_byte_consensus(
            files=files,
            max_bytes=args.max_bytes,
            min_support=args.min_support,
            min_bytes=args.min_files,
            progress=(not args.no_progress)
        )
        # Print previews for readability
        for r in res1:
            print(f"\n== GLOBAL CONSENSUS (size={r['size_bytes']} bytes, files={r['files_in_group']}, "
                  f"support>={r['min_support']}, coverage={r['coverage']}) ==")
            preview = r["pattern_tokens"][:64]
            print(" ".join(preview) + (" ..." if len(r['pattern_tokens']) > 64 else ""))
        all_results["global_patterns"].extend(res1)

    # 2) Anchor growth (byte-wise)
    if not args.no_anchor:
        if not args.no_progress:
            print("[pass] starting anchor-growth (byte-wise)", file=sys.stderr)

        global_rank, per_file_rank = find_anchors(files, args.max_bytes, args.anchor_topk, progress=(not args.no_progress))

        # Global anchors (multi-file; for single file we’ll use per-file anchors)
        if not single_file_mode:
            for anchor_tok, files_with in global_rank:
                pat = grow_from_anchor_bytewise(
                    anchor_tok=anchor_tok,
                    files=files,
                    files_with_anchor=files_with,
                    max_bytes=args.max_bytes,
                    min_support=args.min_support,
                    min_files=args.min_files,
                    pad_cut=args.pad_cut,
                    progress=(not args.no_progress),
                    single_file_bias=False
                )
                if pat:
                    # Preview
                    print(f"\n== GLOBAL ANCHOR '{pat['anchor']}' (files_with={pat['files_with_anchor']}, "
                          f"support>={pat['min_support']}, min_files={pat['min_files']}) ==")
                    preview = pat["pattern_tokens"][:40]
                    print(" ".join(preview) + (" ..." if len(pat['pattern_tokens']) > 40 else ""))
                    all_results["global_patterns"].append(pat)

        # Per-file anchors (works for single file and many files; ranked by within-file occurrences)
        for fp, counter in per_file_rank.items():
            # pick top anchors present in this file
            topk_here = [tok for tok, _ in counter.most_common(args.anchor_topk)]
            file_patterns = []
            for tok in topk_here:
                # Supply only this file as “files_with_anchor” for single-file-like growth,
                # but keep multi-file support logic disabled (use occurrence support).
                pat = grow_from_anchor_bytewise(
                    anchor_tok=tok,
                    files=[fp],
                    files_with_anchor={fp},
                    max_bytes=args.max_bytes,
                    min_support=args.min_support,
                    min_files=1,
                    pad_cut=args.pad_cut,
                    progress=False,
                    single_file_bias=True
                )
                if pat:
                    file_patterns.append(pat)
            # Print preview
            if file_patterns:
                print(f"\n== PER-FILE PATTERNS for {fp} ==")
                for pat in file_patterns[:3]:  # show a few
                    preview = pat["pattern_tokens"][:24]
                    print(f"  - anchor {pat['anchor']} : " + " ".join(preview) + (" ..." if len(pat['pattern_tokens']) > 24 else ""))
            all_results["per_file_patterns"][str(fp)] = file_patterns

    # JSON
    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\n[OK] Wrote JSON to {args.json_out}")

if __name__ == "__main__":
    main()
