# The Simpsons Game (PS3) — .dff.preinstanced format notes

These notes are based on the Blender importer `PreinstancedImportExtension.py` (v1.2.4). While the importer treats `.rws.preinstanced` and `.dff.preinstanced` similarly at the “preinstanced” wrapper level, DFF content follows RenderWare’s DFF conventions internally, with PS3-specific packing.

- Game/Platform: The Simpsons Game (PS3)
- Container: preinstanced-wrapped DFF
- Importer scope: discovery of mesh chunks, triangle strips, UV assignment, and embedded string recovery

## Quick identification (hex patterns)

The importer keys off an internal anchor pattern inside the preinstanced container (also present in the sample you provided):

- Anchor regex (bytes): `33 EA 00 00 ?? ?? ?? ?? 2D 00 02 1C`
  - Python: `b"\x33\xEA\x00\x00....\x2D\x00\x02\x1C"`

Additional section IDs observed in the provided sample that follow a similar layout (`<id> EA 00 00 <size:LE32> 2D 00 02 1C ...`):

- `13 EA 00 00`, `15 EA 00 00`, `16 EA 00 00`, and `33 EA 00 00`
  - Practical regex to spot any: `(?:13|15|16|33) EA 00 00 .. .. .. .. 2D 00 02 1C`

## Header/navigation fields (inferred)

After the `33 EA 00 00` anchor:

- Skip 4 bytes
- Read `FaceDataOff` (LE u32)
- Read `MeshDataSize` (LE u32)
- Bookmark current position as `MeshChunkStart`
- Skip 0x14 bytes
- Read `mDataTableCount` (BE u32)
- Read `mDataSubCount` (BE u32)

Remarks:
- Mixed endianness: little-endian for offsets/sizes, big-endian for certain counts.
- The `2D 00 02 1C` dword marker appears as a recurring block/section delimiter.

## Geometry representation

- Topology: triangle strips expanded to triangle lists with alternating winding
- Degenerates: skipped (flip toggling continues)
- Output parts: `Mesh_<meshIndex>_<subIndex>`
- UV layers:
  - `uvmap` — primary set; non-finite values sanitized to (0,0)
  - `CM_uv` — secondary set; semantics TBD

## String blocks (verified against sample)

The importer scans for signatures and reads a string at a fixed relative offset (+0x10):

- Allowed characters: `[A-Za-z0-9_.-]`
- Max scan length: 64 bytes, min length: 4

Confirmed in samples:

- `02 11 01 00 02 00 00 00 14 00 00 00 2D 00 02 1C` → string follows immediately (e.g., `simpsons_palette`, `loc_canehouse_roof`)
- `02 11 01 00 02 00 00 00 18 00 00 00 2D 00 02 1C` → string follows (e.g., `loc_criscross_multitone`)
- `02 11 01 00 02 00 00 00 1C 00 00 00 2D 00 02 1C` → string follows (e.g., `loc_overlay_cococrumbs_a`)

Unverified here (keep as tentative until seen in files):

- `90 59 20 01 00 00 80 3F 00 00 80 3F 00 00 80 3F`

Extraction procedure:
- For each signature at offset S, candidate string at S + 0x10
- Read until NUL or invalid char, <= 64 bytes; accept if ASCII length ≥ 4

## Additional verification from new samples

- Example block: `33 EA 00 00 D4 25 00 00 2D 00 02 1C 10 00 00 00 60 03 00 00 68 22 00 00 BF BF BF BF 01 00 00 00 00 00 03 60 00 00 22 68 ...`
  - Confirms `FaceDataOff = 0x360`, `MeshDataSize = 0x2268` (LE), with the pair repeated later as LE dwords
  - `BF BF BF BF` sentinel-like dword appears after size; semantics TBD
  - Followed by a table of LE u32 values (candidate sub-chunk offsets/lengths)
- Sequence with smaller blocks preceding mesh: `16 EA 00 00 <24> 2D 00 02 1C ... 15 EA 00 00 <08> 2D 00 02 1C ... 33 EA 00 00 <9A18> 2D 00 02 1C 10 00 00 00 60 0A 00 00 AC 8F 00 00 BF BF BF BF 01 00 00 00 00 00 0A 60 00 00 8F AC ...`
  - Repeats the FaceDataOff/MeshDataSize pair (0x0A60, 0x8FAC) later in the block

Refined regex helpers:
- Any section header: `(?:13|15|16|33) EA 00 00 .. .. .. .. 2D 00 02 1C`
- String signatures: `02 11 01 00 02 00 00 00(?: 14| 18| 1C) 00 00 00 2D 00 02 1C`

## Hex walkthrough checklist

1. Search for `33 EA 00 00 ?? ?? ?? ?? 2D 00 02 1C` (mesh anchor).
2. From the match end: skip 4; read LE `FaceDataOff`, LE `MeshDataSize`.
3. Skip 0x14; read BE `mDataTableCount` and BE `mDataSubCount`.
4. Use `FaceDataOff` to locate strip indices; expand to triangles with alternating winding, skipping degenerates.
5. Scan for `02 11 01 00 02 00 00 00` + a size (`14/18/1C 00 00 00`) then `2D 00 02 1C`; strings start at +0x10.

## Field sketch (navigation aid)

```
Anchor       : 33 EA 00 00 .. .. .. .. 2D 00 02 1C
+0x00..+0x03 : (post-anchor) skip 4
+0x04        : FaceDataOff (LE u32)
+0x08        : MeshDataSize (LE u32)
+0x0C..+0x1F : skip 0x14
+0x20        : mDataTableCount (BE u32)
+0x24        : mDataSubCount  (BE u32)
```

Note: Offsets here are relative to the position immediately after the anchor match; the actual file offsets vary by occurrence.

## Gotchas and validation items

- The meanings of section IDs `13/15/16/33 EA 00 00` and how they map to RW chunks.
- Whether the 4-byte wildcard after `33 EA 00 00` is a size, flags, or version.
- Detailed layouts of sub-tables referenced by `mDataTableCount` / `mDataSubCount`.

If you refine these findings, please update both this document and the importer’s inline comments.