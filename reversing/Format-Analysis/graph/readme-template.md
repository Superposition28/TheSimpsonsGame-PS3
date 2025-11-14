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
