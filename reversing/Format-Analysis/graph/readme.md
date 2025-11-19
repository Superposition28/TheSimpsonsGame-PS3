

## File Format Documentation: `.graph` (Simpsons Game Navigation Graph)

**Version:** 0.4 (draft)
**Last Updated:** 2025-11-14
**Author(s):** samarixum

---

## 1. Overview

* **Format Name:** The Simpsons Game Navigation Graph
* **Common File Extension(s):** `.graph`
* **Purpose/Domain:**
  Encodes navigation graphs and navmesh-like data for AI/pathfinding in *The Simpsons Game* (PS3). Each file typically represents one navigation “chunk” for a zone/area (e.g. `zone02_str` in `MedalOfHomer`).
* **Originating Application/System:**
  Custom navigation system used by *The Simpsons Game*’s engine (likely built on or alongside the modified RenderWare pipeline used for `.rws` / `.dff.preinstanced` assets). 
* **Format Type:** Binary
* **General Structure (high level):**

  > Single, fixed-size header → small header extension → primary node array → optional edge block → optional auxiliary blocks (bitmask/flags, index lists, coordinate references, extra tables, config) → padding/EOF.

Unlike the preinstanced `.dff/.rws` format, `.graph` **does** have a proper global header and a mostly fixed ordering; the variations are about which optional blocks are present. 

---

## 2. Identification

files are identified by:

* **Extension / Context:**

  * Stored under level folders like:
    `...medal_of_homer\story_mode\zoneXX\...\graph\{GUID}.graph`
* **Structurally:**

  * A valid header where:

    * `0x0C` is a 32-bit BE value whose **high 16 bits** are a plausible node count and **low 16 bits** are a plausible secondary count.
    * `0x20` is a node array offset that points into the file (often `0x00000094`).
    * `node_offset + node_count * 0x20` aligns with either `0x24` or `0x68`.

### 2.1 “Version” / Identification fields

There is no explicit version field yet identified. The closest things to “identity” are:

* **GUID (File ID)**

  * **Location:** `0x10–0x1F`
  * **Size:** 16 bytes (`byte[16]`)
  * **Type:** Opaque GUID / ID (per-file; matches GUID in filename)
  * **Notes:** Likely used by the engine to cross-reference graph chunks.

* **Node/Edge Count Word (raw0C)**

  * **Location:** `0x0C–0x0F`
  * **Type:** `uint32_be`
  * **Layout:** `raw0C = (node_count << 16) | other_count`

    * `node_count` = number of node records in the node array
    * `other_count` = secondary count (often equal to edge count in small graphs, but not always; may include other structures in big graphs)

Because the format appears consistent across all PS3 `.graph` files inspected, we currently treat it as a single “version”.

---

## 3. Global Properties

* **Endianness:**

  * **Big-Endian** for everything observed so far:

    * All integers in header and blocks (`uint16_be`, `uint32_be`, `int16_be`)
    * All floats (`float32_be`)
  * Unlike the `.dff.preinstanced` format, there are **no known little-endian exceptions** in `.graph`. 

* **Character Encoding:**

  * None observed in `.graph` files themselves (no plain-text strings). GUIDs are binary, not ASCII.

* **Default Alignment:**

  * Header is 0x80 bytes.
  * Node array is aligned to 4 bytes (and typically at 0x94).
  * Many structures are sized in multiples of 0x10 or 0x20 bytes.
  * There are small 4-byte padding gaps between blocks in some variants.

* **Compression:**

  * None observed. All fields appear directly readable with no compression.

* **Encryption:**

  * None observed.

---

## 4. Detailed Structure

### 4.1 Top-Level Layout

At a high level, the file is:

1. **Main Header (0x00–0x7F)** – fixed size (128 bytes).
2. **Header Extension (0x80–`node_offset`)** – small, mostly-zero block with one float.
3. **Node Array (`node_count` × 32-byte structs)**.
4. **Optional Edge Array** – 16-byte edge records directly after the node array.
5. **Optional blocks located via header offsets:**

   * Bitmask / flags at `off40`
   * Index lists at `off44`
   * Coordinate reference data at `off48`
   * Extra table at `off60` (only if `count_64 > 0`)
   * Alternative/extra block at `off68` (also sometimes used as alternative node-end)
   * Config / mini-block at `off70`
6. **Trailing padding / unused data** (unknown semantics, file end).

Not all blocks are present in every `.graph`. The presence/absence combination defines “layout families” (e.g. nodes-only, nodes+edges, nodes+navmesh, etc.).

---

### 4.2 Header (0x00–0x7F)

> **Size:** 0x80 bytes (128)
> **Endianness:** Big-endian for all numeric fields

| Offset (Hex) | Size | Type        | Name           | Description                                                                                     |
| -----------: | ---: | ----------- | -------------- | ----------------------------------------------------------------------------------------------- |
|       `0x00` |    4 | `uint32_be` | `unk_00`       | Unknown. Appears as `0x00000000` or small values in all samples. Possibly reserved/version.     |
|       `0x04` |    4 | `uint32_be` | `unk_04`       | Unknown; often 0.                                                                               |
|       `0x08` |    4 | `uint32_be` | `hdr_magic_10` | Constant `0x00000010` in observed files; likely a header size/marker (16).                      |
|       `0x0C` |    4 | `uint32_be` | `raw0C`        | Packed counts: `node_count = raw0C >> 16`, `other_count = raw0C & 0xFFFF`.                      |
|       `0x10` |   16 | `byte[16]`  | `graph_guid`   | Per-file GUID/ID; matches GUID used in filename.                                                |
|       `0x20` |    4 | `uint32_be` | `node_offset`  | Offset (from file start) to the beginning of the node array. Often `0x00000094`.                |
|       `0x24` |    4 | `uint32_be` | `node_end_24`  | Preferred node-array end offset, if it “looks right”. Alternative to `off68`.                   |
|       `0x28` |   20 | `byte[20]`  | `unk_28`       | Unknown; possibly bounding information or tuning constants.                                     |
|       `0x3C` |    4 | `uint32_be` | `count_3C`     | Secondary count or block count. Varies per file; exact role unknown.                            |
|       `0x40` |    4 | `uint32_be` | `off40`        | Offset to “bitmask/flags” block (if non-zero).                                                  |
|       `0x44` |    4 | `uint32_be` | `off44`        | Offset to “index-lists” block (if non-zero).                                                    |
|       `0x48` |    4 | `uint32_be` | `off48`        | Offset to “coord-ref” (coordinate reference/geometry) block (if non-zero).                      |
|       `0x4C` |   20 | `byte[20]`  | `unk_4C`       | Unknown / reserved. Often includes `FF FF 00 00` patterns.                                      |
|       `0x60` |    4 | `uint32_be` | `off60`        | Offset to extra table block (only meaningful if `count_64 > 0`).                                |
|       `0x64` |    4 | `uint32_be` | `count_64`     | Small count associated with the `off60` block (0 in most files; 1–16 in big/complex graphs).    |
|       `0x68` |    4 | `uint32_be` | `off68`        | Sometimes used as an **alternative node array end**. Also acts as a block offset in some files. |
|       `0x6C` |    4 | `uint32_be` | `unk_6C`       | Unknown.                                                                                        |
|       `0x70` |    4 | `uint32_be` | `off70`        | Offset to small config/mini block (usually nonzero).                                            |
|       `0x74` |    4 | `uint32_be` | `val74`        | Large value; likely some total count or bitfield; not required to parse main blocks.            |
|       `0x78` |    4 | `uint32_be` | `magic_6D`     | Typically `0x6D000000` in observed samples (“m” / 0x6D).                                        |
|       `0x7C` |    4 | `uint32_be` | `unk_7C`       | Usually `0x00000000`.                                                                           |

**Determining `node_count` and `node_end`:**

* `node_count = raw0C >> 16`
* `other_count = raw0C & 0xFFFF`
* `expected_node_end = node_offset + node_count * 0x20`
* If `node_end_24` is non-zero and `node_end_24 - node_offset` is a multiple of 0x20 and ≥ 0, use `node_end_24`.
  Else if `off68` passes that same check, use `off68`.
  Else fall back to `expected_node_end`.

---

### 4.3 Header Extension Block `[0x80 .. node_offset)`

Immediately after the main header, but before the node array, there is always a **small extension block**:

| Offset (Hex, relative to block start) | Size | Type         | Description                                          |
| ------------------------------------: | ---: | ------------ | ---------------------------------------------------- |
|                                `0x00` |    8 | `byte[8]`    | All zeros in observed files.                         |
|                                `0x08` |    4 | `float32_be` | Single **per-graph parameter** (small value, ~0.01). |
|                                `0x0C` |    8 | `byte[8]`    | All zeros in observed files.                         |

* **Block size:** Typically 0x14 (20 bytes) but treated as `node_offset - 0x80`.
* **Semantics:** Unknown; likely a tuning factor or scale/weight for navigation costs.
* **Presence:** All 425 files examined have this block.

---

### 4.4 Node Array

**Location:** `node_offset` (from header)
**Count:** `node_count` (from `raw0C`)
**Size per Node:** 0x20 (32) bytes

**Structure: `GraphNode`**

| Offset (Rel.) | Size | Type         | Name      | Description                                              |
| ------------: | ---: | ------------ | --------- | -------------------------------------------------------- |
|        `0x00` |    4 | `float32_be` | `x`       | World-space X coordinate of the node.                    |
|        `0x04` |    4 | `float32_be` | `y`       | World-space Y coordinate (height).                       |
|        `0x08` |    4 | `float32_be` | `z`       | World-space Z coordinate of the node.                    |
|        `0x0C` |    4 | `float32_be` | `radius`  | Node radius; in all samples ~`0.125`.                    |
|        `0x10` |    2 | `uint16_be`  | `node_id` | Node ID. Often sequential from 0..N−1, sometimes sparse. |
|        `0x12` |    2 | `int16_be`   | `area_id` | Area index. Often `-1` (`0xFFFF`) when unassigned.       |
|        `0x14` |    4 | `uint32_be`  | `flags`   | Node flags / type bits. Values like `0x01000000`, etc.   |
|        `0x18` |    4 | `uint32_be`  | `unk1`    | Unknown; usually 0.                                      |
|        `0x1C` |    4 | `uint32_be`  | `unk2`    | Unknown; usually 0.                                      |

The nodes define the **core waypoint graph** and radius footprints for AI agents.

**Note:** Some `.graph` files (a small subset) have **no nodes at all** (`node_count == 0` and no node block). These appear to be “geometry-only” navmesh overlays.

---

### 4.5 Edge Block (Optional)

**Location:** Immediately after the node array, at `node_end`.
**Presence:** Controlled implicitly; only if the data at `node_end` parses cleanly into edges before the next header-offset block.

To find the end of the edge block:

1. Collect all non-zero offsets greater than `node_end` from:

   * `off40`, `off44`, `off48`, `off60`, `off68`, `off70`
2. The earliest such offset is taken as `edge_block_end`.
3. Edge records are parsed from `node_end` up to `edge_block_end`, as 16-byte structs, **while they pass sanity checks**.

**Structure: `GraphEdge` (16 bytes)**

| Offset (Rel.) | Size | Type         | Name    | Description                                      |
| ------------: | ---: | ------------ | ------- | ------------------------------------------------ |
|        `0x00` |    4 | `float32_be` | `cost`  | Edge traversal cost or weight (positive float).  |
|        `0x04` |    2 | `uint16_be`  | `a`     | Source node index (0 ≤ `a` < `node_count`).      |
|        `0x06` |    2 | `uint16_be`  | `b`     | Destination node index (0 ≤ `b` < `node_count`). |
|        `0x08` |    2 | `int16_be`   | `tag_c` | Small tag; almost always `-1` or `0`.            |
|        `0x0A` |    2 | `uint16_be`  | `tag_d` | Small tag; often `0`.                            |
|        `0x0C` |    4 | `uint32_be`  | `zero`  | Always `0x00000000` in observed samples.         |

This provides explicit node-to-node connectivity for the graph. Many graphs have these; some rely purely on polygon structures instead.

---

### 4.6 Auxiliary Blocks (via Header Offsets)

These blocks are located via `off40`, `off44`, `off48`, `off60`, `off68`, and `off70`. Not all are present in every file.

#### 4.6.1 Bitmask / Flags Block (`off40`)

**Location:** `off40` (if non-zero).
**Content:** Byte array, typically high density of `0x00`, `0x10`, `0x11`.

Likely a **grid or sector bitfield**:

* Each byte encodes one or more boolean attributes (walkable, blocking, area type, etc.).
* Exact mapping is unknown, but in graphs where present it correlates with areas where AI can/can’t walk.

#### 4.6.2 Index Lists Block (`off44`)

**Location:** `off44` (if non-zero).
**Content:** `uint16_be` values packed back-to-back.

Typical characteristics:

* Most values are either:

  * `0xFFFF` (sentinel / separator), or
  * `< node_count` (indices into nodes or coord-ref vertices).
* Interpreted as lists of indices, broken up by `0xFFFF`.

Probable use:

* Triangles / polygons / sectors referencing:

  * nodes, or
  * coordinate references in the `coord-ref` block.

#### 4.6.3 Coordinate Reference Block (`off48`)

**Location:** `off48` (if non-zero).
**Content:** Sequences of 3 *big-endian floats*: `(x, y, z)`.

Observed properties:

* A large fraction of these triplets EXACTLY match node positions (within float precision).
* Appears to be a **vertex table** for navmesh/sector geometry. Some triplets may be duplicates or local copies of node coordinates.

Probable use:

* Combined with `index-lists` to define polygons, volumes, or area surfaces, separate from the basic node graph. This allows finer navmesh geometry over the coarse node graph.

#### 4.6.4 Extra Table Block (`off60` + `count_64`)

**Location:** `off60` (if non-zero and `count_64 > 0`).
**Content:** `uint32_be` values; in many large graphs, they follow a pattern like:

```text
0x00000000, 0x00000010,
0x00000000, 0x00000020,
0x00000000, 0x00000030,
...
```

i.e., alternating zeros and increasing multiples of 0x10.

Probable semantics:

* An **offset or index table** into substructures:

  * Either further sub-blocks within this `.graph` file, or
  * offsets into a shared structure when graphs are stitched together.

This block is still under active investigation.

#### 4.6.5 Alternate Block / Extra Region (`off68`)

`off68` is overloaded:

* Sometimes used as an alternate `node_end` value (see Section 4.2).
* In some complex graphs, also acts as a block start (i.e., there is a real data region starting at `off68` when it does not equal the node end). The exact semantics of that region remain unclear.

For parsing purposes:

* Treat `off68` primarily as a candidate node-end.
* If it falls after `node_end` and before other offsets, it may be a separate block boundary.

#### 4.6.6 Config / Mini Block (`off70`)

**Location:** `off70` (if non-zero).
**Size:** Typically ≤ 0x20 bytes.

This appears to be a tiny configuration struct:

* Contains a handful of small integers/flags.
* The exact fields are not yet decoded.

Probable purpose:

* Per-graph tuning and flags for AI/pathfinding systems (e.g. movement mode, graph type, dynamic vs static, etc.).

---

## 5. Data Types Reference

* **`uint16_be`** – Unsigned 16-bit integer, big-endian.
* **`int16_be`** – Signed 16-bit integer, big-endian.
* **`uint32_be`** – Unsigned 32-bit integer, big-endian.
* **`float32_be`** – 32-bit IEEE 754 floating-point, big-endian.
* **`byte[N]`** – Raw N bytes, meaning varies (GUIDs, padding, unknown fields).

---

## 6. Checksums / Integrity Checks

* No checksum or hash fields have been identified.
* There is no obvious CRC32/Adler pattern, nor a dedicated “checksum” field in the header.
* Files seem to rely on structural sanity:

  * counts matching spans (`node_count * 0x20`),
  * indices within bounds,
  * and offsets not overlapping incorrectly.

---

## 7. Known Variations / Versions

Although there is no explicit version field, real-world `.graph` files fall into **“families”** based on which blocks they contain:

1. **Waypoint Graph Only:**

   * `nodes + edges + config/mini`
   * No coord-ref, index-lists, or bitmask.
   * Used for simple areas where a basic node graph is sufficient.

2. **Navmesh-Only (Geometry) Graph:**

   * `nodes + coord-ref + index-lists`
   * No explicit edges – connectivity is implied by polygons.
   * Some rare files even have **no nodes**, just `coord-ref + index-lists` (geometry-only overlays).

3. **Hybrid Graph:**

   * `nodes + edges + coord-ref` (+/- index-lists + config)
   * Combines explicit graph edges with detailed navmesh geometry.

4. **Flagged Graph:**

   * `nodes + edges + bitmask/flags` (+ config, possibly coord-ref/index-lists)
   * Adds bitmask/flags for fine-grained walkability or area typing.

5. **Complex Graph with Extra Table:**

   * All of the above plus:

     * `off60` block with `count_64` > 0
     * large `coord-ref` / `index-lists` regions
   * Used in large hub levels or complex zones.

At the moment, all of these are treated as the **same format** with optional blocks, rather than separate versions.

---

## 8. Analysis Tools & Methods

* **Tools Used:**

  * Custom Python scripts (`check_graph_headers.py`, `graph_explorer.py`, `graph_layouts.py`) to:

    * parse header fields,
    * verify node/edge block spans,
    * detect and classify blocks using offset hints and patterns.
  * Hex editor for spot inspection.
  * Comparison against known, documented formats (e.g. `.dff.preinstanced` / `.rws.preinstanced`). 
  * Inferred bounding boxes and plotted node positions to verify 3D coordinates.

* **Methodology:**

  1. Identify stable fields that validate across many `.graph` files:

     * `raw0C` counts, `node_offset`, `node_end`, etc.
  2. Parse node arrays and confirm they yield sensible world-space coordinates for levels.
  3. Use header offsets to slice files into blocks.
  4. Heuristically classify blocks via:

     * value distributions (e.g., 0x10/0x11 densities),
     * index ranges (`< node_count`),
     * coordinate reuse (triplets matching node coords).
  5. Group files by layout (presence/absence of blocks) to understand how flexible the format is.
  6. Iterate over misclassified / unknown blocks with more focused analysis.

The structure of this document follows a generic file-format template used for other reverse-engineered formats in this project.

---

## 9. Open Questions / Uncertainties

* **Exact meaning of `other_count` (low 16 bits of `raw0C`):**

  * Matches edge count in small graphs, but not always in large ones.
  * Likely includes multiple sub-block counts (edges + polygons + something else).

* **Fields at `0x00`, `0x04`, `0x28–0x3B`, `0x4C–0x5F`, `0x6C`:**

  * Purpose unknown; may contain bounding volumes, level flags, or versioning.

* **`count_3C`:**

  * Appears related to number of regions/blocks, but exact semantics are unclear.

* **`off60` + `count_64` table:**

  * Clearly structured (offset/stride pattern), but destination / logical meaning is unknown.
  * May index into subgraphs, sectors, or cross-file references.

* **`off68` as data block vs alternative node_end:**

  * Dual-purpose makes it tricky to interpret automatically.
  * Needs correlation with decompiled code or runtime behavior.

* **Config / mini block fields:**

  * We know where it is and how big it is, but not what each byte means.

* **Node `flags`, `unk1`, `unk2`:**

  * We’ve identified where they are, not how they’re interpreted by the AI.

---



all 425 graph files found in the game, listed with their full paths:
/Map_3-00_GameHub/gamehub/zone13_str/build/PS3/pal_en/assets_rws/gamehub/gamehub/graph/{91CD1F91-8C47-4D32-BDEC-BE274ACAC8F8}.graph
/Map_3-00_GameHub/gamehub_str/build/PS3/pal_en/assets_rws/gamehub/gamehub/graph/{04A213AF-0457-4AD1-B581-3B9C919BA4A3}.graph
/Map_3-00_GameHub/gamehub_str/build/PS3/pal_en/assets_rws/gamehub/gamehub/graph/{31646778-9A5A-40B0-8D0F-0C6FB3F52061}.graph
/Map_3-00_GameHub/gamehub_str/build/PS3/pal_en/assets_rws/gamehub/gamehub/graph/{316D093A-E43C-4107-8F20-28423FCCB80B}.graph
/Map_3-00_GameHub/gamehub_str/build/PS3/pal_en/assets_rws/gamehub/gamehub/graph/{4AEEE35E-11FB-4EDC-88ED-D095D9AF0A43}.graph
/Map_3-00_GameHub/gamehub_str/build/PS3/pal_en/assets_rws/gamehub/gamehub/graph/{55F2E4FF-4640-4135-ADE5-FDF05ADECFA4}.graph
/Map_3-00_GameHub/gamehub_str/build/PS3/pal_en/assets_rws/gamehub/gamehub/graph/{8525883B-F96F-4D09-B17D-69B5A659797D}.graph
/Map_3-00_GameHub/gamehub_str/build/PS3/pal_en/assets_rws/gamehub/gamehub/graph/{D29C8335-B1AF-4F47-A03B-4E0BA8072A39}.graph
/Map_3-00_GameHub/gamehub_str/build/PS3/pal_en/assets_rws/gamehub/gamehub/graph/{E8B24A76-F3A2-4060-9974-30FDF49AEF21}.graph
/Map_3-00_GameHub/gamehub_str/build/PS3/pal_en/assets_rws/gamehub/gamehub/graph/{EE42CEF8-F247-47E2-9049-98B07CBBB725}.graph
/Map_3-00_SprHub/spr_hub/design/Act_1_folderstream_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{6F0D1BEE-580F-4C01-AC57-3482ADB110A5}.graph
/Map_3-00_SprHub/spr_hub/zone01_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{30EC3598-BAD7-4A9A-8218-F0E278A310FB}.graph
/Map_3-00_SprHub/spr_hub/zone01_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{34D45FEB-32D8-4D71-9FDD-0E3ADA758AC8}.graph
/Map_3-00_SprHub/spr_hub/zone01_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{BBF042F7-C75B-4773-B4B9-257683727E8F}.graph
/Map_3-00_SprHub/spr_hub/zone02_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{44503C3A-1849-49C0-A9F1-D4FDDFB2ECA5}.graph
/Map_3-00_SprHub/spr_hub/zone02_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{946EC497-3470-408D-ADB8-5DB82E830EE2}.graph
/Map_3-00_SprHub/spr_hub/zone03_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{096C6248-78A8-4D77-9572-CE834F104942}.graph
/Map_3-00_SprHub/spr_hub/zone03_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{BE26059F-AC21-4433-B8A6-274B6945A31F}.graph
/Map_3-00_SprHub/spr_hub/zone04_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{61389D28-0F35-4057-9CC3-441D705DF0EF}.graph
/Map_3-00_SprHub/spr_hub/zone04_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{EED5D320-928C-48C5-855F-78526963E227}.graph
/Map_3-00_SprHub/spr_hub/zone05_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{80FEA8F2-D23D-4AEA-A405-00239304F5C5}.graph
/Map_3-00_SprHub/spr_hub/zone05_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{F0083C84-47E7-4262-BDD3-557D15C4AD3B}.graph
/Map_3-00_SprHub/spr_hub/zone06_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{8C84D3D7-EB15-4776-BA04-C85CCC70E176}.graph
/Map_3-00_SprHub/spr_hub/zone06_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{CB99D88A-36F3-47F9-A010-5944FC534794}.graph
/Map_3-00_SprHub/spr_hub/zone07_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{5C062BB2-28E8-4F05-A004-A8B82449158C}.graph
/Map_3-00_SprHub/spr_hub/zone07_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{D47F6B2E-4741-4B39-8563-BAED91D4648C}.graph
/Map_3-00_SprHub/spr_hub/zone07_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{F524D089-0A10-402B-9FD8-BF45E663F42C}.graph
/Map_3-00_SprHub/spr_hub/zone08_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{2281AF75-AD8B-46C8-BB0E-218ACF82BC1E}.graph
/Map_3-00_SprHub/spr_hub/zone08_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{48B76C50-3C8E-4490-B5BD-60943FE44D63}.graph
/Map_3-00_SprHub/spr_hub/zone09_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{EFC6837C-083E-46E4-9559-8FB01CC523F1}.graph
/Map_3-00_SprHub/spr_hub/zone10_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{23D78C50-7509-4C33-982E-6328947F6204}.graph
/Map_3-00_SprHub/spr_hub/zone10_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{67D6D0B0-EA65-4290-B743-9557877BE207}.graph
/Map_3-00_SprHub/spr_hub/zone13_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{91CD1F91-8C47-4D32-BDEC-BE274ACAC8F8}.graph
/Map_3-00_SprHub/spr_hub/zone14_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{1A05EF91-D970-4EE7-945C-517222C38AAA}.graph
/Map_3-00_SprHub/spr_hub/zone15_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{15D1B993-141B-4B3B-AF50-DD7C3870EDEE}.graph
/Map_3-00_SprHub/spr_hub/zone15_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{94042C67-EB54-4829-9E18-044FE6A5BCDB}.graph
/Map_3-00_SprHub/spr_hub/zone15_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{ACD9809E-C3F0-410C-90D0-1B9A08CD5713}.graph
/Map_3-00_SprHub/spr_hub/zone16_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{00CFC530-3739-46E1-ADFF-55393D3D5F53}.graph
/Map_3-00_SprHub/spr_hub/zone16_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{58C1EAC5-0C57-4C4F-AFE0-34B4EDB1B79D}.graph
/Map_3-00_SprHub/spr_hub/zone17_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{3AFE226F-FFB7-4F26-BF1B-E73DD69C8348}.graph
/Map_3-00_SprHub/spr_hub/zone17_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{F700B624-4EB0-4033-A0E4-3E9C24A76067}.graph
/Map_3-00_SprHub/spr_hub/zone19_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{83571910-282C-4D6F-9ED6-95A67E0A2B88}.graph
/Map_3-00_SprHub/spr_hub/zone20_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{DB4E2494-0B0F-4FC7-99D9-49C7261E6E01}.graph
/Map_3-00_SprHub/spr_hub/zone21_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{21551060-3D6B-4D5C-90E0-FBFD8F494F1D}.graph
/Map_3-00_SprHub/spr_hub/zone21_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{754A060E-626E-4A31-93B2-F82D7B68C815}.graph
/Map_3-00_SprHub/spr_hub/zone21_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{E861E4FE-CD4E-4368-9F40-8B645CF78AF9}.graph
/Map_3-00_SprHub/spr_hub_str/build/PS3/pal_en/assets_rws/spr_hub/spr_hub/graph/{3513FEF3-4DEC-4EB2-96BB-4D5D94BC62A4}.graph
/Map_3-01_LandOfChocolate/loc/Challenge_Mode/Challenge_Mode_Design_str/build/PS3/pal_en/assets_rws/loc/loc/graph/{C62CB55D-3C27-4216-B651-57EB3DEB71EC}.graph
/Map_3-01_LandOfChocolate/loc/Story_Mode/Story_Mode_Design_str/build/PS3/pal_en/assets_rws/loc/loc/graph/{015DA6D2-352E-40F6-A78E-81713291CEC1}.graph
/Map_3-01_LandOfChocolate/loc/Story_Mode/Story_Mode_Design_str/build/PS3/pal_en/assets_rws/loc/loc/graph/{053FCFAE-55F0-462B-A8B4-724690F8B732}.graph
/Map_3-01_LandOfChocolate/loc/Story_Mode/Story_Mode_Design_str/build/PS3/pal_en/assets_rws/loc/loc/graph/{543D213A-F06E-42C3-8A24-97B9DEFFDA77}.graph
/Map_3-01_LandOfChocolate/loc/Story_Mode/Story_Mode_Design_str/build/PS3/pal_en/assets_rws/loc/loc/graph/{ABD43E7E-E5F1-429C-A44D-DFD167B1EE2A}.graph
/Map_3-01_LandOfChocolate/loc/Story_Mode/Story_Mode_Design_str/build/PS3/pal_en/assets_rws/loc/loc/graph/{B3468CEE-D3C4-4EAB-9670-30539131480B}.graph
/Map_3-01_LandOfChocolate/loc/Story_Mode/Story_Mode_Design_str/build/PS3/pal_en/assets_rws/loc/loc/graph/{ECBAD9E8-BAFB-4A8D-AE0F-02831501F3EB}.graph
/Map_3-01_LandOfChocolate/loc_str/build/PS3/pal_en/assets_rws/loc/loc/graph/{74C88925-83BF-46F9-8C83-ED252A44A1DC}.graph
/Map_3-01_LandOfChocolate/loc_str/build/PS3/pal_en/assets_rws/loc/loc/graph/{77945598-5F84-4DFF-A91B-B248BC99F6A9}.graph
/Map_3-01_LandOfChocolate/loc_str/build/PS3/pal_en/assets_rws/loc/loc/graph/{996AF219-E201-48EB-863B-4FE4FBC9213C}.graph
/Map_3-01_LandOfChocolate/loc_str/build/PS3/pal_en/assets_rws/loc/loc/graph/{BF20E8AA-39D9-4E51-9828-BDF2AE6202E4}.graph
/Map_3-01_LandOfChocolate/loc_str/build/PS3/pal_en/assets_rws/loc/loc/graph/{C19C5CAD-3247-43C7-819C-0B9D849C941A}.graph
/Map_3-01_LandOfChocolate/loc_str/build/PS3/pal_en/assets_rws/loc/loc/graph/{F1DEDAF0-A2A2-41DC-BDDF-918427072291}.graph
/Map_3-02_BartmanBegins/brt/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/brt/brt/graph/{0BB05DDA-1B52-4B70-9466-60A46FC9B988}.graph
/Map_3-02_BartmanBegins/brt/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/brt/brt/graph/{124C0E2D-B403-43A0-8F76-92CB34045D57}.graph
/Map_3-02_BartmanBegins/brt/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/brt/brt/graph/{56D67643-1816-4302-B5F0-D7E4CD5597CB}.graph
/Map_3-02_BartmanBegins/brt/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/brt/brt/graph/{7DB22B86-52D1-453F-8B3B-EB1BF66FBF9E}.graph
/Map_3-02_BartmanBegins/brt/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/brt/brt/graph/{801EFED7-D67B-4EE9-9C88-317D163757EF}.graph
/Map_3-02_BartmanBegins/brt/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/brt/brt/graph/{8F8E20B1-2B0B-4B49-9FBB-50AD98F6D320}.graph
/Map_3-02_BartmanBegins/brt/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/brt/brt/graph/{930CC5FC-8A0C-446D-A097-9B84B7E5A0FC}.graph
/Map_3-02_BartmanBegins/brt/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/brt/brt/graph/{C82F378A-9D42-4672-8893-03B38E9706D5}.graph
/Map_3-02_BartmanBegins/brt/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/brt/brt/graph/{E7506A2D-1E36-47A7-BB21-8B921B39136D}.graph
/Map_3-02_BartmanBegins/brt/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/brt/brt/graph/{ED45B768-2971-4F86-8CC8-FD97C6709522}.graph
/Map_3-03_HungryHungryHomer/eighty_bites/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{01EA206F-2999-4407-A387-CCA2819FFCED}.graph
/Map_3-03_HungryHungryHomer/eighty_bites/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{1652FAD2-4DA5-4230-B160-6F356D433DB8}.graph
/Map_3-03_HungryHungryHomer/eighty_bites/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{31A9A821-7763-4318-9B50-95A18B7D72BC}.graph
/Map_3-03_HungryHungryHomer/eighty_bites/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{383AC57D-96EB-4C59-B9DC-19CFA1CB1ECB}.graph
/Map_3-03_HungryHungryHomer/eighty_bites/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{3D40C8B3-96AE-486E-9BC1-04DEC8993A81}.graph
/Map_3-03_HungryHungryHomer/eighty_bites/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{47FCE28E-588C-4385-8BF8-C499AEAAA7C3}.graph
/Map_3-03_HungryHungryHomer/eighty_bites/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{56351C70-E212-422F-9171-A267F28E8B92}.graph
/Map_3-03_HungryHungryHomer/eighty_bites/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{6186D3BE-27B8-4CE4-85E2-72D82DCD8936}.graph
/Map_3-03_HungryHungryHomer/eighty_bites/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{750A2F23-D00F-4FB4-9D1B-E5D767F9DD1E}.graph
/Map_3-03_HungryHungryHomer/eighty_bites/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{78D172D3-3D00-49D2-8053-C31FB779A668}.graph
/Map_3-03_HungryHungryHomer/eighty_bites/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{7A67340B-D2E7-4AAA-ABEC-2526FB9F2E64}.graph
/Map_3-03_HungryHungryHomer/eighty_bites/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{89C8341D-9106-4C13-84A6-13A91775F2A0}.graph
/Map_3-03_HungryHungryHomer/eighty_bites/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{8B918ED0-BFA6-4D5A-9B14-9B6A7BC85F83}.graph
/Map_3-03_HungryHungryHomer/eighty_bites/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{8D33F614-9BDC-4682-A485-E4AB603FE43E}.graph
/Map_3-03_HungryHungryHomer/eighty_bites/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{96E057A6-CBA2-45ED-A5DB-820CF1BD2B17}.graph
/Map_3-03_HungryHungryHomer/eighty_bites/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{BBD02648-E59F-4CBA-B3FE-59B655FAE899}.graph
/Map_3-03_HungryHungryHomer/eighty_bites/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{CDF44901-F53D-496C-A879-306393428F54}.graph
/Map_3-03_HungryHungryHomer/eighty_bites/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{CFE09DD4-5B51-465B-8E98-BF44DC95BD21}.graph
/Map_3-03_HungryHungryHomer/eighty_bites/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{DC2CFEEA-CA0D-408A-BFD1-BEBF3B50301A}.graph
/Map_3-03_HungryHungryHomer/eighty_bites/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{E9A8529A-D5BA-407F-B172-10EF925E4E47}.graph
/Map_3-03_HungryHungryHomer/eighty_bites/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{FFCA8C0B-2286-4097-BEE6-C964891166F7}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{072F448F-69CA-46D1-BC3F-60D939628D4E}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{0B3F6379-3783-4EF3-925A-735B92693A29}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{13DCCE0E-B003-4ACA-B8C4-FCD51CF5F141}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{1CA319F9-06F6-4221-A202-CE55381833CF}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{1F3F24B7-DCE1-46C7-ACD7-6519AB09E0AE}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{244BBEAA-1616-44B0-9C3D-75208545E42F}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{390352F0-4D24-4E38-B95B-21FF566AC9A8}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{3F606F60-E3DB-4CF4-A425-9E689076D6FE}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{5270860A-3490-4D8D-B506-8CC8C69ABA26}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{62F7079B-41CE-48D7-B136-6D2936E31709}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{63559CD3-0357-4CF8-A3DF-CA4268EA9854}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{657E6B1B-ED17-48D8-B025-16C75F61A341}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{6E37C51F-24EE-4146-8355-6A0A17FE42CC}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{6EEC6404-9146-42EB-8B73-C23512391116}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{70595FD2-37A3-461C-B585-E04154E97AF9}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{727E1AD5-9E94-4DBE-A01B-267A1A44F0D8}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{8066B0B2-65B8-41A7-835E-2F24BF592EE0}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{80FC1984-E44E-447D-8689-7BC4269537F1}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{8798B12E-4E4B-4C18-93A8-55931BC7BE12}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{88B076A7-8266-4C08-A4A8-D119850A2C87}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{A31A87D5-8164-4ED6-B2BE-1E2C4FF3F575}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{AA1BB141-A750-4BEA-BFCB-9FD9845AFE43}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{C61D5842-7F85-415B-A0D7-8695077B9BFD}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{CB137142-16C1-47DA-BD35-43BD6AEDAC4F}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{D97D4DAB-6401-47ED-BB08-15006C54C038}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{DC5D6B43-C80A-4385-8C32-1CF0BD20CD1E}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{DFC49D4B-E62C-4426-AEE9-A886B745C120}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{E13DF562-0E96-494E-83B1-515F8004BD4E}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{FAAB25F7-C61D-4015-A3A6-B872287DF5E2}.graph
/Map_3-03_HungryHungryHomer/eighty_bites_str/build/PS3/pal_en/assets_rws/eighty_bites/eighty_bites/graph/{FE3A4231-9646-4B79-8E92-8B45369517F0}.graph
/Map_3-04_TreeHugger/tree_hugger/Challenge_Mode/ChallengeMode_Design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{1B8CB112-2E0B-472B-9C87-94FCE5C0C2C8}.graph
/Map_3-04_TreeHugger/tree_hugger/Challenge_Mode/ChallengeMode_Design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{1E32675D-6E01-44C8-B712-8CE7E25F7BB3}.graph
/Map_3-04_TreeHugger/tree_hugger/Challenge_Mode/ChallengeMode_Design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{398D3E26-D337-4353-BDDA-F670CBB3C465}.graph
/Map_3-04_TreeHugger/tree_hugger/Challenge_Mode/ChallengeMode_Design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{6F893FF0-4F1E-4512-A9B9-6DB4845E72D6}.graph
/Map_3-04_TreeHugger/tree_hugger/Challenge_Mode/ChallengeMode_Design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{760EF3D7-7D2B-4F71-8349-3B8290675C68}.graph
/Map_3-04_TreeHugger/tree_hugger/Challenge_Mode/ChallengeMode_Design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{BC494C07-11A9-4AC7-80CC-52E631C15E04}.graph
/Map_3-04_TreeHugger/tree_hugger/Challenge_Mode/ChallengeMode_Design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{BE3D1D4F-4181-4C51-911A-A90063D9C23D}.graph
/Map_3-04_TreeHugger/tree_hugger/Challenge_Mode/ChallengeMode_Design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{D0AFC5A2-AED7-4542-A4DB-785FECE71612}.graph
/Map_3-04_TreeHugger/tree_hugger/Challenge_Mode/ChallengeMode_Design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{F755388B-4B38-4A77-A9B6-4CE7AAB3C4EF}.graph
/Map_3-04_TreeHugger/tree_hugger/Story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{11FC0489-3384-4762-B410-94B0126C7A64}.graph
/Map_3-04_TreeHugger/tree_hugger/Story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{28330273-8970-473D-AEB8-2186709B6308}.graph
/Map_3-04_TreeHugger/tree_hugger/Story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{2DD563B7-AAB1-441A-83F1-3D4416B371FA}.graph
/Map_3-04_TreeHugger/tree_hugger/Story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{3D4031B2-8382-446F-BE1A-82C857A578F7}.graph
/Map_3-04_TreeHugger/tree_hugger/Story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{46E83870-BB65-4F08-ABA0-FC110B07987F}.graph
/Map_3-04_TreeHugger/tree_hugger/Story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{4C2CB18E-D568-4D7A-9A1E-E07A0EA4323A}.graph
/Map_3-04_TreeHugger/tree_hugger/Story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{4C8CFC66-6444-47B2-BF90-D45BE236A679}.graph
/Map_3-04_TreeHugger/tree_hugger/Story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{54D4DEDD-3FF3-498A-8B7B-3746C21E4829}.graph
/Map_3-04_TreeHugger/tree_hugger/Story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{863BB9B9-C8DD-4F8B-87BD-7353A9CAC88D}.graph
/Map_3-04_TreeHugger/tree_hugger/Story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{9CEBAFAD-0423-4546-B0AB-11167A23A3A3}.graph
/Map_3-04_TreeHugger/tree_hugger/Story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{A6B3E8C0-8A64-49CD-AD87-3CF2415AA5F4}.graph
/Map_3-04_TreeHugger/tree_hugger/Story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{AB4BC3E9-52DE-4413-9B81-2DFE80E720BE}.graph
/Map_3-04_TreeHugger/tree_hugger/Story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{ABAB00E4-6E7D-451B-AB5A-5BA741D469AA}.graph
/Map_3-04_TreeHugger/tree_hugger/Story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{ADBDDE21-205C-40A3-AB18-09EF7CB1D761}.graph
/Map_3-04_TreeHugger/tree_hugger/Story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{EC69E523-10A6-483B-A07D-5A3381987C9E}.graph
/Map_3-04_TreeHugger/tree_hugger/Story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{F8D12F9D-0CCA-4D5C-86F0-806CA5A22E3E}.graph
/Map_3-04_TreeHugger/tree_hugger_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{055CCAFF-D819-46BC-ADD0-9D9C0306A2AB}.graph
/Map_3-04_TreeHugger/tree_hugger_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{05A874F4-6BAB-48A9-9668-8BB632EBED56}.graph
/Map_3-04_TreeHugger/tree_hugger_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{161F34AE-8F96-46BA-939D-DE9486863318}.graph
/Map_3-04_TreeHugger/tree_hugger_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{6096E41C-855D-4A1A-8691-5922A91CF9F4}.graph
/Map_3-04_TreeHugger/tree_hugger_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{725A2A88-5D4F-4B1F-B40D-AC20B9E91E43}.graph
/Map_3-04_TreeHugger/tree_hugger_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{7B7B29CC-163D-413B-A10B-96BED3275FF2}.graph
/Map_3-04_TreeHugger/tree_hugger_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{8078FC1F-F516-4DBE-B1B0-73463A3B7FBD}.graph
/Map_3-04_TreeHugger/tree_hugger_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{85177234-D0D0-4C79-9AE6-B276560CB93F}.graph
/Map_3-04_TreeHugger/tree_hugger_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{8579449E-9258-428B-888C-2B16D2C7E0E8}.graph
/Map_3-04_TreeHugger/tree_hugger_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{9170888F-4AD3-4C07-8863-9748CC7B943D}.graph
/Map_3-04_TreeHugger/tree_hugger_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{9E22F613-BDEB-49E5-A5A8-85C5FAECF7ED}.graph
/Map_3-04_TreeHugger/tree_hugger_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{9E5A3C7F-1107-49DD-BDC1-7166714752E5}.graph
/Map_3-04_TreeHugger/tree_hugger_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{A8678105-C7AF-41CC-99C6-1F05E92A6312}.graph
/Map_3-04_TreeHugger/tree_hugger_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{BBDD3D89-33C6-4BFF-929E-A83F004B68C1}.graph
/Map_3-04_TreeHugger/tree_hugger_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{BC5C811E-845A-44FC-8C04-C80743CE3A37}.graph
/Map_3-04_TreeHugger/tree_hugger_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{E1C2044A-406D-453C-900D-B8A8A15071E5}.graph
/Map_3-04_TreeHugger/tree_hugger_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{F600D9CE-DD69-4D44-AF9E-95D5196C3CA9}.graph
/Map_3-04_TreeHugger/tree_hugger_str/build/PS3/pal_en/assets_rws/tree_hugger/tree_hugger/graph/{F82635F7-E8FC-4210-82DE-79B98305CD72}.graph
/Map_3-05_MobRules/mob_rules/challenge_mode/challenge_mode_design_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{B90BB7AB-4CC4-46F5-A0F4-10BFD9DFBB15}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{04EC70FE-226D-4FF1-974B-53D671C663CE}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{1AD0D700-F024-4035-9763-4CF3E677B74C}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{1EAFED7F-E63D-45E7-B07B-40434DBE6726}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{3767E934-9456-4225-8B95-A348D4F86176}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{3E07D7F3-071F-418D-AA04-7B97CF959BCD}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{4649E46B-E993-4CB2-A8F7-CB5EF2F1197E}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{58D387AA-B95E-4EA4-A88A-8D05A7BDDA71}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{5DA61ECD-4857-4999-956C-567B6FDB55C1}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{5E7FF6DF-2C88-4811-96F4-C0DCFD0B789C}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{657FED6B-E9B9-48FD-838C-3EE0019F73C9}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{694EF976-3DBD-427C-BB26-EA52F9AEF8D0}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{6B9A801E-ACC3-403E-86E3-6F0BF958522F}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{6CD7C842-C0AB-489C-B9AD-4DC1D241247A}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{795E2091-88D8-4E6D-ACEA-EA6724BECA3B}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{982CC38D-7068-4E5C-B7BC-70F438CBD153}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{AF7CBF7E-0D39-4D66-9888-D18E667A0A66}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{C5E5EEA2-3AFB-46C4-B95E-33FAA47E577C}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{CD64C096-0DA5-413E-B6F7-229318E46AC2}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{DB7F5604-9A2F-4A66-B223-E1C2D6ECFFAA}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{EB21A3EF-CEA7-4729-BF05-23271E9F4480}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{F13E1818-380D-4FCC-B18A-1BB717618CB0}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{F2A700A6-85A8-415B-8ACE-376ADAB0166F}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{F571551C-B574-459C-B042-60B2ECAD2268}.graph
/Map_3-05_MobRules/mob_rules_str/build/PS3/pal_en/assets_rws/mob_rules/mob_rules/graph/{F9F98499-1AD2-4432-A800-8D4765664A3F}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{0A05335D-CFAF-41BD-B96C-EA4C2F8E0B0F}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{0AEA5FB9-A914-4EC8-8684-6886B8295925}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{147C63E9-66DB-4E59-B553-AD295B3434B3}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{2C4F4A67-B4A7-4BF0-A41F-256289D4056B}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{2C82FEAB-D1E3-4860-BAF7-6C69309D85FE}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{2E85C914-1D06-4807-8BD6-CE03FAACB432}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{32FE3BBC-3963-4989-9451-5551FDEF1237}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{33868BC6-5163-4B82-9718-23F0C69098EF}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{36FCBE47-B440-4F2D-A310-BF0AE3E976B9}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{40D5EF07-4A40-467D-92B1-A07E6D3C56C5}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{40F7E900-4668-4AFD-81D7-021066DE7385}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{4F55233E-20D3-4472-B2E2-C4F0171B7623}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{67848EC1-3349-46C8-AD07-3376FC09F319}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{67FFD7A4-A6A0-4B5F-B40D-2F370F122F2E}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{81AE6580-EE80-4BB0-B907-94C0C3608DF2}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{8708241A-A7B5-42AF-BD24-18D312824C9A}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{8838E070-785F-4C20-9143-67B335D69AB0}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{8DAADC85-58E6-4A52-A22E-E43717BE7556}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{91CD8974-FB1B-4785-800C-BCDBB39268F2}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{AF91357B-E35E-413E-A3D0-38A80E18D511}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{B6B9A0AC-BB8E-4FFC-8B87-86376DF9E68C}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{B9F5698A-15F9-470F-A512-A3DD84C0B9A3}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{BC4FD77F-B868-45EA-8809-BEFDE6F42FF7}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{C29BFC6B-3FF2-40BB-92ED-E4E6D390EE77}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{C4484B1E-C884-4BFF-B58F-C263B2D4F4CD}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{C77D76EC-FF58-4C97-8407-B9CF24BE6D9B}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{CB675412-04E5-4458-BFFA-9EBC7E71A829}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{CDD9EEC9-7B61-423D-8F4F-03DAD71EC905}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{CF17318F-5DB9-4959-AA87-271B3B5FA6D1}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{D4C9C348-E0B6-42C7-80AF-EFDC3070D28D}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{DBE4CD6A-B4F7-4AC9-AE70-5C1CF4119458}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{E32A1DA1-02BD-47B7-8D1C-30F3FDD1838E}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{E3DBB712-FD9F-4307-81AE-B59C68C45659}.graph
/Map_3-06_EnterTheCheatrix/cheater/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{FAFEFCD3-D915-4F29-88F2-A5333A7B1AD3}.graph
/Map_3-06_EnterTheCheatrix/cheater_str/build/PS3/pal_en/assets_rws/cheater/cheater/graph/{035E5271-7B3F-48C7-BF7C-07D2149540D9}.graph
/Map_3-07_DayOfTheDolphin/dayofthedolphins/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/dayofthedolphins/dayofthedolphins/graph/{65F95751-7815-46FD-B6D9-368D3C9D9723}.graph
/Map_3-07_DayOfTheDolphin/dayofthedolphins/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/dayofthedolphins/dayofthedolphins/graph/{8FB2E7B8-E3AA-43EE-82DB-0C0E276B1068}.graph
/Map_3-07_DayOfTheDolphin/dayofthedolphins_str/build/PS3/pal_en/assets_rws/dayofthedolphins/dayofthedolphins/graph/{48CD4E71-B8FF-46AF-AD96-42546E870751}.graph
/Map_3-08_TheColossalDonut/colossaldonut/challenge_mode/challenge_mode_design_str/build/PS3/pal_en/assets_rws/colossaldonut/colossaldonut/graph/{3C0FF1CC-106D-474D-A0B3-27DACFAD5E45}.graph
/Map_3-08_TheColossalDonut/colossaldonut/story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/colossaldonut/colossaldonut/graph/{162A2F92-7426-4DEF-AF9F-F40620D3437F}.graph
/Map_3-08_TheColossalDonut/colossaldonut/story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/colossaldonut/colossaldonut/graph/{32D887AF-DE7B-41FB-A904-BE11E2A6FA32}.graph
/Map_3-08_TheColossalDonut/colossaldonut/story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/colossaldonut/colossaldonut/graph/{3C0FF1CC-106D-474D-A0B3-27DACFAD5E45}.graph
/Map_3-08_TheColossalDonut/colossaldonut/story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/colossaldonut/colossaldonut/graph/{728935E2-34A2-4513-97CF-F441E8FAB7A0}.graph
/Map_3-08_TheColossalDonut/colossaldonut/story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/colossaldonut/colossaldonut/graph/{76B820CB-FBE1-4401-AE7B-88DECD694720}.graph
/Map_3-08_TheColossalDonut/colossaldonut/story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/colossaldonut/colossaldonut/graph/{85715971-C8E5-4B06-8A71-97E8476E541B}.graph
/Map_3-08_TheColossalDonut/colossaldonut/story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/colossaldonut/colossaldonut/graph/{91D4EC94-1671-44F4-A8EA-BF16D47AA21F}.graph
/Map_3-08_TheColossalDonut/colossaldonut/story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/colossaldonut/colossaldonut/graph/{97CFA185-A182-4F83-B135-48B46FF6E115}.graph
/Map_3-08_TheColossalDonut/colossaldonut/story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/colossaldonut/colossaldonut/graph/{BEF39AD0-787D-464F-A2EB-292284926794}.graph
/Map_3-09_Invasion/dayspringfieldstoodstill/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/dayspringfieldstoodstill/dayspringfieldstoodstill/graph/{1ACD1E86-65B4-4D46-8E35-2B7E065D311A}.graph
/Map_3-09_Invasion/dayspringfieldstoodstill/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/dayspringfieldstoodstill/dayspringfieldstoodstill/graph/{259F0C11-17CE-4256-9419-A5900FB1624D}.graph
/Map_3-09_Invasion/dayspringfieldstoodstill/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/dayspringfieldstoodstill/dayspringfieldstoodstill/graph/{27B48FD6-C150-4188-A7DA-014775C56BF1}.graph
/Map_3-09_Invasion/dayspringfieldstoodstill/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/dayspringfieldstoodstill/dayspringfieldstoodstill/graph/{77BFDFEF-23E7-4C49-BB20-0A37A2F89270}.graph
/Map_3-09_Invasion/dayspringfieldstoodstill/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/dayspringfieldstoodstill/dayspringfieldstoodstill/graph/{87F89FAD-F940-414E-A8C8-22A17CF0DD13}.graph
/Map_3-09_Invasion/dayspringfieldstoodstill/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/dayspringfieldstoodstill/dayspringfieldstoodstill/graph/{8C23C552-738C-43D1-B9C5-557E273C872A}.graph
/Map_3-09_Invasion/dayspringfieldstoodstill/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/dayspringfieldstoodstill/dayspringfieldstoodstill/graph/{A4F74C96-7111-4DC9-90BF-6851836E0426}.graph
/Map_3-09_Invasion/dayspringfieldstoodstill/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/dayspringfieldstoodstill/dayspringfieldstoodstill/graph/{B8BE19F9-3F2D-405F-9DE1-739477A89B0E}.graph
/Map_3-09_Invasion/dayspringfieldstoodstill/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/dayspringfieldstoodstill/dayspringfieldstoodstill/graph/{BDD82093-366C-41F2-995C-3343018BB50D}.graph
/Map_3-09_Invasion/dayspringfieldstoodstill/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/dayspringfieldstoodstill/dayspringfieldstoodstill/graph/{CD43FF05-AA47-43C2-81F3-8D34BA9F8D9C}.graph
/Map_3-09_Invasion/dayspringfieldstoodstill/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/dayspringfieldstoodstill/dayspringfieldstoodstill/graph/{E55C9741-9A01-4B97-955D-B23827AD3EE2}.graph
/Map_3-09_Invasion/dayspringfieldstoodstill/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/dayspringfieldstoodstill/dayspringfieldstoodstill/graph/{FB4C2577-3AD1-4D0A-A636-4A1862D49193}.graph
/Map_3-09_Invasion/dayspringfieldstoodstill/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/dayspringfieldstoodstill/dayspringfieldstoodstill/graph/{FE12EEEC-0F95-4915-816C-53347D1F7BD0}.graph
/Map_3-10_BargainBin/bargainbin/Story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/bargainbin/bargainbin/graph/{9DF6B18A-41AA-444F-8EF3-6849FE9792A3}.graph
/Map_3-10_BargainBin/bargainbin/Story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/bargainbin/bargainbin/graph/{E33143CD-C649-4FF9-8ECB-62AA3F8D269C}.graph
/Map_3-10_BargainBin/bargainbin/Story_mode/Story_mode_design_str/build/PS3/pal_en/assets_rws/bargainbin/bargainbin/graph/{FDBFAF68-C088-46B5-8AD3-A243190A7E20}.graph
/Map_3-10_BargainBin/bargainbin_str/build/PS3/pal_en/assets_rws/bargainbin/bargainbin/graph/{1B8CA733-C808-4E52-AB8A-3EFC93B01FEE}.graph
/Map_3-10_BargainBin/bargainbin_str/build/PS3/pal_en/assets_rws/bargainbin/bargainbin/graph/{3BB2A55D-898E-446B-99DE-16F1F3811E2B}.graph
/Map_3-10_BargainBin/bargainbin_str/build/PS3/pal_en/assets_rws/bargainbin/bargainbin/graph/{904B4A51-53D4-4A1B-BB10-85FF01C0A8BD}.graph
/Map_3-11_NeverQuest/neverquest/challenge_mode/challenge_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{EA9A72BC-A7E4-49F3-AFAB-3C637AFB3A03}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{004EB306-CEEA-4CAE-850A-EADFC8E95ADB}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{08B220E2-D2D3-46D5-AF3D-C20C34F5BEEA}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{0A94E1EE-19F8-4665-91E9-A6424A7AF307}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{0C6478DD-7A2E-4829-BB32-59053D9CF275}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{108E322E-D935-47F8-8834-950AFB4FA6B1}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{16257B73-A370-4021-81F5-D44357DD9CBC}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{1690126A-92D8-4AE2-951D-87B20E5518FE}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{180BC7ED-EBA5-4DFC-A365-B511069F55B7}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{1C1746DE-BFD1-4635-B073-4891CC71B28E}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{1D9464D1-E54A-4DEF-AC61-443CA0C34F30}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{1EF5DFF1-746D-4F52-97B8-9CE50B192152}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{22ADC985-41ED-4EFB-8F52-C2B586CD702B}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{294F5F58-418E-48A4-B6C1-EF0978C5F711}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{2992FB8C-77BA-4D00-9F6C-5D4398C4CE28}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{29AFDDDA-D85A-4870-AD16-8ECCA1FFB6FD}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{33E8FEAD-80B8-4B1B-AC94-4C1E01F801A3}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{3AA7C41D-028A-4110-AA34-10BD3D4455A1}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{3C2AC297-EA44-4A47-9F06-D495E7616640}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{3D718B7E-F266-43D4-9D98-3B3DE4EFBBA8}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{40585AA1-F61D-41D1-8EDA-6B6C986A6EC6}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{43D3BFEE-B756-4552-8418-7AB2F9459061}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{43E39CF2-D512-4E98-852F-E90D457BFEB5}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{4D350227-3E78-425B-BD2A-73F1F61E61E1}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{50659F60-C54B-4E6B-B39F-475EC940B549}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{54F4BA49-34AF-4DCB-AB35-83C7411BA7AA}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{573DEFF9-BCB0-4D02-AA3C-1DC211C8343E}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{57A57C67-4EFF-4C07-B4B0-C85C003AB439}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{5DD0217F-42CF-46DF-B0D3-2BAACFB75EC1}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{5F3F2544-6C90-4B22-B873-333A96E1207D}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{6388AF7D-3163-4C67-BC3A-FE4F0EE2A223}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{662DD360-5F7E-4CF5-BDD4-8AF41CCF4BBD}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{7C3C554C-81F6-415B-B7C2-1D88E9662A2C}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{86B3F4C3-151E-4131-B024-B60FEDA82ADF}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{902320E1-34C8-46A0-B5B9-11C578E463DD}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{924B5E01-C2CA-4B0B-BA3A-A16AAC9AF433}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{9A30A3F7-AB42-42C5-BB36-8DB38BC8662E}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{9D7519CD-3B75-41A5-94A9-AF4D26DDE3C5}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{A1695E6B-CD6B-4391-8057-80F6C46DE210}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{A73CA4DB-6007-4C81-9D9B-D7F873ACF325}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{A8EF9617-2A3F-4530-8AED-D24D5BDF9D3D}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{AB497ECA-1012-428E-B362-36A4AB02F84E}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{ACC6A26F-104F-4B2C-BE26-7CEDE0B8FF47}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{AE5FE8FC-AD71-41D1-99A6-72FBD61243CE}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{B14117D9-7232-416D-BC06-53EC42D62E19}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{B44666AF-A1F0-4917-A9A9-9EC22C276CFB}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{B7A950AC-4834-4EF3-87C3-6C8FF07AFD68}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{BC62D3D1-39C1-454B-B001-1AC075432D74}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{BE4CF8E9-334C-4517-821E-D4CB6832FFC5}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{C0E06B08-E34E-428A-99DC-B5AB63227066}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{C1995BB9-C2BC-49D7-83D9-549D2AAEC9FB}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{C30216AC-C14B-4CBF-84CD-CFB91C7065FC}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{C66F84C7-F923-4713-9BA7-9CF6FBFCBF1E}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{D26653D8-E5B3-456A-A88E-7EA58781158B}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{D4E0F9F4-A1A1-4A69-83D3-1A8160DBC77E}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{D5B420E3-B78E-4B93-98B4-0FE5AE61D8A6}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{DF904BAB-995F-4B78-B0C6-B490F782E0D0}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{E00E2737-36F9-44A3-97E1-FB528654F5F8}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{E4954E79-2582-49D1-A5D3-3B65B572010C}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{E4F4A0B4-D4ED-46FE-A812-A87A8E36EA46}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{ECA499C7-8D16-499E-940B-E8150E69F01C}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{F08C045E-46D1-48AF-96D7-0EBD8EE70EA6}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{F442ED72-E28D-45D3-87DB-B2541A507482}.graph
/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/neverquest/neverquest/graph/{FB9A44EE-7AF7-4646-8548-626F317E8BAA}.graph
/Map_3-12_GrandTheftScratchy/grand_theft_scratchy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/grand_theft_scratchy/grand_theft_scratchy/graph/{024FB6C9-FB01-44A7-A23C-1FCD4C0C02A0}.graph
/Map_3-12_GrandTheftScratchy/grand_theft_scratchy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/grand_theft_scratchy/grand_theft_scratchy/graph/{0B33178A-FCD6-4D48-A051-B7599AAB2C91}.graph
/Map_3-12_GrandTheftScratchy/grand_theft_scratchy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/grand_theft_scratchy/grand_theft_scratchy/graph/{1CA92483-60EF-4440-B7F0-85E3424093C5}.graph
/Map_3-12_GrandTheftScratchy/grand_theft_scratchy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/grand_theft_scratchy/grand_theft_scratchy/graph/{202E1FE3-94A5-474A-B410-BAC6E4A89A0A}.graph
/Map_3-12_GrandTheftScratchy/grand_theft_scratchy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/grand_theft_scratchy/grand_theft_scratchy/graph/{21ED3D4E-8117-4A7A-ABFA-B5EA7B52693D}.graph
/Map_3-12_GrandTheftScratchy/grand_theft_scratchy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/grand_theft_scratchy/grand_theft_scratchy/graph/{23874F39-698A-42F5-BA18-0941CE68DA67}.graph
/Map_3-12_GrandTheftScratchy/grand_theft_scratchy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/grand_theft_scratchy/grand_theft_scratchy/graph/{3ED35E14-DB9A-4E4A-A42A-224B5CD51CB7}.graph
/Map_3-12_GrandTheftScratchy/grand_theft_scratchy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/grand_theft_scratchy/grand_theft_scratchy/graph/{58AF6383-77A7-426A-8466-EF022D51252A}.graph
/Map_3-12_GrandTheftScratchy/grand_theft_scratchy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/grand_theft_scratchy/grand_theft_scratchy/graph/{6402AF8F-3E8B-4AD0-BA1E-4EA66C92B3D6}.graph
/Map_3-12_GrandTheftScratchy/grand_theft_scratchy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/grand_theft_scratchy/grand_theft_scratchy/graph/{6A420051-402E-4E59-9680-E28BEE2F01EF}.graph
/Map_3-12_GrandTheftScratchy/grand_theft_scratchy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/grand_theft_scratchy/grand_theft_scratchy/graph/{8391CBC4-BBAB-4101-B356-5005EF6A298D}.graph
/Map_3-12_GrandTheftScratchy/grand_theft_scratchy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/grand_theft_scratchy/grand_theft_scratchy/graph/{84115479-CAC0-46EB-AF69-4296DDCE1000}.graph
/Map_3-12_GrandTheftScratchy/grand_theft_scratchy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/grand_theft_scratchy/grand_theft_scratchy/graph/{9C1D61CD-2EB3-44AD-97DB-1E19775C82D0}.graph
/Map_3-12_GrandTheftScratchy/grand_theft_scratchy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/grand_theft_scratchy/grand_theft_scratchy/graph/{9D87B149-85C1-4F33-A885-CBB2D1B53975}.graph
/Map_3-12_GrandTheftScratchy/grand_theft_scratchy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/grand_theft_scratchy/grand_theft_scratchy/graph/{B1DAA28C-9E79-4452-801C-327CB3856742}.graph
/Map_3-12_GrandTheftScratchy/grand_theft_scratchy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/grand_theft_scratchy/grand_theft_scratchy/graph/{B60C2026-46EF-46BB-913A-2D2985CA3123}.graph
/Map_3-12_GrandTheftScratchy/grand_theft_scratchy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/grand_theft_scratchy/grand_theft_scratchy/graph/{D62502C1-434F-4700-9D2B-363C21C70BE7}.graph
/Map_3-12_GrandTheftScratchy/grand_theft_scratchy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/grand_theft_scratchy/grand_theft_scratchy/graph/{D73BDDB4-66F3-474A-849B-928AD1FC7BB2}.graph
/Map_3-12_GrandTheftScratchy/grand_theft_scratchy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/grand_theft_scratchy/grand_theft_scratchy/graph/{F1A2ED80-03B1-4252-8CAF-996A9CD5087C}.graph
/Map_3-12_GrandTheftScratchy/grand_theft_scratchy_str/build/PS3/pal_en/assets_rws/grand_theft_scratchy/grand_theft_scratchy/graph/{F09007EA-151E-4DAB-BC72-2E07E1CC2311}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone01_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{06E00604-E095-4D09-B8F3-4B52EDCDF94D}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone01_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{1953781D-DE4B-407F-86E1-D49C3E78C829}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone01_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{6505A7E5-1B93-4822-8685-C2C60102DACE}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone01_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{727B67DA-51F2-41D0-A6B5-6FFEA5B131B0}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone01_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{AE162078-295B-4B83-A96B-B2BAD3FAAAC6}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone01_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{D2060B6E-FBC1-483A-A345-679EC7FEA7D6}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone01_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{DA4E4187-1F66-44E7-9CF2-8ABD0FD6847C}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone01_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{F59E7704-A84E-4649-8693-37A8FBD50611}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone02_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{35F4E7AB-601A-4679-BAC1-96A0FCDC01FB}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone02_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{557A62AF-D97B-485C-87D6-73AE865EC225}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone02_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{6FD760FB-6FD1-4148-9176-C3A26E576529}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone02_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{7F3C2AA1-0B59-47D2-8F70-D751A80E6702}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone02_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{CCC7D965-FC16-458D-8865-629DF6215D3B}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone02_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{D1281096-CA70-47AF-B963-4B242BDE018D}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone03_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{1B1C4986-6879-4BE0-9CAA-07523FDEB3CF}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone03_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{261EF12E-E17E-4552-AC47-B7427B960CDC}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone03_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{2DFB7675-CE13-4EEC-AFB6-A12E10B96B0B}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone03_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{37E79D04-B6FB-4BA7-9C36-9AB9ED8BF0E9}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone03_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{39A3DD33-90F0-46D6-9BAA-B5BDB749432D}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone03_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{775856BD-04BD-46DF-86CB-C0F25764A8E3}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone03_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{807B2D4F-D726-4B3B-852F-52606A872419}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone03_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{8B93153C-2F3E-44CC-94F9-215D1E18805E}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone03_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{BAA6F3B2-E0FA-4A4D-9704-6696A4A85B5C}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone03_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{BFE83990-8E70-4B5D-A1C1-41E7D1C510F6}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone03_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{CD52DFA9-1062-4EA6-B86F-4246589B950E}.graph
/Map_3-13_MedalOfHomer/medal_of_homer/story_mode/zone03_str/build/PS3/pal_en/assets_rws/medal_of_homer/medal_of_homer/graph/{E2852B96-6529-4BF3-BD1B-8601DD155CFB}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{0EBD8240-72C8-4C9D-8D5F-8A092509F5B7}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{151A0D38-4D84-497D-BE4D-ECC2DBA73EF6}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{15CB9F2F-1BA6-4631-BBA3-C08F6AE1BDE1}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{26E576D3-6844-48B4-8F73-3D5B9B30940E}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{2DC43DEB-F4C7-460D-AE80-C5A033F297C4}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{3A508EF7-6497-44F9-BBF8-D90840BA3531}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{46A8EC46-3C30-443E-BC6B-DEB3A953F516}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{52144DFE-F2A4-4C2B-9F5D-B695BD356602}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{7834FD61-7FCA-4678-BF46-D601C75FF3CD}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{8ACA8CC4-5AF5-47CC-B8A4-DAE7C097373A}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{95609D82-CBBD-4385-AA1A-C301EBE0921B}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{9CC873AE-D0AE-4E70-A602-514F9FB6DBC0}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{9F677BC7-039D-4086-84A3-105C4E997E46}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{B1CD31CB-DF63-46C4-86B6-FBDE428CF779}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{B7D5566A-DA5F-44D7-9FB9-D1EA93A9E5BD}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{BD58D09D-FA8D-4EEF-A03D-98E990EE1F1E}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{C761F065-B165-42EA-8714-EE43816C4DA9}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{CBDEBCA9-A27B-4F9C-896A-8BC44FD319A9}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{CFDA05F6-1BA9-4425-AAF9-BE650D3862CD}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{DF722624-24A7-4754-A94E-A4522BF6E720}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{E22380CD-91FB-49AB-A3B8-F819CEC5063C}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{EE14CDF1-2ECE-4281-AB23-C4735421AACD}.graph
/Map_3-14_BigSuperHappy/bigsuperhappy_str/build/PS3/pal_en/assets_rws/bigsuperhappy/bigsuperhappy/graph/{398C7F2A-6B67-4D83-BF3D-27B20E16F656}.graph
/Map_3-15_Rhymes/rhymes/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{665564E6-EEFC-42AA-9286-40DED903720D}.graph
/Map_3-15_Rhymes/rhymes/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{87C1EEAF-0A42-4E4D-AB9A-41DAE57BFACF}.graph
/Map_3-15_Rhymes/rhymes/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{95B29A13-76FA-4576-B1EA-6006FD4387FC}.graph
/Map_3-15_Rhymes/rhymes/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{97DB58C2-3CA4-467F-BD2E-DCCAF0D5EF41}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{1F45E3D6-A4B3-4426-B7DC-4AEE9251F1EE}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{21A36A43-C979-43C5-8D01-8DD7C7B2F98C}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{4BB1D6C1-DB11-4871-B437-FC7D86B8F49B}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{56B142DB-73A3-4CC3-9938-E64E654CE08A}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{5E83EB48-FB3C-489C-B05A-52068E6FE40E}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{680014A6-B3E0-4FFB-9D5C-69F3107F7260}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{78B1ADA4-2F70-49B7-A4DF-9E06F8E4BBB0}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{8ECCBD9A-4954-4AA2-877C-A75C1B0AA406}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{8F1A94BC-0C36-493C-9E56-F9C30D3C4B4F}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{9037D87C-0AEC-4C97-8F81-D314D9AE67B8}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{98FBAF8C-FB1D-45A1-99C1-AB4CB9797C61}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{B078B413-82D0-4281-992D-5660A1DE18B7}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{B27705BF-9978-4110-A484-C30ABE73CB7B}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{BADBDB3A-8547-404F-9092-F0E41E0E5CC2}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{C9BFC654-890E-42E9-887F-DD8156EE873A}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{CADE26D3-783E-4D6F-B829-EAB9A25EEB2C}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{DE9E13B8-500A-4B3D-B9DD-718CB6843C47}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{E31D4F5E-FAEA-42C2-AAF4-6AA885774C24}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{EC85F95D-076E-4385-B0AE-516DF7561512}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{EDBA9848-E021-47A6-8E77-58A1BACAD91D}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{F21F8ACE-745A-4F26-8556-06F670BE221C}.graph
/Map_3-15_Rhymes/rhymes_str/build/PS3/pal_en/assets_rws/rhymes/rhymes/graph/{F7994E40-FC79-4CC0-A329-F8410F8BA08A}.graph
/Map_3-16_MeetThyPlayer/meetthyplayer/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/meetthyplayer/meetthyplayer/graph/{191AEB7E-1B24-47A4-B4BA-4A07D33EBC59}.graph
/Map_3-16_MeetThyPlayer/meetthyplayer/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/meetthyplayer/meetthyplayer/graph/{1E0758D2-FA51-49C9-8FF9-6D6367865512}.graph
/Map_3-16_MeetThyPlayer/meetthyplayer/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/meetthyplayer/meetthyplayer/graph/{581B4F63-5C45-4FCB-A586-3A63C556FC4C}.graph
/Map_3-16_MeetThyPlayer/meetthyplayer/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/meetthyplayer/meetthyplayer/graph/{AB6AFF6B-8B78-4F6E-AAEC-8E1B487F167B}.graph
/Map_3-16_MeetThyPlayer/meetthyplayer/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/meetthyplayer/meetthyplayer/graph/{AFF3AE47-9074-4D64-A55D-4DF1BB94C0C9}.graph
/Map_3-16_MeetThyPlayer/meetthyplayer/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/meetthyplayer/meetthyplayer/graph/{B5C98473-F547-460A-9DBA-765C638FE346}.graph
/Map_3-16_MeetThyPlayer/meetthyplayer/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/meetthyplayer/meetthyplayer/graph/{DF725584-7ECF-45FA-B29E-58FF262413AA}.graph
/Map_3-16_MeetThyPlayer/meetthyplayer/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/meetthyplayer/meetthyplayer/graph/{F14A7B13-116E-4C9E-A125-1BA94B22885C}.graph
/Map_3-16_MeetThyPlayer/meetthyplayer/story_mode/story_mode_design_str/build/PS3/pal_en/assets_rws/meetthyplayer/meetthyplayer/graph/{FE9BA724-1B5A-4A66-BE44-5C69C624F983}.graph
/Map_3-16_MeetThyPlayer/meetthyplayer/zone02_str/build/PS3/pal_en/assets_rws/meetthyplayer/meetthyplayer/graph/{214B2530-91E4-481A-B0B3-F14616F4C1A8}.graph