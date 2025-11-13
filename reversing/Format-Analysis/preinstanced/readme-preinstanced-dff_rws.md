# File Format Documentation: `.dff.preinstanced` / `.rws.preinstanced`

**Version:** 1.5.6
**Last Updated:** 2025-11-13
**Author(s):** (Based on reverse-engineering by Turk645, misternebula, and Samarixum)

---

## 1. Overview

* **Format Name:** Simpsons Game Preinstanced Asset
* **Common File Extension(s):** `.dff.preinstanced`, `.rws.preinstanced`
* **Purpose/Domain:** Defines 3D model geometry, multiple UV maps, and texture name associations for assets in *The Simpsons Game* (PS3).
* **Originating Application/System:** A heavily modified version of RenderWare (`.rws`, `.dff`) customized by EA for *The Simpsons Game*.
* **Format Type:** Binary, Chunk-based
* **General Structure:** This is a container format. It does not have a single global header. Instead, it's composed of sequential chunks, including texture name headers, mesh headers, and raw data blocks. The relative order of texture headers and mesh chunks is critical for linking them.

---

## 2. Identification

The format is identified by the presence of several key chunk signatures within the file, not by a single magic number at the beginning.

* **Texture Header Signatures:** Used to identify a texture name string. One of the following:
    * `02 11 01 00 02 00 00 00 14 00 00 00 2D 00 02 1C`
    * `02 11 01 00 02 00 00 00 18 00 00 00 2D 00 02 1C`
    * `02 11 01 00 02 00 00 00 10 00 00 00 2D 00 02 1C`
* **Texture List Delimiter (TLFD):**
    * `54 4C 46 44` (ASCII: `TLFD`)
    * This marker is crucial for linking. It signals the end of a texture list for a *subsequent* mesh chunk.
* **Mesh Chunk Signature:**
    * `33 EA 00 00 ?? ?? ?? ?? 2D 00 02 1C` (where `??` is a 4-byte wildcard)
* **End of File (EOF) Marker:**
    * `16 EA 00 00 05 00 00 00 2D 00 02 1C 01 00 00 00 00`

---

## 3. Global Properties

* **Endianness:** **Mixed-Endian**. This is the most critical property of the format.
    * **Big-Endian:** Used for almost all data, including geometry (vertices, UVs), face indices, and most chunk metadata (counts, sizes, and relative offsets).
    * **Little-Endian:** Used *only* for two specific fields in the `Mesh Chunk Header` (`FaceDataOff` and `MeshDataSize`).
* **Character Encoding:** **ASCII**. Used for texture names.
* **Compression:** None observed.
* **Encryption:** None observed.

---

## 4. Detailed Structure

### 4.1. High-Level Linking Logic

The file must be parsed sequentially to establish relationships between texture names and mesh chunks.

1.  A "pending texture list" (a list of strings) is maintained during parsing.
2.  When a **Texture Header** chunk is found, the **Texture String** immediately following it is read and added to this "pending" list.
3.  When a **TLFD Marker** (`54 4C 46 44`) is found, the *current* "pending texture list" is saved as a "snapshot." The pending list is then cleared.
4.  When a **Mesh Chunk** is found, it is associated with the most recent "snapshot."
5.  This process repeats, allowing one or more texture names to be associated with each mesh chunk.

### 4.2. Chunk Definitions

**Chunk: Texture Header**

A 16-byte signature that indicates a texture name string follows. See Section 2 for the three known variants.

**Chunk: Texture String**

This data block immediately follows a `Texture Header` signature.

| Offset (Relative) | Size (Bytes) | Data Type | Description | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `0x00` | 16 | `byte[16]` | Texture Header | One of the 3 variants. |
| `0x10` | 4 - 64 (Var) | `char[]` | Texture Name | ASCII string. Read until a non-string character (non `[a-zA-Z0-9_.-]`) is found. |

---

**Chunk: Mesh Chunk (Signature: `33 EA 00 00 ...`)**

This is the main header for a block of geometry.

**Section: Mesh Chunk Header**

| Offset (Hex) | Size (Bytes) | Data Type | Endianness | Field Name | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `0x00` | 4 | `byte[4]` | N/A | Signature | `0x33 0xEA 0x00 0x00` |
| `0x04` | 4 | `byte[4]` | N/A | Unknown | Wildcard bytes |
| `0x08` | 4 | `byte[4]` | N/A | Signature | `0x2D 0x00 0x02 0x1C` |
| `0x0C` | 4 | `byte[4]` | N/A | Unknown | Padding? |
| `0x10` | 4 | `uint32` | **Little** | `FaceDataOff` | Base offset for data blocks? (See notes) |
| `0x14` | 4 | `uint32` | **Little** | `MeshDataSize` | Total size of the data? (See notes) |
| `0x18` | 28 | `byte[28]` | N/A | Unknown | Padding / Other metadata |
| `0x34` | 4 | `uint32` | **Big** | `mDataTableCount` | Unknown purpose. The import script skips over this table. |
| `0x38` | 4 | `uint32` | **Big** | `mDataSubCount` | The number of sub-meshes in this chunk. |
| `0x3C` | ... | `SubMeshEntry[]`| | Sub-Mesh Table | An array of `SubMeshEntry` structures. |

* **Note:** The script defines `MeshChunkStart` as the offset *after* `MeshDataSize` (i.e., at `0x18`). All subsequent offsets are relative to this `MeshChunkStart` or `FaceDataOff`.

---

**Section: Sub-Mesh Table**

* **Structure:** `SubMeshEntry`
* **Count:** `MeshChunkHeader.mDataSubCount`
* **Location:** Starts immediately after `mDataSubCount` (at `0x3C`).

| Offset (Relative) | Size (Bytes) | Data Type | Endianness | Field Name | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `0x00` | 8 | `byte[8]` | N/A | Unknown | ... |
| `0x08` | 4 | `uint32` | **Big** | `Offset` | Relative offset (from `MeshChunkStart`) to the `Sub-Mesh Header`. |
| **Total Size** | **12 Bytes** | | | | |

---

**Section: Sub-Mesh Header**

* **Location:** `MeshChunkStart + SubMeshEntry.Offset`

| Offset (Relative) | Size (Bytes) | Data Type | Endianness | Field Name | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `0x00` | 12 | `byte[12]`| N/A | Unknown | ... |
| `0x0C` | 4 | `uint32` | **Big** | `VertCountDataOff` | Relative offset (from `MeshChunkStart`) to the `Vertex Info Header`. |
| ... | ... | ... | | ... | Other unknown data |

---

**Section: Vertex Info Header**

* **Location:** `MeshChunkStart + SubMeshHeader.VertCountDataOff`

| Offset (Relative) | Size (Bytes) | Data Type | Endianness | Field Name | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `0x00` | 4 | `uint32` | **Big** | `VertChunkTotalSize`| Total size in bytes of the associated Vertex Buffer. |
| `0x04` | 4 | `uint32` | **Big** | `VertChunkSize` | The stride (size in bytes) of a single vertex. |
| `0x08` | 4 | `byte[4]` | N/A | Unknown | ... |
| `0x0C` | 4 | `uint32` | **Big** | `VertexStart` | Relative offset (from `MeshChunkStart + FaceDataOff`) to the Vertex Buffer. |
| `0x10` | 20 | `byte[20]`| N/A | Unknown | ... |
| `0x24` | 4 | `uint32` | **Big** | `FaceDataByteLength`| Total size in bytes of the Index Buffer (FaceCount * 2). |
| `0x28` | 4 | `byte[4]` | N/A | Unknown | ... |
| `0x2C` | 4 | `uint32` | **Big** | `FaceStart` | Relative offset (from `MeshChunkStart + FaceDataOff`) to the Index Buffer. |

---

### 4.3. Data Blocks

**Data: Vertex Buffer**

* **Location:** `MeshChunkStart + FaceDataOff + VertexInfo.VertexStart`
* **Count:** `VertexInfo.VertChunkTotalSize / VertexInfo.VertChunkSize`
* **Structure:** `Vertex` (size is `VertexInfo.VertChunkSize`)

This table describes the *known* fields within the vertex stride. `VertChunkSize` is often 36 bytes or larger.

| Offset (Relative) | Size (Bytes) | Data Type | Endianness | Field Name | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `0x00` | 12 | `float32[3]` | **Big** | `Position` | (X, Y, Z) vertex coordinates. |
| `0x0C` | 8 | `byte[8]` | N/A | Unknown | ... |
| `0x14` | 4 | `float32` | **Big** | `U` (Main UV) | U coordinate for the primary texture map. |
| `0x18` | 4 | `float32` | **Big** | `V` (Main UV) | V coordinate. **Note:** Needs to be flipped (`1.0 - V`). |
| `0x1C` | 4 | `float32` | **Big** | `U` (CM UV) | U coordinate for the secondary (CM) texture map. |
| `0x20` | 4 | `float32` | **Big** | `V` (CM UV) | V coordinate for the secondary map. **Note:** Needs to be flipped (`1.0 - V`). |
| ... | ... | ... | | ... | Remainder of stride (normals, vertex colors, etc.) |

---

**Data: Index Buffer (Triangle Strips)**

* **Location:** `MeshChunkStart + FaceDataOff + VertexInfo.FaceStart`
* **Count:** `VertexInfo.FaceDataByteLength / 2`
* **Structure:** `Index`

| Offset (Relative) | Size (Bytes) | Data Type | Endianness | Field Name | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `0x00` | 2 | `uint16` | **Big** | `Index` | A vertex index. |
| **Special Value:** `0xFFFF` (65535) is a delimiter indicating a "strip cut" (end of one triangle strip and start of a new one). |

---

## 5. Data Types Reference

* **`uint16_be`:** Unsigned 16-bit integer, Big-Endian.
* **`uint32_be`:** Unsigned 32-bit integer, Big-Endian.
* **`uint32_le`:** Unsigned 32-bit integer, **Little-Endian**.
* **`float32_be`:** 32-bit IEEE 754 floating-point number, Big-Endian.
* **`char[]`:** Fixed-size array of bytes, interpreted as an ASCII string.

---

## 8. Analysis Tools & Methods

* **Tools Used:** `PreinstancedImportExtension.py` (Blender Addon), Hex Editor.
* **Methodology:** This document was created by analyzing the `PreinstancedImportExtension.py` script. The script finds known chunk signatures using regular expressions (`33 EA 00 00...`) and byte-wise searching (`02 11 01 00...`, `TLFD`). It then reads the binary structure using these documented offsets, data types, and specific endianness rules to extract geometry and texture linkages.

---

## 9. Open Questions / Uncertainties

* **`FaceDataOff` / `MeshDataSize`:** The exact purpose of these little-endian values is unclear. They are read by the script and used as part of the base offset for finding the data blocks, but their specific meaning (e.g., "offset to first face" or "total mesh block size") is ambiguous.
* **`mDataTableCount`:** The script identifies a loop based on this count but performs no operations within it. The data in this table is unknown.
* **Full Vertex Stride:** The vertex buffer contains more data than just position and two UV maps (e.g., normals, vertex colors, bone weights). The full layout of the `VertChunkSize` is not documented here.
* **Unknown Sections:** Many sections are marked as "Unknown" (e.g., in the `Mesh Chunk Header` between `0x18` and `0x34`). Their purpose is not evident from the import script.

---

## 10. References

* **Analysis Source:** `PreinstancedImportExtension.py` (versions by Turk645, misternebula, Samarixum).
* **Texture Storage:** Texture data is not stored in this file. They are stored in separate `.txd.ps3` archives, which must be extracted separately. This file only contains the *name* of the texture to be linked and possibly an identifier or reference to the texture within those archives however ive not found it.

