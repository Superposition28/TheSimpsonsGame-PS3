# Simpsons Game `.mus` Audio Format

**File Extension:** `.mus`

**Origin:** The Simpsons Game (PAL PS3 Version), likely a proprietary format from EA Redwood Shores.

**Purpose:** Used for background music streams.

**Key Characteristics:**

*   **Proprietary EA Format:**
*   **Two Subtypes:** Identified by values in the header:
    *   **Type 1:** Header bytes `0x08-0x0B` = `0F 00 00 00` (15 LE), bytes `0x0C-0x0F` = `78 01 32 00`.
    *   **Type 2:** Header bytes `0x08-0x0B` = `0B 00 00 00` (11 LE), bytes `0x0C-0x0F` = `02 03 02 03`.
*   **16-Byte Header:** Contains a per-file ID, an unknown variable integer (potentially sample count/size/loop info), and the type identifiers.
*   **Fixed Chunking:** Data is processed in fixed 64-byte physical chunks.
*   **Variable Bit Rate (VBR):** Logical audio frames can vary in size and may span across 64-byte chunks.
*   **Padding Marker:** The sequence `0C 00 00 00` (12 LE) frequently appears, likely marking the end of valid audio data within a 64-byte chunk, followed by `0x00` padding bytes.

