# File Format Documentation: CTB (.ctb)

**Version:** 0.1
**Last Updated:** 2025-05-05
**Author(s):** [Your Name/Team] (Based on analysis)

---

## 1. Overview

* **Format Name:** Control Table / Chart Table
* **Common File Extension(s):** `.ctb`
* **Purpose/Domain:** Defines the "When" and "How" for audio playback in *The Simpsons Game*. Links high-level game events (identified by human-readable names) to low-level sound aliases/IDs defined in a corresponding `.alb` (Audio Library Bank) file. Provides contextual logic and triggers for sounds cataloged in the `.alb`. Does **not** contain raw audio data.
* **Originating Application/System:** The Simpsons Game (PAL version)
* **Format Type:** Binary (Complex metadata and control flow)
* **General Structure:** Composed of several distinct sections: Header Area, Structured Data Section, ID List Section, and String Table Section.

---

## 2. Identification

* **Magic Number(s) / Signature:** Potentially `0x00 0x06` (similar to `.alb`, possibly indicating Type/Version 6 for this family of formats).
    * **Offset:** 0
* **Version Information:** Not clearly defined. May be part of the initial `00 06` bytes.
    * **Location:** Start of file.
    * **Data Type:** Unknown.

---

## 3. Global Properties (If Applicable)

* **Endianness:** Big-Endian (for observed multi-byte numerical values like IDs, potential pointers, counts).
* **Character Encoding:** ASCII (for strings in the String Table section).
* **Default Alignment:** Unknown.
* **Compression:** None observed.
* **Encryption:** None observed.

---

## 4. Detailed Structure

The `.ctb` file is composed of several distinct sections. The exact boundaries and sizes may be defined by pointers or counts within the file itself. The general layout appears to be:

1.  **Header Area:** Contains format identifiers, potentially pointers, counts, and other metadata defining the file layout. Structure appears complex and possibly variable.
2.  **Structured Data Section:** The core logic area, likely containing rules, conditions, cue definitions, and pointers linking events, IDs, and strings. Structure seems complex.
3.  **ID List Section:** An array of 4-byte sound identifiers, referencing entries in the corresponding `.alb` file.
4.  **String Table Section:** A block of null-terminated ASCII strings representing game event names or triggers.

```
+-----------------------------+
| Header Area (~0x00 - ~0x37?) |
+-----------------------------+
| Structured Data Section     |
| (Variable Size, Complex)    |
| (~0x38 - ~0x16F?)           |
+-----------------------------+
| ID List Section             |
| (Array of uint32 IDs)       |
| (~0x170 - ~0x207?)          |
+-----------------------------+
| String Table Section        |
| (Null-terminated ASCII)     |
| (~0x208 - EOF)              |
+-----------------------------+
```
*(Note: Offsets are based on `global_marg.ctb` example and are approximate)*

**Section: Header Area (Approx `0x00` - `0x37`)**

*   **Format Identifier:** Usually starts with `00 06`.
*   **Content:** Contains a mix of potential pointers, size/count values (e.g., `00 00 00 18` at `0x14`), unknown data blocks (e.g., `1E DB 04 D5 42 C8 00 00` at `0x18`), and null padding.
*   **Purpose:** Believed to contain essential metadata defining the offsets and sizes of the subsequent data sections, although the exact fields are currently undefined.
*   **Structure:** Appears complex and possibly variable length.

**Section: Structured Data Section (Approx `0x38` - `0x16F`)**

*   **Purpose:** Holds the core control logic. Defines rules, sequences, conditions, and cues linking game events (String Table) to sound IDs (ID List).
*   **Content:** Contains a mix of:
    *   **Markers:** Repeating values like `50 00 00 0X` (ASCII `P` followed by a byte) might denote different types of cues or records.
    *   **Pointers/Offsets:** Values that look like file offsets (e.g., `00 00 02 08`, `00 00 01 78`) likely point into the ID List or String Table sections.
    *   **Data Chunks:** Other blocks of data (e.g., `33 53 5A 4E`, `49 90 BB 27`) related to the specific rule or cue.
*   **Structure:** Complex, potentially involving multiple types of records or variable-length entries. Not a simple array of identical records.

**Section: ID List Section (Approx `0x170` - `0x207`)**

*   **Purpose:** Index/manifest of sound IDs managed or referenced by this control table, corresponding to sounds in the linked `.alb` file.
*   **Format:** Tightly packed array of 4-byte identifiers.
*   **Type:** `uint32`, Big-Endian.
*   **Content:** Values like `C2 DB 01 E7`, `32 0E 2A E0`, `AA 76 AF 39`, etc., matching IDs in the corresponding `.alb`.
*   **Note:** The number of IDs here might not always exactly match the number of entries in the `.alb` file (e.g., 38 IDs in `global_marg.ctb` vs 36 entries in `global_marg.alb`). Reason unknown.

**Section: String Table Section (Approx `0x208` - End of File)**

*   **Purpose:** Contains human-readable names for game events or script triggers handled by this `.ctb` file.
*   **Format:** Sequence of standard null-terminated ASCII strings.
*   **Content:** Strings like `from_buddy_pc_wait_there`, `maggie_activated`, `react_cop`, etc.
*   **Reference:** The Structured Data section likely contains pointers/indices referring to strings within this table.

---

## 5. Data Types Reference

* **`uint32_be`:** Unsigned 32-bit integer, Big-Endian byte order. Used for IDs and potentially pointers/counts.
* **`ASCII String`:** Sequence of bytes representing characters, terminated by a null byte (`0x00`). Used in the String Table.
* **`byte[N]`:** Fixed-size array of N bytes. Purpose varies depending on context (e.g., unknown data blocks, markers).

---

## 6. Checksums / Integrity Checks

* **Type:** None observed or identified.
* **Location:** N/A
* **Scope:** N/A
* **Algorithm Details:** N/A

---

## 7. Known Variations / Versions

*   The format appears significantly more complex than `.alb`, suggesting potential variations between files, but no specific versions have been identified or differentiated yet.

---

## 8. Analysis Tools & Methods

* **Tools Used:** Hex Editor (HxD, 010 Editor), comparison with corresponding `.alb` files.
* **Methodology:** Manual analysis, identifying patterns (like potential pointers, markers, IDs), cross-referencing IDs and string content with game behavior or `.alb` files.

---

## 9. Open Questions / Uncertainties

*   Precise structure and meaning of fields within the Header Area.
*   Detailed internal structure and logic representation within the Structured Data Section.
*   Reason for potential discrepancies between the number of IDs in the ID List section and the number of entries in the corresponding `.alb` file.
*   Meaning of specific markers (e.g., `50 00 00 0X`) and data chunks in the Structured Data section.

---

## 10. References

*   Critically dependent on corresponding `.alb` files (usually sharing the same base filename) for sound definitions. Requires both `.ctb` and `.alb` for full understanding.
*   Example file used for offset analysis: `global_marg.ctb` (and `global_marg.alb`).

---

## 11. Revision History (of this document)

| Version | Date       | Author(s) | Changes Made                     |
| :------ | :--------- | :-------- | :------------------------------- |
| 0.1     | 2025-05-05 | [Your Name] | Initial draft based on analysis |
|         |            |           |                                  |

## 12. Other:
<!-- Any other relevant notes or context -->

