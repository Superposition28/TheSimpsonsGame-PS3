# File Format Documentation: ALB

**Version:** 1.0
**Last Updated:** 2025-05-05
**Author(s):** [Reverse Engineering Team/Contributor Name]

---

## 1. Overview

*   **Format Name:** Audio Library Bank / Alias Bank
*   **Common File Extension(s):** `.alb`
*   **Purpose/Domain:** Metadata layer for managing dialogue streams and other categorized sound events. Defines sound event identifiers (IDs/Hashes) used by the game engine to locate and manage audio playback. Does not contain raw audio data.
*   **Originating Application/System:** *The Simpsons Game* (PAL version observed)
*   **Format Type:** Binary
*   **General Structure:** Fixed-size Header followed by a variable number of fixed-size Entry Records.

---

## 2. Identification

*   **Magic Number(s) / Signature:** No traditional magic number, but the first two bytes seem fixed.
    *   **Value:** `0x0006`
    *   **Offset:** 0
*   **Version Information:** Potentially indicated by the first two bytes.
    *   **Location:** Offset 0
    *   **Data Type:** `uint16` (Big-Endian)
    *   **Observed Value:** `0x0006`

---

## 3. Global Properties (If Applicable)

*   **Endianness:** Big-Endian
*   **Character Encoding:** Not Applicable (Binary format, no significant text strings observed)
*   **Default Alignment:** Structures appear tightly packed, no explicit padding mentioned beyond potential internal field alignment within the 28-byte record.
*   **Compression:** None observed.
*   **Encryption:** None observed.

---

## 4. Detailed Structure

**Section: Header**

| Offset (Hex) | Offset (Dec) | Size (Bytes) | Data Type | Endianness | Field Name          | Description                                   | Notes / Example Value      |
| :----------- | :----------- | :----------- | :-------- | :--------- | :------------------ | :-------------------------------------------- | :------------------------- |
| `0x00`       | 0            | 2            | `uint16`  | Big        | Format Type/Version | Consistently `0x0006`.                        | `00 06`                    |
| `0x02`       | 2            | 2            | `uint16`  | Big        | Entry Record Count  | Number of Entry Records following the header. | `00 0D` (13), `00 24` (36) |
| `0x04`       | 4            | 4            | `uint32`  | Big        | Data Offset         | Offset to the first Entry Record. Always `8`. | `00 00 00 08`              |

**Section: Entry Records**

*   **Structure Name:** `AlbEntry`
*   **Count:** Determined by `Header.EntryRecordCount`
*   **Location:** Starts at offset `Header.DataOffset` (always 8)
*   **Total Size per Record:** 28 bytes

*Structure based on common pattern (e.g., `global_marg.alb`), see notes for variations:*

| Offset (Relative) | Size (Bytes) | Data Type | Endianness | Field Name                 | Description                                                                                                | Notes / Example Value (`global_marg.alb`) |
| :---------------- | :----------- | :-------- | :--------- | :------------------------- | :--------------------------------------------------------------------------------------------------------- | :---------------------------------------- |
| `0x00`            | 4            | `uint32`  | Big        | Primary ID / Metadata 1    | Often seems sequential or related between entries.                                                         | `11 8B D8 FD`, `12 94 15 3E`              |
| `0x04`            | 4            | `uint32`  | Big        | Constant Flag / Type ID?   | Appears fixed within a file/category. **Position might vary (see Variations below)**.                      | `A1 B3 C0 62`                             |
| `0x08`            | 4            | `uint32`  | Big        | Sound Hash / Secondary ID 1 | Main identifier for the sound cue. Repeated 3 times.                                                       | `3E 02 F8 57`                             |
| `0x0C`            | 4            | `uint32`  | Big        | Sound Hash / Secondary ID 2 | Identical to bytes at offset `0x08`.                                                                       | `3E 02 F8 57`                             |
| `0x10`            | 4            | `uint32`  | Big        | Sound Hash / Secondary ID 3 | Identical to bytes at offset `0x08`.                                                                       | `3E 02 F8 57`                             |
| `0x14`            | 4            | `uint32`  | Big        | Metadata Field 2           | Varies per entry. Purpose unclear (flags, length, priority?).                                            | `B7 14 EE 51`, `B7 14 EE 52`              |
| `0x18`            | 4            | `uint32`  | Big        | Metadata Field 3 / Next ID? | Often related to the Primary ID of the current or next entry. **May contain Constant Flag in variations.** | `11 8B D8 FE`, `12 94 15 3F`              |

---

## 5. Data Types Reference

*   **`uint16`:** Unsigned 16-bit integer, Big-Endian.
*   **`uint32`:** Unsigned 32-bit integer, Big-Endian.

---

## 6. Checksums / Integrity Checks

*   None observed or identified.

---

## 7. Known Variations / Versions

*   The primary variation observed is the position of the 4-byte "Constant Flag / Type ID".
    *   **Common Position:** Offset `0x04` within the 28-byte record (e.g., `global_marg.alb`).
    *   **Alternate Position:** Offset `0x18` within the 28-byte record (e.g., `eps_gam_homr.alb`, Example: `2C 04 E1 25`). In this case, the field at offset `0x04` takes on a different, variable role.
*   The core structure (28-byte record size, 3x repeated Sound Hash) appears consistent across observed variations.
*   **How to Differentiate:** Requires inspecting the value at offset `0x04` across multiple records. If it's constant, it's likely the flag. If it varies, the flag might be at offset `0x18`.

---

## 8. Analysis Tools & Methods

*   **Tools Used:** Hex Editor (e.g., HxD, 010 Editor).
*   **Methodology:** Manual comparison and analysis of various `.alb` files using a hex editor. Identifying fixed patterns (header, record size) and variable fields. Correlating repeated values (Sound Hash). Observing differences between files associated with different game contexts (global vs. level-specific).

---

## 9. Open Questions / Uncertainties

*   Precise meaning and usage of `Primary ID / Metadata 1` (Offset `0x00`).
*   Precise meaning and usage of `Metadata Field 2` (Offset `0x14`).
*   Precise meaning and usage of `Metadata Field 3 / Next ID?` (Offset `0x18`), especially when it doesn't contain the Constant Flag.
*   Exact relationship between `Primary ID` and the repeated `Sound Hash / Secondary ID`. Is one derived from the other, or are they independent lookups?
*   Full extent of variations across all `.alb` files in the game.

---

## 10. References

*   Corresponding `.ctb` (Control Table) files, which reference the IDs defined in `.alb` files to trigger sounds based on game events.
*   Specific file examples used for analysis: `global_marg.alb`, `eps_gam_homr.alb`.

---

## 11. Revision History (of this document)

| Version | Date       | Author(s)                               | Changes Made                                      |
| :------ | :--------- | :-------------------------------------- | :------------------------------------------------ |
| 1.0     | 2025-05-05 | [Reverse Engineering Team/Contributor Name] | Initial structured documentation based on template |

---

## 12. Other:

*   These files work in direct conjunction with corresponding `.ctb` (Control Table) files. The `.ctb` file links the low-level IDs from the `.alb` file to high-level game events and defines playback logic.

