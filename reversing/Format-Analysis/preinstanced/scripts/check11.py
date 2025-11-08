"""
Inspect pairing between pre-texture marker and TLFD chunks.

Usage: python check11.py <file> [--window BYTES]

Notes:
- Recognises both 0x14 and 0x18 header-size variants of the marker.
- Uses nearest-preceding pairing instead of strict global ordering.
- Optional locality window can be enforced via --window (bytes).
"""

import sys, mmap, os, re, argparse
from bisect import bisect_left

# Constants
TLFD = b'TLFD'  # 0x54 0x4C 0x46 0x44

# 02 11 01 00  02 00 00 00  (len=0x14|0x18)  2D 00 02 1C
MARK_PRETEX_RE = re.compile(
    b"\x02\x11\x01\x00\x02\x00\x00\x00(?:\x14|\x18)\x00\x00\x00\x2D\x00\x02\x1C"
)


def find_all_regex(data, regex: re.Pattern) -> list[int]:
    """Return all match start offsets of regex in data without copying.

    Accepts bytes-like inputs (bytes, bytearray, mmap, memoryview).
    """
    return [m.start() for m in regex.finditer(data)]


def find_all_bytes(data, needle: bytes) -> list[int]:
    """Return all offsets of 'needle' using a bytes-like .find loop without copying.

    Works with objects that implement .find (bytes, bytearray, mmap). If not available
    (e.g., memoryview), falls back to regex scanning without materializing a full copy.
    """
    out: list[int] = []
    i = 0
    finder = getattr(data, "find", None)
    if callable(finder):
        while True:
            j = finder(needle, i)
            if j < 0:
                break
            out.append(j)
            i = j + 1
        return out

    # Fallback: regex scan over bytes-like object
    pat = re.compile(re.escape(needle))
    for m in pat.finditer(data):
        out.append(m.start())
    return out


def nearest_preceding(sorted_offsets: list[int], x: int) -> int | None:
    """Return the offset <= x that is nearest and strictly preceding x, else None."""
    if not sorted_offsets:
        return None
    # bisect_left gives index where x would be inserted to keep order
    idx = bisect_left(sorted_offsets, x) - 1
    return sorted_offsets[idx] if idx >= 0 else None


def main(path: str, window: int | None = None) -> int:
    size = os.path.getsize(path)
    with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
        mv = memoryview(m)
        try:
            # Offsets (no copies; release mv before mmap closes)
            mark_offsets = find_all_regex(mv, MARK_PRETEX_RE)
            # Use mmap's .find directly for efficiency
            tlfd_offsets = find_all_bytes(m, TLFD)
        finally:
            # Important on Windows to avoid BufferError when closing mmap
            mv.release()

    mark_offsets.sort()
    tlfd_offsets.sort()

    print(f"File: {path} ({size:,} bytes)")
    print(
        f" MARK count={len(mark_offsets)}  offsets={mark_offsets[:10]}"
        + (" ..." if len(mark_offsets) > 10 else "")
    )
    print(
        f" TLFD count={len(tlfd_offsets)}  offsets={tlfd_offsets[:10]}"
        + (" ..." if len(tlfd_offsets) > 10 else "")
    )

    if not tlfd_offsets:
        print(" No TLFD chunks found. Nothing to validate.")
        return 0

    pairing_fail_points: list[int] = []
    for i, t in enumerate(tlfd_offsets):
        prev = nearest_preceding(mark_offsets, t)
        if window is not None and prev is not None:
            if t - prev > window:
                prev = None

        verdict = "OK" if prev is not None else "NO_PRECEDING_MARK"
        if prev is None:
            pairing_fail_points.append(t)
        print(
            f"  TLFD[{i}] @ {t}: {verdict}  (nearest prev mark: {prev if prev is not None else 'None'})"
        )

    # Summarise: Hard FAIL only if none of the TLFDs has a preceding marker
    if len(pairing_fail_points) == len(tlfd_offsets):
        print(
            f"FAIL: No preceding pre-texture marker for any TLFD (count={len(tlfd_offsets)})."
        )
        return 2
    elif pairing_fail_points:
        example = pairing_fail_points[0]
        print(
            f"WARN: {len(pairing_fail_points)} TLFD(s) without a preceding marker"
            + (f" within window={window} bytes" if window is not None else "")
            + f"; example @ {example}"
        )
        return 1
    else:
        print("PASS: Every TLFD has a preceding pre-texture marker." + (f" (window={window} bytes)" if window is not None else ""))
        return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Inspect pre-texture marker vs TLFD pairing")
    ap.add_argument("file", help="Path to the file to inspect")
    ap.add_argument(
        "--window",
        type=int,
        default=None,
        help="Optional locality window in bytes; require marker to be within this distance",
    )
    args = ap.parse_args()
    sys.exit(main(args.file, args.window))
