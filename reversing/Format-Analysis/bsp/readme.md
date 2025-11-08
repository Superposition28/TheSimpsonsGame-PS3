# File Format Documentation: .bsp (The Simpsons Game)

**Version:** 0.9
**Last Updated:** 2025-05-05
**Author(s):** [Your Name/Team based on analysis]

---

## 1. Overview

* **Format Name:** Custom Binary Space Partitioning (BSP) File
* **Common File Extension(s):** `.bsp`
* **Purpose/Domain:** 3D Game Level Data. Stores the spatial partitioning structure (BSP tree) and potentially other related level geometry data for a zone within the game. Used for efficient visibility determination, collision detection, and organizing level data.
* **Originating Application/System:** The Simpsons Game (Likely using a customized RenderWare engine)
* **Format Type:** Binary
* **General Structure:** File Header, Lump Directory, Variable Metadata Section, Main BSP Node Data (Lump 3), potentially other data lumps (Vertices, Faces, Textures, etc.), optional trailing data.

---

## 2. Identification

* **Magic Number(s) / Signature:** `0x0000000B`
    * **Offset:** `0x00`
* **Version Information:** The magic number `0x0000000B` might indicate Version 11.
    * **Location:** Offset `0x00`
    * **Data Type:** `uint32` (Big-Endian)

---

## 3. Global Properties (If Applicable)

* **Endianness:** Big-Endian
* **Character Encoding:** N/A (Primarily non-text binary data)
* **Default Alignment:** Likely 4-byte alignment for node structure components (floats, ints), but overall alignment rules are not explicitly confirmed. BSP nodes are 64 bytes.
* **Compression:** None identified in the analyzed sections.
* **Encryption:** None identified in the analyzed sections.

---

## 4. Detailed Structure

**Section: File Header**

| Offset (Hex) | Offset (Dec) | Size (Bytes) | Data Type | Endianness | Field Name       | Description                                      | Notes / Example Value                       |
| :----------- | :----------- | :----------- | :-------- | :--------- | :--------------- | :----------------------------------------------- | :------------------------------------------ |
| `0x00`       | 0            | 4            | `uint32`  | BE         | Magic/Version    | File identifier, possibly format version         | `0x0000000B` (Maybe Version 11)             |
| `0x04`       | 4            | 4            | `uint32?` | BE         | Unknown          | Unknown purpose                                  |                                             |
| `0x08`       | 8            | 4            | `uint32`  | BE         | Metadata Count   | Controls structure/count of subsequent metadata  | Varies (6 in zone01, 1 in zone13)           |
| `0x0C`       | 12           | 4            | `uint32`  | BE         | Metadata Offset  | Offset from start of file to Variable Metadata   | `0x00000070` (Example from zone01)          |

**Section: Lump Directory**

*   **Location:** Starts at `0x10`, ends at `0x6F`.
*   **Description:** Acts as a directory containing entries pointing to various data chunks ("lumps") within the file. The exact structure is not fully decoded, but entries likely contain at least an offset and a size for each lump.
*   **Known Entry:** The entry at index 3 (file offset `0x30`) points to the start (Offset) and size (Length) of the main BSP node data chunk (Lump 3). Other entries likely point to vertices, faces, textures, etc.

**Section: Variable Metadata Section**

*   **Location:** Starts at the offset specified in `Header.MetadataOffset` (e.g., `0x70`).
*   **Structure:** Varies depending on the value of `Header.MetadataCount`.
    *   If Count is 6 (e.g., zone01), this section contains 6 identical-looking 16-byte blocks marked with `PE0`. Total size 96 bytes (`0x60`).
    *   If Count is 1 (e.g., zone13), this section contains different data (example bytes: `C8 FD CE AB...`).
*   **Purpose:** Unknown, precedes the main BSP node data.

**Section: Main BSP Node Data (Lump 3)**

*   **Structure Name:** `BSPNode`
*   **Count:** Determined by `LumpDirectory[3].Length / 64`.
*   **Location:** Starts at offset `LumpDirectory[3].Offset` (e.g., `0xD0` in zone01, `0x80` in zone13).
*   **Total Size per Record:** 64 bytes.
*   **Format:** 8 Floats, 8 Integers (all Big-Endian).

| Offset (Relative) | Size (Bytes) | Data Type | Endianness | Field Name       | Description                                 | Notes / Interpretation                      |
| :---------------- | :----------- | :-------- | :--------- | :--------------- | :------------------------------------------ | :------------------------------------------ |
| `0x00`            | 4            | `float32` | BE         | Plane Normal X   | X component of the node's splitting plane normal | Unnormalized?                               |
| `0x04`            | 4            | `float32` | BE         | Plane Normal Y   | Y component of the node's splitting plane normal | Unnormalized?                               |
| `0x08`            | 4            | `float32` | BE         | Plane Normal Z   | Z component of the node's splitting plane normal | Unnormalized?                               |
| `0x0C`            | 4            | `float32` | BE         | Plane Distance   | Distance D for the plane equation Ax+By+Cz=D | Exact definition/sign needs confirmation.   |
| `0x10`            | 4            | `float32` | BE         | Unknown Float 5  | Possibly BBox or Texture Projection Data    | Purpose uncertain.                          |
| `0x14`            | 4            | `float32` | BE         | Unknown Float 6  | Possibly BBox or Texture Projection Data    | Purpose uncertain.                          |
| `0x18`            | 4            | `float32` | BE         | Unknown Float 7  | Possibly BBox or Texture Projection Data    | Purpose uncertain.                          |
| `0x1C`            | 4            | `float32` | BE         | Unknown Float 8  | Possibly BBox or Texture Projection Data    | Purpose uncertain.                          |
| `0x20`            | 4            | `int32`   | BE         | Flags?           | Integer flag field. Varies between nodes.   | Stores leaf-specific data in leaf nodes. Purpose uncertain. |
| `0x24`            | 4            | `int32`   | BE         | Child Front      | Front child node reference                  | Positive: Offset in bytes from start of Lump 3. <= 0: Leaf node indicator. |
| `0x28`            | 4            | `int32`   | BE         | Child Back       | Back child node reference                   | Positive: Offset in bytes from start of Lump 3. <= 0: Leaf node indicator. |
| `0x2C`            | 4            | `int32`   | BE         | Unknown Int 4    | Unknown integer                             | Often 0 in internal nodes. Stores leaf-specific data in leaf nodes. |
| `0x30`            | 4            | `int32`   | BE         | Unknown Int 5    | Unknown integer                             | Often 65535 (`0xFFFF`) in internal nodes. Stores leaf-specific data in leaf nodes. |
| `0x34`            | 4            | `int32`   | BE         | Unknown Int 6    | Unknown integer                             | Often -1 (`0xFFFFFFFF`) in internal nodes. Stores leaf-specific data in leaf nodes. |
| `0x38`            | 4            | `int32`   | BE         | Unknown Int 7    | Unknown integer                             | Often -2147483648 (`0x80000000`) in internal nodes. Leaf data. |
| `0x3C`            | 4            | `int32`   | BE         | Unknown Int 8    | Unknown integer                             | Often 0 in internal nodes. Stores leaf-specific data in leaf nodes. |

**Section: Trailing Data**

*   **Location:** Immediately following the last `BSPNode` in Lump 3.
*   **Presence:** Observed in some files (e.g., `zone01.bsp` has 16 extra bytes).
*   **Purpose:** Unknown.

---

## 5. Data Types Reference

*   **`float32`:** 32-bit IEEE 754 floating-point number, Big-Endian byte order.
*   **`int32`:** Signed 32-bit integer, Big-Endian byte order.
*   **`uint32`:** Unsigned 32-bit integer, Big-Endian byte order.
*   **`byte[N]`:** Fixed-size array of N bytes.
*   **`Leaf Node Data`:** When `ChildFront` and `ChildBack` are ≤0, the node is a leaf. Negative values likely encode a leaf identifier. The fields `Flags?` and `Unknown Int 4-8` then store leaf-specific data (e.g., properties like solid, empty, water, trigger, references to geometry). Exact encoding TBD. A (0, 0) child pair indicates a different type of leaf.

---

## 6. Checksums / Integrity Checks

* **Type:** None identified.
* **Location:** N/A
* **Scope:** N/A
* **Algorithm Details:** N/A

---

## 7. Known Variations / Versions

*   The primary observed variation relates to the `Header.MetadataCount` field and the subsequent Variable Metadata Section.
    *   **Count = 6** (e.g., `zone01.bsp`): Metadata section contains 6 x 16-byte 'PE0' blocks. Lump 3 starts at `0xD0`.
    *   **Count = 1** (e.g., `zone13.bsp`): Metadata section contains different, smaller data. Lump 3 starts at `0x80`.
*   **How to Differentiate:** Check the `uint32` value at offset `0x08`.

---

## 8. Analysis Tools & Methods

* **Tools Used:** Hex Editor likely used for initial inspection and data extraction. Reverse engineering tools and custom scripts (e.g., Python with `struct` module) would be useful for further decoding.
* **Methodology:** Comparison between different `.bsp` files (`zone01` vs `zone13`) to identify variable sections and fixed structures. Analysis of data patterns (floating point numbers, integers, offsets) to infer structure meaning.

---

## 9. Open Questions / Uncertainties

* Exact purpose and structure of the Lump Directory (`0x10`-`0x6F`).
* Exact purpose and structure of the Variable Metadata section (PE0 blocks / other data).
* Confirmation of plane normal normalization and exact definition of Plane Distance (Float 4).
* Purpose of BSP Node Floats 5-8 (BBox/Tex?).
* Meaning of BSP Node Int 1 (Flags?).
* Detailed encoding of leaf node data within BSP Node Ints 1, 4-8.
* Purpose of the 16 trailing bytes seen in `zone01.bsp`.
* Structure and content of other lumps presumably pointed to by the Lump Directory (Vertices, Faces, Textures, Collision, Entities, PVS data).

---

## 10. References

* Analysis notes provided in the user prompt.
* Example files: `zone01.bsp`, `zone13.bsp` from The Simpsons Game.
* [Link to any existing partial documentation.]
* [Link to related file formats.]
* [Specific file examples used for analysis.]
* [Relevant code snippets or analysis scripts.]

---

## 11. Revision History (of this document)

| Version | Date       | Author(s)    | Changes Made                                                 |
| :------ | :--------- | :----------- | :----------------------------------------------------------- |
| 0.1     | 2025-05-05 | AI Assistant | Initial draft based on provided analysis.                    |
| 0.9     | 2025-05-05 | AI Assistant | Integrated provided analysis data into template structure. Added details. |

## 12. Other:

*   **Overall Purpose:** The BSP tree structure defined in Lump 3 allows the game engine to efficiently determine visibility (PVS), perform collision detection, and organize level data by associating spatial regions (leaves) with properties and renderable geometry.
*   **Missing Pieces (Likely in Other Lumps):** The complete level representation requires additional data beyond the BSP structure itself, expected to be in other lumps referenced by the Lump Directory:
    *   Vertex List (X, Y, Z coordinates)
    *   Face/Polygon List (Vertex indices, texture assignments, lighting info)
    *   Texture Information
    *   Collision Data (Specific collision meshes or properties)
    *   Entity Information (Spawn points, items, triggers, NPCs, etc.)
    *   Visibility Data (Precomputed Visibility Set - PVS, if used)

