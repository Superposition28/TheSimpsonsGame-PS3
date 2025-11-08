#!/usr/bin/env python3
"""
Scan a directory recursively for files ending with:
  - .rws.ps3.preinstanced
  - .dff.ps3.preinstanced

For each file, confirm it starts (at offset 0 unless --offset is used) with the long SOF
pattern below. Token "**" means a wildcard byte (any value is accepted at that position).

Long SOF pattern (spaces/newlines ignored, "**" = any byte):

10 00 00 00 ** ** 00 00 2D 00 02 1C 01 00 00 00
0C 00 00 00 2D 00 02 1C 01 00 00 00 00 00 00 00
00 00 00 00 0E 00 00 00 ** ** 00 00 2D 00 02 1C
01 00 00 00 ** 00 00 00 2D 00 02 1C ** 00 00 00
00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00
00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00
00 00 80 3F ** ** ** ** ** ** ** ** ** ** ** **
FF FF FF FF 00 00 00 00 00 00 80 3F 00 00 00 00
00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00
00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 ** 00 ** ** 00 00 00 00 ** 00 ** **
** 00 00 00 ** 00 ** ** ** 00 ** ** ** ** 00 00
** 00 00 00 ** 00 ** ** ** ** ** ** ** ** ** **
** ** ** 00 00 00 00 00 ** ** ** ** 00 00 00 00

Exit code is non-zero if any matching file fails the check.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Iterable, List, Optional


TARGET_SUFFIXES = (
	".rws.ps3.preinstanced",
	".dff.ps3.preinstanced",
)

# Long SOF pattern with wildcards (** or ?? tokens are single-byte wildcards)
LONG_SOF_PATTERN = (
	"10 00 00 00 ** ** ** ** 2D 00 02 1C 01 00 00 00 0C 00 00 00 2D 00 02 1C ** ** ** ** 00 00 00 00 "
	"00 00 00 00 0E 00 00 00 ** ** ** ** 2D 00 02 1C 01 00 00 00 ** ** ** ** 2D 00 02 1C ** ** ** ** "
	"00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 "
	"00 00 80 3F ** ** ** ** ** ** ** ** ** ** ** ** FF FF FF FF 00 00 00 00 " ## after this about 100 of 5533 have a block of unknown binary bytes from here to the texture data
	">> " ## skip until next pattern
	#"02 11 01 00 02 00 00 00 ** 00 00 00 2D 00 02 1C" # pattern before texture string names
	"16 EA 00 00 05 00 00 00 2D 00 02 1C 01 00 00 00 00 " ## pattern at EOF

)




@dataclass
class CheckResult:
	path: str
	ok: bool
	reason: str = ""
	head_hex: str = ""


def iter_target_files(root: str) -> Iterable[str]:
	"""Yield file paths under root that end with the target suffixes (case-insensitive)."""
	root = os.path.abspath(root)
	for dirpath, _dirnames, filenames in os.walk(root):
		for name in filenames:
			lower = name.lower()
			if lower.endswith(TARGET_SUFFIXES):
				yield os.path.join(dirpath, name)


def read_prefix(path: str, n: int) -> bytes:
	with open(path, "rb") as f:
		return f.read(n)


def to_hex(b: bytes) -> str:
	return " ".join(f"{x:02X}" for x in b)


def parse_wildcard_pattern_to_bytes_and_mask(pat: str) -> tuple[bytes, bytes]:
	"""Parse a wildcard hex pattern into (pattern_bytes, mask_bytes).

	- Accepts tokens separated by whitespace
	- Wildcards: "**" or "??" (match any byte) → mask 0x00 at that position
	- Hex byte tokens: two hex digits (e.g., "2D") → mask 0xFF and corresponding byte value
	- Raises ValueError on any invalid token
	"""
	p: List[int] = []
	m: List[int] = []
	for raw_tok in pat.replace("\n", " ").split():
		tok = raw_tok.strip()
		if not tok:
			continue
		# ">>" is handled by higher-level parser; reject it here to avoid silent misuse
		if tok == ">>":
			raise ValueError("'>>' skip token must be handled by parse_pattern_with_skips()")
		if tok in ("**", "??"):
			p.append(0x00)
			m.append(0x00)
			continue
		if len(tok) != 2:
			raise ValueError(f"Invalid token length in pattern: {tok!r}")
		try:
			val = int(tok, 16)
		except ValueError as e:
			raise ValueError(f"Invalid hex token in pattern: {tok!r}") from e
		p.append(val)
		m.append(0xFF)
	if not p:
		raise ValueError("Pattern parsed to empty list")
	return bytes(p), bytes(m)


def parse_pattern_with_skips(pat: str) -> List[tuple[bytes, bytes]]:
	"""Parse a pattern that may contain the skip token '>>' into a list of segments.

	Each segment is a (pattern_bytes, mask_bytes) tuple as produced by
	parse_wildcard_pattern_to_bytes_and_mask(). The semantics of '>>' are:
	- After matching one segment, skip any number of bytes until the next segment matches.
	- Multiple '>>' tokens are supported. Empty segments are ignored.
	"""
	# Tokenize once, split into segments on '>>'
	tokens = [t.strip() for t in pat.replace("\n", " ").split() if t.strip()]
	segments_tokens: List[List[str]] = []
	current: List[str] = []
	for tok in tokens:
		if tok == ">>":
			if current:
				segments_tokens.append(current)
				current = []
			continue
		current.append(tok)
	if current:
		segments_tokens.append(current)

	if not segments_tokens:
		raise ValueError("Pattern parsed to zero segments")

	segments: List[tuple[bytes, bytes]] = []
	for seg in segments_tokens:
		seg_str = " ".join(seg)
		p, m = parse_wildcard_pattern_to_bytes_and_mask(seg_str)
		if len(p) != len(m) or len(p) == 0:
			raise ValueError("Invalid segment in pattern")
		segments.append((p, m))
	return segments


def find_masked(data: bytes, patt: bytes, mask: bytes, start: int) -> int:
	"""Search for patt/mask in data at or after 'start'. Return index or -1 if not found."""
	need = len(patt)
	limit = len(data) - need
	if need == 0:
		return start
	for i in range(max(0, start), max(-1, limit) + 1):
		seg = data[i:i + need]
		# Fast path: check first byte with mask before full compare
		if (seg[0] & mask[0]) != (patt[0] & mask[0]):
			continue
		match = True
		for db, pb, mb in zip(seg, patt, mask):
			if (db & mb) != (pb & mb):
				match = False
				break
		if match:
			return i
	return -1


def match_prefix_masked(data: bytes, patt: bytes, mask: bytes, offset: int = 0) -> Optional[str]:
	"""Match data[offset:offset+len(patt)] against patt using mask bytes.

	For each i: (data[offset+i] & mask[i]) must equal (patt[i] & mask[i]).
	Returns None if it matches, otherwise a short reason string.
	"""
	if len(patt) != len(mask):
		return "internal error: pattern/mask length mismatch"
	need = len(patt)
	have = len(data)
	if have < offset + need:
		return f"too short: have {have}B, need at least {offset + need}B"
	seg = data[offset:offset + need]
	for i, (db, pb, mb) in enumerate(zip(seg, patt, mask)):
		if (db & mb) != (pb & mb):
			return f"mismatch @+0x{i:02X}: expected {(pb & mb):02X} mask {mb:02X}, got {(db & mb):02X}"
	return None


def match_segments_with_skips(data: bytes, segments: List[tuple[bytes, bytes]], offset: int = 0) -> Optional[str]:
	"""Match the first segment at 'offset', then for each subsequent segment, find it
	anywhere after the previous matched segment (skip any bytes in between).

	Returns None if all segments are matched; otherwise a reason string.
	"""
	if not segments:
		return "internal error: no segments"

	# First segment must match at the given offset
	first_p, first_m = segments[0]
	reason = match_prefix_masked(data, first_p, first_m, offset)
	if reason is not None:
		return reason

	# Subsequent segments: search forward after end of previous match
	search_start = offset + len(first_p)
	for idx, (p, m) in enumerate(segments[1:], start=2):
		found = find_masked(data, p, m, search_start)
		if found == -1:
			return f"segment {idx} not found after +0x{search_start:X}"
		search_start = found + len(p)
	return None


def check_file(path: str, segments: List[tuple[bytes, bytes]], offset: int) -> CheckResult:
	try:
		with open(path, "rb") as f:
			data = f.read()
	except Exception as e:
		return CheckResult(path=path, ok=False, reason=f"read error: {e}")

	# For display, capture the initial bytes needed for the first segment check
	first_len = len(segments[0][0]) if segments else 0
	head_len = min(len(data), offset + first_len)
	head_hex = to_hex(data[:head_len])

	reason = match_segments_with_skips(data, segments, offset)
	ok = reason is None
	return CheckResult(path=path, ok=ok, reason=(reason or ""), head_hex=head_hex)


def parse_args(argv: List[str]) -> argparse.Namespace:
	p = argparse.ArgumentParser(description="Validate ONLY a long SOF pattern (with wildcards) at file start for preinstanced PS3 files.")
	p.add_argument(
		"path",
		nargs="?",
		default=".",
		help="Root directory to scan (defaults to current directory)",
	)
	p.add_argument(
		"--quiet",
		"-q",
		action="store_true",
		help="Only print the summary (suppress per-file lines)",
	)
	p.add_argument(
		"--show-bytes",
		action="store_true",
		help="Include the head bytes read for each file in output",
	)
	p.add_argument(
		"--offset",
		type=int,
		default=0,
		help="Byte offset at which to match the pattern (default: 0)",
	)
	return p.parse_args(argv)


def main(argv: List[str]) -> int:
	args = parse_args(argv)
	root = args.path
	files = list(iter_target_files(root))

	total = len(files)
	failures = 0
	pass_lines = []
	fail_lines = []

	# Prepare pattern segments and masks (pure hex under the hood)
	try:
		segments = parse_pattern_with_skips(LONG_SOF_PATTERN)
	except Exception as e:
		print(f"Pattern parse error: {e}")
		return 3

	if not args.quiet:
		print(f"Scanning: {os.path.abspath(root)}")
		print(f"Target suffixes: {', '.join(TARGET_SUFFIXES)}")
		seg_lens = ", ".join(str(len(p)) for (p, _m) in segments)
		print(f"Pattern segments (bytes): [{seg_lens}] @ offset {args.offset} with '>>' gaps allowed")
		print(f"Found {total} file(s)\n")

	for idx, path in enumerate(files, 1):
		res = check_file(path, segments, args.offset)
		if res.ok:
			line = None
			if not args.quiet:
				line = f"PASS - {path}"
				if args.show_bytes:
					line += f"  |  HEAD[{len(res.head_hex.split())}]: {res.head_hex}"
			if line is not None:
				pass_lines.append(line)
		else:
			failures += 1
			line = f"FAIL - {path} :: {res.reason or 'pattern mismatch'}"
			if args.show_bytes and res.head_hex:
				line += f"  |  HEAD[{len(res.head_hex.split())}]: {res.head_hex}"
			fail_lines.append(line)
			print(line)

		# Live progress counter (only when not quiet)
		if not args.quiet:
			progress = f"\rScanned {idx}/{total} files"
			sys.stdout.write(progress)
			sys.stdout.flush()

	# Summary
	overall_status = "OK" if failures == 0 else "ERROR"

	print()
	print("Summary:")
	print(f"  Long SOF pattern: {overall_status} - {total - failures} pass, {failures} fail, {total} total")

	return 0 if failures == 0 else 2


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))

