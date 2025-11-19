


# File Format Documentation: LH2

**Version:** 1.0
**Last Updated:** 2025-11-19
**Author(s):** samarixum

---

## 1. Overview

* **Format Name:** The Simpsons Game String Table
* **Common File Extension(s):** `.LH2`
* **Purpose/Domain:** Localization and text storage for *The Simpsons Game* (2007). It stores string identifiers, text pointers, and the actual text strings for multiple languages or columns.
* **Originating Application/System:** Electronic Arts / Rebellion (PlayStation 3 / Xbox 360 generation).
* **Format Type:** Binary
* **General Structure:** A 32-byte fixed header, followed by a list of String IDs (hashes), followed by sequences of offset tables (one sequence per language/column), and finally the heap of null-terminated strings.

---

## 2. Identification

* **Magic Number(s) / Signature:** `2HCL` (ASCII)
    * **Hex:** `32 48 43 4C`
    * **Offset:** 0x00
* **Version Information:** An integer located in the header.
    * **Location:** Offset 0x08 (4 bytes)
    * **Data Type:** `uint32_be`
    * **Observed Value:** `0x00000001`

---

## 3. Global Properties

* **Endianness:** Big-Endian (High byte first). This is consistent with the PowerPC architecture of the PS3 and Xbox 360.
* **Character Encoding:** Windows-1252 (CP1252). Strings are Null-terminated (`0x00`).
* **Default Alignment:** 4-byte alignment for integers and offsets.
* **Compression:** None. The text is stored as plain bytes.
* **Encryption:** None.

---

## 4. Detailed Structure

**Section: Header**

| Offset (Hex) | Offset (Dec) | Size (Bytes) | Data Type   | Endianness | Field Name    | Description                                    | Notes / Example Value |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `0x00` | 0 | 4 | `char[4]` | N/A | Magic Number | File signature. | `2HCL` |
| `0x04` | 4 | 4 | `uint32` | Big | File Size | Total size of the file in bytes. | Varies |
| `0x08` | 8 | 4 | `uint32` | Big | Version | Format version. | `1` |
| `0x0C` | 12 | 4 | `byte[4]` | N/A | Padding | Padding/Reserved. | `00 00 00 00` |
| `0x10` | 16 | 4 | `uint32` | Big | Entry Count | Number of strings/records per table. | `N` |
| `0x14` | 20 | 4 | `uint32` | Big | Table Count | Number of columns/languages included. | `M` |
| `0x18` | 24 | 8 | `byte[8]` | N/A | Reserved | Unused or runtime pointers. Skipped during parsing. | Typically nulls. |

**Section: String IDs**

* **Location:** Starts immediately after the header (Offset `0x20`).
* **Count:** Equal to `Header.EntryCount`.
* **Size:** `Entry Count * 4` bytes.

| Data Type | Endianness | Description | Notes |
| :--- | :--- | :--- | :--- |
| `uint32` | Big | String Hash ID | A hash representing the string label (e.g., `homr_igc_0005e10`). Used by the game engine to look up text. |

**Section: Offset Tables**

* **Location:** Immediately follows the String IDs.
* **Structure:** This section contains `M` (Table Count) blocks. Each block contains `N` (Entry Count) offsets.
* **Logic:** The pointers are grouped by table (column), not interleaved.
    * *Block 1:* Offsets for Language 0 (Entries 0 to N-1)
    * *Block 2:* Offsets for Language 1 (Entries 0 to N-1)
    * *...*

| Data Type | Endianness | Description | Notes |
| :--- | :--- | :--- | :--- |
| `uint32` | Big | String Offset | Absolute file offset pointing to the start of a null-terminated string. |

**Section: String Blob**

* **Location:** Pointed to by the Offset Tables.
* **Content:** Null-terminated sequences of characters.

| Data Type | Encoding | Description |
| :--- | :--- | :--- |
| `string` | Windows-1252 | The actual localized text. Ends with `0x00`. |

---

## 5. Data Types Reference

* **`uint32_be`:** Unsigned 32-bit integer, Big-Endian byte order.
* **`char[4]`:** 4-byte ASCII character array.
* **`string_z`:** Variable length string, encoded in Windows-1252, terminated by a null byte (`\x00`).

---

## 6. Checksums / Integrity Checks

* **File Size Check:** The integer at offset `0x04` must match the actual file size on disk.
* **ID Hashing:** The String IDs (offset `0x20`) are likely generated via a specific hashing algorithm (CRC or custom) derived from the internal string labels (e.g., `brt8_xxx_0005bcc`). The provided script alludes to a `tsg_hash.py` for validating these IDs.

---

## 7. Known Variations / Versions

* **Convention:** If `Table Count` > 1, the *last* table usually contains the internal String Labels (e.g., `homr_igc_0005e10`) rather than localized text. The parser treats `Table Count - 1` columns as languages and the final column as the Label.

---

## 8. Analysis Tools & Methods

* **Tools Used:**
    * Python 3 custom script (`TheSimpsonsGame_NewGen_LH2.py`).
    * Hex analysis of input files (`simpsons_global.en.LH2`, `bsh_igc12.LH2`).
* **Methodology:**
    * Reverse-engineered the logic within the `parse_lh` function of the provided script.
    * Correlated the script's read operations (`read_int`, `seek`, `read(0x1)`) with the binary file structure.
    * Verified structure against the text output generated by the script.

---

## 9. Open Questions / Uncertainties

* **Bytes 0x18 - 0x1F:** The script explicitly seeks to `0x20`, skipping these 8 bytes. In the write function, it writes `bytes(0x8)` (nulls). These are likely reserved for runtime memory pointers or padding, but their exact utility in a static file is unknown.
* **Encoding:** While Windows-1252 covers English and Western European languages (French, Spanish, Italian), it is unclear if Asian releases of the game use a different encoding (e.g., Shift-JIS) within the same container structure, or if they use a modified `.LH2` format.

---

## 10. References

* **Script Source:** `TheSimpsonsGame_NewGen_LH2.py` (Written by Edness, v1.1, 2022-05-30).
* **GitHub Repository:** [EdnessP/scripts](https://github.com/EdnessP/scripts/blob/main/simpsons-game/TheSimpsonsGame_NewGen_LH2.py)

---

## 11. Revision History

| Version | Date | Author(s) | Changes Made |
| :--- | :--- | :--- | :--- |
| 1.0 | 2025-11-19 | Gemini | Initial documentation based on parser analysis. |

---
