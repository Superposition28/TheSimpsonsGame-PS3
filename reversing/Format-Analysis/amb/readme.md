# File Format Documentation: .amb

**Version:** 1.0
**Last Updated:** 2025-05-05
**Author(s):** Analysis based on user-provided data

---

## 1. Overview

*   **Format Name:** AEMS Asset Metadata Bundle (Tentative Name based on observed paths)
*   **Common File Extension(s):** `.amb`
*   **Purpose/Domain:** Appears to be a versatile binary container format used by an internal "AEMS" system within The Simpsons Game. Its specific purpose varies depending on the asset context, indicated by file path and name. Observed uses include:
    *   Defining character interaction logic/parameters (e.g., using poles, ladders, slides).
    *   Storing character-specific audio metadata, mapping, or event triggers.
*   **Originating Application/System:** Electronic Arts (The Simpsons Game, associated with an internal "AEMS" system).
*   **Format Type:** Binary.
*   **General Structure:** Consists of a common Header structure containing identification markers, standard parameters, and configuration bytes, followed by various structured data sections heavily reliant on internal offsets/pointers. The content of the data sections varies based on the asset type being described.

---

## 2. Identification

*   **Magic Number(s) / Signature:** `41 42 4B 43` (ASCII "ABKC"). This appears to be the primary structural identifier for this format.
    *   **Offset:** `0x40` (Decimal: 64)
*   **Version Information:** Potentially the `uint32` value at the very start of the file, which was consistently `0x00000009` in all examples.
    *   **Location:** `0x00`
    *   **Data Type:** `uint32_be` (Assumed)

---

## 3. Global Properties (If Applicable)

*   **Endianness:** Big-Endian (Based on representation of multi-byte integers like offsets and floating-point values).
*   **Character Encoding:** Primarily N/A as few strings observed. If strings exist in data sections, likely ASCII.
*   **Default Alignment:** Likely 4-byte alignment, common in console game formats, but not strictly verified.
*   **Compression:** None observed in the overall structure or headers. Data sections also appear uncompressed.
*   **Encryption:** None observed.

---

## 4. Detailed Structure

The format starts with a relatively consistent header area, followed by data sections whose content depends on the file's specific purpose.

**Section: Header Area (Approx. 0x00 - 0x7F)**

This initial section contains identifiers, common parameters, and file-specific setup values.

| Offset (Hex) | Offset (Dec) | Size (Bytes) | Data Type         | Endianness | Field Name            | Description                                                              | Notes / Example Value                       |
| :----------- | :----------- | :----------- | :---------------- | :--------- | :-------------------- | :----------------------------------------------------------------------- | :------------------------------------------ |
| `0x00`       | 0            | 4            | `uint32`          | Big        | Format ID / Version?  | Consistently `0x00000009`. Possible version identifier for the AMB format within AEMS. | `00 00 00 09`                               |
| `0x04`       | 4            | 4            | `uint32`          | Big        | Unknown ID/Offset 1   | Purpose unclear. Value varies between files.                             | `00 09 4C 4C`, `00 1B E5 C0`, `00 2B 9D 1C` |
| `0x08`       | 8            | 4            | `uint32`          | Big        | Offset 1              | Points to data within the file. Purpose of data pointed to varies.       | `00 00 00 D8`, `00 00 02 88`, `00 00 02 D0` |
| `0x0C`       | 12           | 4            | `uint32`          | Big        | Unknown ID/Offset 2   | Often repeats the value from `0x04`. Purpose unclear.                    | `00 09 4C 4C`, `00 1B E5 C0`, `00 2B 9D 1C` |
| `0x10`       | 16           | 4            | `uint32`          | Big        | Unknown / Padding     | Often `00 00 00 00`.                                                     | `00 00 00 00`                               |
| `0x14`       | 20           | 4            | `uint32`          | Big        | Unknown Hash/ID?      | Consistent value (`86 55 C9 61`) in Bart/Lisa audio files. Different in pole/ladder file. | `2C 82 F4 EE`, `86 55 C9 61`                |
| `0x18`       | 24           | 4            | `float32`         | Big        | Constant Float 1      | Consistently `1.0f`. Purpose unknown (maybe scale/time factor?).         | `3F 80 00 00` (1.0f)                        |
| `0x1C`       | 28           | 4            | `float32`         | Big        | Constant Float 2      | Consistently `2.0f`. Purpose unknown.                                    | `40 00 00 00` (2.0f)                        |
| `0x20`       | 32           | 4            | `float32`         | Big        | Constant Float 3      | Consistently `100.0f`. Purpose unknown.                                  | `42 C8 00 00` (100.0f)                      |
| `0x24`       | 36           | 4            | `uint32`          | Big        | Flags / Count?        | Often `0x00010000`.                                                      | `00 01 00 00`                               |
| `0x28`       | 40           | 16+          | `byte[]`          | N/A        | Padding / Reserved    | Area often filled with zeros before the ABKC marker. Size varies slightly. | `00 00 ... 00`                              |
| `0x40`       | 64           | 4            | `char[4]`         | N/A        | ABKC Marker           | Consistent structural identifier "ABKC".                                 | `41 42 4B 43` ("ABKC")                      |
| `0x44`       | 68           | 8            | `byte[8]`         | N/A        | Configuration Bytes   | Contains various flags/counts. Byte at `0x4B` seems to vary based on content type. | `01 01 02 02 0A 03 00 [01/05/02]`          |
| `0x4C`       | 76           | 4            | `uint32`          | Big        | Unknown / Padding     | Often `00 00 00 00`.                                                     | `00 00 00 00`                               |
| `0x50`       | 80           | 4            | `uint32`          | Big        | Unknown / Padding     | Often `00 00 00 00`.                                                     | `00 00 00 00`                               |
| `0x54`       | 84           | 4            | `uint32`          | Big        | Unknown ID/Offset 3   | Repeats value from `0x04`.                                               | `00 09 4C 4C`, `00 1B E5 C0`, `00 2B 9D 1C` |
| `0x58`       | 88           | 4            | `uint32`          | Big        | Offset 2              | Points to data/structure within the file.                                | `00 00 0B 80`, `00 00 AA 00`, `00 00 66 80` |
| `0x5C`       | 92           | 4            | `uint32`          | Big        | Offset 3              | Points to data/structure within the file (Often `0x78`).                 | `00 00 00 78`                               |
| `0x60`       | 96           | 4            | `uint32`          | Big        | Offset 4              | Points to data/structure within the file.                                | `00 00 0B 80`, `00 00 AA 00`, `00 00 66 80` |
| `0x64`       | 100          | 4            | `uint32`          | Big        | Offset 5              | Points to data/structure within the file.                                | `00 09 40 24`, `00 1B 36 E0`, `00 2B 31 FC` |
| `0x68`       | 104          | 12           | `byte[12]`        | N/A        | Padding / Unknown     | Often `00 00 ... 00`.                                                    | `00 00 ... 00`                              |
| `0x74`       | 116          | 12           | `uint32[3]`       | Big        | Offset List 1         | List of 3 offsets pointing to related data structures.                   | e.g., `00 09 4B A4`, `00 09 4B A8`, `00 09 4B D8` |

**Section: Data Sections (Variable Content)**

*   **Location:** Follows the header area (from approx `0x80` onwards).
*   **Structure:** Composed of multiple data blocks located at offsets specified in the header or other data blocks.
*   **Content:** Highly variable based on the file's purpose:
    *   Interaction Files (e.g., poles/ladders): Likely contains animation references, timing data, physics parameters, trigger conditions.
    *   Audio Metadata Files (e.g., Bart/Lisa): Likely contains lists mapping game events/states/animations to Sound IDs (for ALB/CTB lookup) or direct stream references (e.g., SNU filenames/hashes), along with playback parameters (volume, probability, etc.).
*   **Common Patterns:** Often includes blocks of records starting with type/flag bytes, followed by lists of offsets. The value `FF FF FF FF` is frequently used, possibly indicating null pointers, default values, or end-of-list markers.
*   **Audio Waveforms:** No raw or compressed audio waveform data has been observed within `.amb` files themselves.

---

## 5. Data Types Reference

*   **`uint8`:** Unsigned 8-bit integer.
*   **`uint32_be`:** Unsigned 32-bit integer, Big-Endian byte order.
*   **`float32_be`:** 32-bit IEEE 754 floating-point number, Big-Endian byte order.
*   **`char[4]`:** Fixed-size array of 4 bytes, used for the "ABKC" marker.

---

## 6. Checksums / Integrity Checks

*   None observed or known for this format.

---

## 7. Known Variations / Versions

*   **Content Type:** The primary variation is the type of metadata stored within the common AMB structure (e.g., Interaction data vs. Audio metadata). This might be indicated by the configuration byte at offset `0x4B`.
*   **Specific Data:** Offsets, counts, and the content of data records vary significantly between files depending on the specific asset being described.

---

## 8. Analysis Tools & Methods

*   **Tools Used:** Hex Editor (e.g., HxD, 010 Editor).
*   **Methodology:** Comparison of multiple `.amb` files from different functional areas (interaction, audio) and for different characters (Bart, Lisa) to identify consistent structural elements ("ABKC", header pattern, floats) versus variable content sections. Analyzing file paths provided crucial context for interpreting purpose.

---

## 9. Open Questions / Uncertainties

*   What does the "AEMS" acronym stand for?
*   What is the precise purpose of the consistent header fields (ID at `0x00`, IDs/Offsets at `0x04`/`0x0C`/`0x54`/etc., the hash at `0x14`, the floats `1.0`/`2.0`/`100.0`)?
*   What is the exact meaning and bitmask/enum breakdown of the configuration bytes at `0x44`-`0x4B`? Does `0x4B` reliably indicate content type?
*   What is the detailed structure and interpretation of the various data records and blocks referenced by offsets?
*   For audio-related `.amb` files, how exactly do they reference the sound resources? (Via ALB/CTB IDs? Direct SNU references? Hashes?)

---

## 10. References

*   **Files Analyzed:**
    *   `char_poles_and_ladders.amb`
    *   `char_sa_bart.amb`
    *   `char_sa_lisa.amb`
*   **Related Formats:** `.alb`, `.ctb`, `.snu` (Interact with the assets potentially defined or referenced by `.amb` files).

---

## 11. Revision History (of this document)

| Version | Date       | Author(s)                         | Changes Made                                |
| :------ | :--------- | :-------------------------------- | :------------------------------------------ |
| 1.0     | 2025-05-05 | Analysis based on user-provided data | Initial draft based on provided examples |

---

## 12. Other

*   The `.amb` format within the AEMS system appears to be a flexible, pointer-heavy structure capable of holding metadata for different types of game assets, unified by a common header pattern including the "ABKC" marker. Its specific interpretation relies heavily on the context provided by the file's path and name.

