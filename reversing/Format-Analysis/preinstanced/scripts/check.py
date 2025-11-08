#!/usr/bin/env python3
"""
Scan a directory recursively for files ending with:
  - .rws.ps3.preinstanced
  - .dff.ps3.preinstanced

For each file, confirm it starts with the strict SOF signature:

Offset 0x00: 10 00 00 00
Offset 0x04: <size> (any 4 bytes)
Offset 0x08: 2D 00 02 1C
Offset 0x0C: 01 00 00 00

Strict regex: ^ 10 00 00 00 .. .. .. .. 2D 00 02 1C 01 00 00 00

Exit code is non-zero if any matching file fails the check.

Additionally validates an EOF sentinel at the end of file:
EOF_SENTINEL = 16 EA 00 00 05 00 00 00 2D 00 02 1C 01 00 00 00 00

Also scans for RenderWare markers:

Texture dictionary / "texture list"
	- ID: 13 EA 00 00 (u32 LE = 0x0000EA13)
	- Discriminator inside payload: contains ASCII TLFD (54 4C 46 44)
	- Start: first 13 EA whose payload contains TLFD
	- End (recommended): byte before first mesh section 33 EA 00 00; if no mesh exists, end of the 13 EA section (H+12+size)

Mesh / 3D data block
	- ID: 33 EA 00 00 (u32 LE = 0x0000EA33)
	- Start: on the 33 EA header
	- End (per block): H+12+size; overall 3D region: from first 33 EA to end of last 33 EA
	- Optional internal anchors (heuristics; not required to pass): after chunk header, skip 4 then read FaceDataOff (LE u32), MeshDataSize (LE u32);
		skip 0x14 then read mDataTableCount (BE u32), mDataSubCount (BE u32)
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Tuple


TARGET_SUFFIXES = (
	".rws.ps3.preinstanced",
	".dff.ps3.preinstanced",
)

## SOF
# Constants for the signature
SIG_HEAD = b"\x10\x00\x00\x00"  # 10 00 00 00
SIG_E2 = b"\x2D\x00\x02\x1C"    # 2D 00 02 1C
SIG_AFTER = b"\x01\x00\x00\x00"  # 01 00 00 00
REQUIRED_LEN = 16

# EOF sentinel (17 bytes)
EOF_SENTINEL = b"\x16\xEA\x00\x00\x05\x00\x00\x00\x2D\x00\x02\x1C\x01\x00\x00\x00\x00"
EOF_LEN = len(EOF_SENTINEL)

# RW markers
RW_CHUNK_HEADER_SIZE = 12  # ID(4) + size(4) + version(4)
RW_VERSION_E2 = b"\x2D\x00\x02\x1C"  # common version seen in these files

ID_TEX_LIST = b"\x13\xEA\x00\x00"  # 0x0000EA13
ID_MESH = b"\x33\xEA\x00\x00"      # 0x0000EA33
TLFD = b"TLFD"


@dataclass
class CheckResult:
	path: str
	ok: bool
	# Per-marker outcomes
	sof_ok: bool
	eof_ok: bool
	# Optional reasons for failure (combined when overall fails)
	reason: str = ""
	sof_reason: str = ""
	eof_reason: str = ""
	# Debug hex dumps
	bytes_hex: str = ""   # head 16 bytes
	tail_hex: str = ""    # last EOF_LEN bytes
	# Marker findings (optional; do not affect ok)
	texture_start: Optional[int] = None
	texture_end: Optional[int] = None  # recommended end boundary
	texture_chunk_end: Optional[int] = None  # H+12+size of selected 13EA
	mesh_count: int = 0
	mesh_first: Optional[int] = None
	mesh_last_end: Optional[int] = None
	marker_errors: List[str] = field(default_factory=list)


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


def read_suffix(path: str, n: int) -> bytes:
	with open(path, "rb") as f:
		try:
			f.seek(0, os.SEEK_END)
			size = f.tell()
			if size < n:
				f.seek(0)
				return f.read()
			f.seek(size - n)
			return f.read(n)
		except Exception:
			# Fallback simple read
			data = f.read()
			return data[-n:]


def to_hex(b: bytes) -> str:
	return " ".join(f"{x:02X}" for x in b)


def to_off_hex(x: Optional[int]) -> str:
	return "-" if x is None else f"0x{x:08X}"


def find_rw_chunks(data: bytes, chunk_id: bytes) -> List[Tuple[int, int, int]]:
	"""Find RW chunks with a given 4-byte ID, returning list of (start, size, endExclusive).

	We require:
	- at least 12 bytes available for header
	- version equals RW_VERSION_E2 (to reduce false positives)
	- end within file length
	"""
	res: List[Tuple[int, int, int]] = []
	i = 0
	data_len = len(data)
	while True:
		pos = data.find(chunk_id, i)
		if pos == -1:
			break
		# Header bounds
		if pos + RW_CHUNK_HEADER_SIZE <= data_len:
			size = int.from_bytes(data[pos + 4: pos + 8], "little", signed=False)
			version = data[pos + 8: pos + 12]
			end = pos + RW_CHUNK_HEADER_SIZE + size
			if version == RW_VERSION_E2 and end <= data_len:
				res.append((pos, size, end))
		i = pos + 1
	return res


def check_file(path: str) -> CheckResult:
	# Defaults
	sof_ok = False
	eof_ok = False
	sof_reason = ""
	eof_reason = ""
	head = b""
	tail = b""

	# SOF checks
	try:
		head = read_prefix(path, REQUIRED_LEN)
	except Exception as e:
		sof_reason = f"read error: {e}"
	else:
		if len(head) < REQUIRED_LEN:
			sof_reason = f"too short: {len(head)}B (< {REQUIRED_LEN})"
		else:
			# Validate strict signature
			if head[0:4] != SIG_HEAD:
				sof_reason = f"mismatch @0: expected {to_hex(SIG_HEAD)}, got {to_hex(head[0:4])}"
			elif head[8:12] != SIG_E2:
				sof_reason = f"mismatch @8: expected {to_hex(SIG_E2)}, got {to_hex(head[8:12])}"
			elif head[12:16] != SIG_AFTER:
				sof_reason = f"mismatch @12: expected {to_hex(SIG_AFTER)}, got {to_hex(head[12:16])}"
			else:
				sof_ok = True

	# EOF checks (attempt regardless of SOF result to report per-marker status)
	try:
		tail = read_suffix(path, EOF_LEN)
	except Exception as e:
		eof_reason = f"read tail error: {e}"
	else:
		if len(tail) < EOF_LEN:
			eof_reason = f"too short for EOF: {len(tail)}B tail (< {EOF_LEN})"
		elif tail != EOF_SENTINEL:
			eof_reason = f"EOF mismatch: expected {to_hex(EOF_SENTINEL)}, got {to_hex(tail)}"
		else:
			eof_ok = True

	# Marker scans (do not affect ok unless we later make strict)
	texture_start: Optional[int] = None
	texture_end: Optional[int] = None
	texture_chunk_end: Optional[int] = None
	mesh_count = 0
	mesh_first: Optional[int] = None
	mesh_last_end: Optional[int] = None
	marker_errors: List[str] = []

	try:
		with open(path, "rb") as f:
			data = f.read()
	except Exception as e:
		marker_errors.append(f"marker scan read error: {e}")
	else:
		# Texture list: first 13EA whose payload contains TLFD
		tex_chunks = find_rw_chunks(data, ID_TEX_LIST)
		for (h, size, end) in tex_chunks:
			payload = data[h + RW_CHUNK_HEADER_SIZE:end]
			if TLFD in payload:
				texture_start = h
				texture_chunk_end = end
				break
			else:
				# If TLFD not found in this 13EA payload, continue searching; if none matched we just report not found
				continue

		# Mesh blocks: collect all valid 33EA chunks
		mesh_chunks = find_rw_chunks(data, ID_MESH)
		mesh_count = len(mesh_chunks)
		if mesh_chunks:
			mesh_first = mesh_chunks[0][0]
			mesh_last_end = mesh_chunks[-1][2]

		# Recommended texture_end is byte before first mesh header (exclude preludes)
		if texture_start is not None:
			if mesh_first is not None and mesh_first > texture_start:
				texture_end = mesh_first  # exclusive end boundary; "byte before" is mesh_first-1
			else:
				# No mesh after texture → end at chunk end
				texture_end = texture_chunk_end

		# Light structural validations and heuristics on mesh chunks
		for (h, size, end) in mesh_chunks:
			base = h + RW_CHUNK_HEADER_SIZE
			# need at least 4 + 4 + 4 + 0x14 + 8 bytes inside payload to read anchors safely
			need = 4 + 4 + 4 + 0x14 + 8
			if base + need > end:
				marker_errors.append(f"mesh@{to_off_hex(h)}: too small for anchors (chunkSize={size})")
				continue
			unk0 = int.from_bytes(data[base:base + 4], "little", signed=False)
			face_off = int.from_bytes(data[base + 4:base + 8], "little", signed=False)
			mesh_data_size = int.from_bytes(data[base + 8:base + 12], "little", signed=False)
			p2 = base + 4 + 8 + 0x14
			table_cnt = int.from_bytes(data[p2:p2 + 4], "big", signed=False)
			sub_cnt = int.from_bytes(data[p2 + 4:p2 + 8], "big", signed=False)
			# Sanity checks
			payload_size = size
			if face_off > payload_size:
				marker_errors.append(f"mesh@{to_off_hex(h)}: FaceDataOff {face_off} > payload {payload_size}")
			if mesh_data_size > payload_size:
				marker_errors.append(f"mesh@{to_off_hex(h)}: MeshDataSize {mesh_data_size} > payload {payload_size}")
			# Optional heuristic: BF BF BF BF appears often
			if b"\xBF\xBF\xBF\xBF" in data[base:end]:
				pass  # marker present; nothing to report
			# Optional heuristic: later repeat of <FaceDataOff, MeshDataSize> as LE dwords
			pair_le = face_off.to_bytes(4, "little") + mesh_data_size.to_bytes(4, "little")
			if pair_le in data[base:end]:
				pass

	ok = sof_ok and eof_ok

	# Construct combined reason for overall failure
	reason_parts = []
	if not sof_ok and sof_reason:
		reason_parts.append(f"SOF: {sof_reason}")
	if not eof_ok and eof_reason:
		reason_parts.append(f"EOF: {eof_reason}")
	reason = "; ".join(reason_parts)

	return CheckResult(
		path=path,
		ok=ok,
		sof_ok=sof_ok,
		eof_ok=eof_ok,
		reason=reason,
		sof_reason=sof_reason,
		eof_reason=eof_reason,
		bytes_hex=to_hex(head) if head else "",
		tail_hex=to_hex(tail) if tail else "",
		texture_start=texture_start,
		texture_end=texture_end,
		texture_chunk_end=texture_chunk_end,
		mesh_count=mesh_count,
		mesh_first=mesh_first,
		mesh_last_end=mesh_last_end,
		marker_errors=marker_errors,
	)


def parse_args(argv: List[str]) -> argparse.Namespace:
	p = argparse.ArgumentParser(description="Validate SOF signature of preinstanced PS3 files.")
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
		help="Include the first 16 bytes for each file in output",
	)
	p.add_argument(
		"--markers",
		action="store_true",
		help="Include marker offsets/details (13EA TLFD texture, 33EA mesh) in per-file output and summary",
	)
	return p.parse_args(argv)


def main(argv: List[str]) -> int:
	args = parse_args(argv)
	root = args.path
	files = list(iter_target_files(root))

	total = len(files)
	failures = 0
	sof_failures = 0
	eof_failures = 0
	files_with_texture = 0
	files_with_mesh = 0
	files_with_marker_issues = 0
	pass_lines = []
	fail_lines = []

	if not args.quiet:
		print(f"Scanning: {os.path.abspath(root)}")
		print(f"Target suffixes: {', '.join(TARGET_SUFFIXES)}")
		print(f"Found {total} file(s)\n")

	for idx, path in enumerate(files, 1):
		res = check_file(path)
		# Per-marker tally
		if not res.sof_ok:
			sof_failures += 1
		if not res.eof_ok:
			eof_failures += 1
		if res.texture_start is not None:
			files_with_texture += 1
		if res.mesh_count > 0:
			files_with_mesh += 1
		if res.marker_errors:
			files_with_marker_issues += 1
		if res.ok:
			line = None
			if not args.quiet:
				line = f"PASS - {path}"
				if args.show_bytes:
					line += f"  |  HEAD: {res.bytes_hex}  |  EOF: {res.tail_hex}"
				if args.markers:
					m_parts = []
					if res.texture_start is not None:
						# Show recommended texture region and chunk end
						tex_end_disp = (res.texture_end - 1) if (res.texture_end is not None and res.mesh_first is not None and res.texture_end == res.mesh_first) else (res.texture_end if res.texture_end is not None else None)
						m_parts.append(
							f"TL(start={to_off_hex(res.texture_start)}, end={to_off_hex(tex_end_disp)}, chunkEnd={to_off_hex(res.texture_chunk_end)})"
						)
					if res.mesh_count:
						m_parts.append(
							f"MESH(count={res.mesh_count}, range={to_off_hex(res.mesh_first)}-{to_off_hex(res.mesh_last_end)})"
						)
					if res.marker_errors:
						m_parts.append(f"markerIssues={len(res.marker_errors)}")
					if m_parts:
						line += "  |  " + "  |  ".join(m_parts)
			if line is not None:
				pass_lines.append(line)
		else:
			failures += 1
			line = f"FAIL - {path} :: {res.reason or 'validation failed'}"
			if args.show_bytes and (res.bytes_hex or res.tail_hex):
				parts = []
				if res.bytes_hex:
					parts.append(f"HEAD: {res.bytes_hex}")
				if res.tail_hex:
					parts.append(f"EOF: {res.tail_hex}")
				if parts:
					line += "  |  " + "  |  ".join(parts)
			if args.markers:
				m_parts = []
				if res.texture_start is not None:
					tx_end_disp = (res.texture_end - 1) if (res.texture_end is not None and res.mesh_first is not None and res.texture_end == res.mesh_first) else (res.texture_end if res.texture_end is not None else None)
					m_parts.append(
						f"TL(start={to_off_hex(res.texture_start)}, end={to_off_hex(tx_end_disp)}, chunkEnd={to_off_hex(res.texture_chunk_end)})"
					)
				if res.mesh_count:
					m_parts.append(
						f"MESH(count={res.mesh_count}, range={to_off_hex(res.mesh_first)}-{to_off_hex(res.mesh_last_end)})"
					)
				if res.marker_errors:
					m_parts.append("issues: " + "; ".join(res.marker_errors))
				if m_parts:
					line += "  |  " + "  |  ".join(m_parts)
			fail_lines.append(line)

		# Live progress counter (only when not quiet)
		if not args.quiet:
			progress = f"\rScanned {idx}/{total} files"
			sys.stdout.write(progress)
			sys.stdout.flush()

	# Summary
	sof_pass = total - sof_failures
	eof_pass = total - eof_failures
	sof_status = "OK" if sof_failures == 0 else "ERROR"
	eof_status = "OK" if eof_failures == 0 else "ERROR"
	overall_status = "OK" if failures == 0 else "ERROR"

	print()
	print("Summary:")
	print(f"  SOF: {sof_status} - {sof_pass} pass, {sof_failures} fail")
	print(f"  EOF: {eof_status} - {eof_pass} pass, {eof_failures} fail")
	print(f"  Overall: {overall_status} - {total - failures} pass, {failures} fail, {total} total")
	if args.markers:
		print("  Markers:")
		print(f"    TLFD textures: {files_with_texture}/{total} files")
		print(f"    Mesh blocks present: {files_with_mesh}/{total} files")
		print(f"    Files with marker issues: {files_with_marker_issues}/{total}")

	return 0 if failures == 0 else 2


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))

