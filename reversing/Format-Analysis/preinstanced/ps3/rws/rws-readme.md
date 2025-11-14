# The Simpsons Game (PS3) — .rws.preinstanced format notes

These notes are distilled from the Blender importer `PreinstancedImportExtension.py` (v1.2.4). They focus on byte patterns, field endianness, and practical tips for inspecting files with a hex editor. The importer handles both `.rws.preinstanced` and `.dff.preinstanced`; this page highlights observations specific to RWS streams and the shared “preinstanced” wrapper used on PS3.

- Game/Platform: The Simpsons Game (PS3)
- Importer: PreinstancedImportExtension.py (supported Blender 2.8–4.0)
- Scope: mesh chunk discovery, basic header fields, triangle strips, UV layers, and embedded string detection

## Quick identification (hex patterns)

The importer searches for a recurring mesh-chunk anchor pattern:

- Regex (bytes): `33 EA 00 00 ?? ?? ?? ?? 2D 00 02 1C`
  - Expressed in Python as: `b"\x33\xEA\x00\x00....\x2D\x00\x02\x1C"`
  - “....” is any 4 bytes (wildcard)
  - Useful to locate the start of a mesh-related chunk in the preinstanced data

Once this pattern is found, the importer reads several little-endian and big-endian fields (see next section).

## Mesh-chunk header (inferred from importer IO)

After the anchor pattern, the importer seeks and reads fields in this order:

- Skip: 4 bytes after the regex end
- `FaceDataOff`: uint32, little-endian
- `MeshDataSize`: uint32, little-endian
- `MeshChunkStart`: current stream position (bookmark)
- Skip: 0x14 bytes (20 bytes)
- `mDataTableCount`: uint32, big-endian
- `mDataSubCount`: uint32, big-endian

Notes and cautions:
- Endianness is mixed: offsets/sizes are LE, while the two counts are BE.
- The exact semantic meaning of the 4 bytes in the regex wildcard and the 0x14-byte gap is not confirmed (treated as unknown/padding by the importer).
- The trailing `2D 00 02 1C` sequence appears consistently near mesh data and likely denotes a RenderWare plugin/section marker (inferred), but the exact mapping is TBD.

### Suggested structure sketch (best-effort)

This is a convenience view only; unknowns are placeholders based on importer behavior:

```
Offset  Size  Endian  Name/Meaning
------  ----  ------  -------------------------------
+00     4     LE      Magic? = 33 EA 00 00 (0x0000EA33)
+04     4     -       UnknownA (regex wildcard covers +04..+07)
+08     4     -       UnknownB (regex wildcard covers +08..+0B)
+0C     4     -       Marker = 2D 00 02 1C (RenderWare plugin?)
+10     4     -       Skip4 (importer seeks +4 here before reads)
+14     4     LE      FaceDataOff
+18     4     LE      MeshDataSize
+1C     0x14  -       Unknown/Pad (skipped)
+30     4     BE      mDataTableCount
+34     4     BE      mDataSubCount
...
```

Treat the above as a navigation aid; exact field names may differ from the engine’s internal structs.

## Geometry payload shape (high level)

- Topology: triangle strips
  - Strips are converted to triangle faces with alternating winding per step.
  - Degenerate triangles (any repeated index within a tri) are skipped, but the flip sequence continues.
- Buffers: vertices plus at least one UV set and one secondary set named `CM_uv` (exact semantics unknown; could be color map or control map UVs).
- UV hygiene: the importer sanitizes non-finite UVs (NaN/Inf) by replacing them with (0.0, 0.0).

## Embedded string detection (shared with DFF)

The importer scans for known fixed signatures and attempts to read a C-style string at a fixed relative offset from each match.

- Allowed characters: ASCII letters/digits and `_ - .`
- Max scan length: 64 bytes
- Minimum accepted length: 4 characters
- Relative offset from the signature: 0x10 (16) bytes

Signatures checked (hex):

- `02 11 01 00 02 00 00 00` — “String Block Header (General, 8 bytes)”
- `02 11 01 00 02 00 00 00 14 00 00 00 2D 00 02 1C` — “String Block Header (Subtype A, 16 bytes)”
- `02 11 01 00 02 00 00 00 18 00 00 00 2D 00 02 1C` — “String Block Header (Subtype B, 16 bytes) – hypothesized”
- `90 59 20 01 00 00 80 3F 00 00 80 3F 00 00 80 3F` — “Another block type (common 1.0f pattern)” [not observed in sample below]

For each match:
- Candidate string start = signature_offset + 0x10
- Read up to 64 bytes, stop at NUL or on first disallowed char
- If decoded as ASCII and length ≥ 4, record it as a valid string

These often recover asset names, material identifiers, or short resource tags embedded near the mesh/section blocks.

## Verified against provided hex sample

From the provided dump (truncated for brevity):

- Anchor confirmed: `33 EA 00 00 C0 38 00 00 2D 00 02 1C 10 00 00 00 60 0C 00 00 54 2C 00 00 ...`
  - Matches the regex and importer flow: skip 4 (`10 00 00 00`), then `FaceDataOff = 0x0C60`, `MeshDataSize = 0x2C54` (LE).
- String signatures confirmed in-place with strings immediately after the 16-byte signature:
  - `... 02 11 01 00 02 00 00 00 14 00 00 00 2D 00 02 1C 6C 6F 63 5F 63 61 6E 65 68 6F 75 73 65 5F 72 6F 6F 66 00 ...` → `"loc_canehouse_roof"`
  - `... 02 11 01 00 02 00 00 00 18 00 00 00 2D 00 02 1C 6C 6F 63 5F 63 72 69 73 63 72 6F 73 73 5F 6D 75 6C 74 69 74 6F 6E 65 00 ...` → `"loc_criscross_multitone"`
  - `... 02 11 01 00 02 00 00 00 14 00 00 00 2D 00 02 1C 73 69 6D 70 73 6F 6E 73 5F 70 61 6C 65 74 74 65 00 ...` → `"simpsons_palette"`
  - `... 02 11 01 00 02 00 00 00 1C 00 00 00 2D 00 02 1C 6C 6F 63 5F 6F 76 65 72 6C 61 79 5F 63 6F 63 6F 63 72 75 6D 62 73 5F 61 00 ...` → `"loc_overlay_cococrumbs_a"`
- Additional recurring section IDs observed before a LE size and the same `2D 00 02 1C` marker:
  - `13 EA 00 00 <size:LE32> 2D 00 02 1C ...`
  - `15 EA 00 00 <size:LE32> 2D 00 02 1C ...`
  - `16 EA 00 00 <size:LE32> 2D 00 02 1C ...`
  - `33 EA 00 00 <size:LE32> 2D 00 02 1C ...` (the mesh anchor we key on)
  - Practical regex: `(?:13|15|16|33) EA 00 00 .. .. .. .. 2D 00 02 1C`
- The speculative `90 59 20 01 00 00 80 3F 00 00 80 3F 00 00 80 3F` header was not found in this sample; keep as unverified until corroborated by other files.

## Additional verification from new samples

Two more snippets reinforce and refine the patterns:

1) `33 EA 00 00 D4 25 00 00 2D 00 02 1C 10 00 00 00 60 03 00 00 68 22 00 00 BF BF BF BF 01 00 00 00 00 00 03 60 00 00 22 68 ...`

- Confirms post-anchor layout:
  - skip 4 → `10 00 00 00`
  - `FaceDataOff = 0x00000360`
  - `MeshDataSize = 0x00002268`
- Repeated pair later as LE dwords: `00 00 03 60 00 00 22 68`
- Sentinel-like dword `BF BF BF BF` commonly appears after size fields (purpose TBD)
- Followed by a table of LE u32 values that look like sub-chunk offsets/lengths:
  - e.g., `00 00 00 10`, `00 00 00 18`, `00 00 00 F4`, `00 00 00 FC`, `00 00 01 2C`, ... (likely offsets within the mesh block)

2) `16 EA 00 00 24 00 00 00 2D 00 02 1C ... 15 EA 00 00 08 00 00 00 2D 00 02 1C ... 33 EA 00 00 18 9A 00 00 2D 00 02 1C 10 00 00 00 60 0A 00 00 AC 8F 00 00 BF BF BF BF 01 00 00 00 00 00 0A 60 00 00 8F AC ...`

- Shows a sequence of small blocks (IDs `16 EA`, `15 EA`) preceding a larger `33 EA` mesh block
- For the `33 EA` block:
  - `FaceDataOff = 0x00000A60`, `MeshDataSize = 0x00008FAC`
  - The same LE pair is repeated later: `00 00 0A 60 00 00 8F AC`
  - The `BF BF BF BF` dword and `01 00 00 00` also appear before the repetition

Refined regex helpers:
- Any section header: `(?:13|15|16|33) EA 00 00 .. .. .. .. 2D 00 02 1C`
- String signatures: `02 11 01 00 02 00 00 00(?: 14| 18| 1C) 00 00 00 2D 00 02 1C`

These corroborate the mixed-endian navigation and the presence of sub-chunk tables following the mesh header.

## Hex-inspection checklist

When analyzing an `.rws.preinstanced` file in a hex editor:

1. Search for the mesh anchor: `33 EA 00 00 ?? ?? ?? ?? 2D 00 02 1C`.
2. From the end of that pattern, skip 4 bytes, then read two LE u32s: `FaceDataOff`, `MeshDataSize`.
3. Skip 0x14 bytes and read two BE u32s: `mDataTableCount`, `mDataSubCount`.
4. Use `FaceDataOff` to locate triangle strip index data. Expect alternating-winding unpack.
5. Look for embedded strings by scanning for the signatures above; then jump +0x10 to read a potential ASCII string.

## Minimal example template for notes

Use this to jot down findings for a particular file as you browse:

```
File: <name>.rws.preinstanced  Size: 0x???????

[Mesh Anchor]
Offset: 0x????????  Bytes: 33 EA 00 00 ?? ?? ?? ?? 2D 00 02 1C
FaceDataOff (LE): 0x???????
MeshDataSize (LE): 0x???????
mDataTableCount (BE): 0x???????
mDataSubCount  (BE): 0x???????

[Strings]
Sig @ 0x????????: 02 11 01 00 02 00 00 00 -> String @ +0x10: "..."
Sig @ 0x????????: 90 59 20 01 ... -> (unverified signature; skip unless seen)

[Topology]
- N strips: ?   (degenerates skipped)
- N faces (post-conversion): ?
- UV layers: uvmap, CM_uv (sanitized: Y/N)
```

## Open questions / to validate

- The exact semantics of the `2D 00 02 1C` marker and the 0x14-byte gap.
- Whether the wildcard 4 bytes after `33 EA 00 00` encode a size/version.
- Full field layout of the sub-tables addressed by `mDataTableCount/mDataSubCount`.

If you confirm or refine any of the above, please update this document and the importer comments accordingly.