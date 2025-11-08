# Simpsons Game STR Archive Format Documentation

**File Extension:** `.str`

**Origin:** The Simpsons Game. Note that `.str` is a common extension; this documentation specifically describes the version used in this game, identifiable by its signature.

**Purpose:**
The `.str` files in The Simpsons Game function as archive files. They bundle multiple individual files together into a single container. These contained files may be compressed.

**Endianness:** Big Endian. All multi-byte numerical values (longs, shorts) are stored in big-endian format.

**Signature:**
Files start with the 4-byte ASCII signature `"SToc"` (Hex: `0x53 0x54 0x6F 0x63`).

**Overall Structure:**
The file follows a typical archive structure:

1.  **Header:** Contains the signature, offsets, file count, and other metadata.
2.  **File Information Table:** A list of entries, each describing a file stored in the archive.
3.  **Padding:** Alignment bytes to ensure the data block starts at a specific boundary.
4.  **File Data Blocks:** Contiguous blocks containing the actual data for each file listed in the information table.

**Detailed Format:**

**1. Header (Offsets relative to the start of the file):**

*   `0x00` (4 bytes): Signature `"SToc"`.
*   `0x04` (4 bytes): Unknown field (`DUMMY1` in script).
*   `0x08` (4 bytes): Unknown field (`DUMMY2` in script). However, its most significant byte (at file offset `0x08`) contains the total number of file entries stored in this archive.
*   `0x0C` (4 bytes): Unknown field (`DUMMY3` in script).
*   `0x10` (4 bytes): Info Table Offset. Absolute offset within the `.str` file where the File Information Table begins.
*   `0x14` - `0x30` (32 bytes): 8 unknown 4-byte fields (`DUMMY5` through `DUMMY12` in script).

**2. File Information Table:**

*   Starts at the `Info Table Offset` read from the header (at `0x10`).
*   Consists of a series of entries, one for each file. The total number of entries is derived from the byte at file offset `0x08`.
*   Each entry has a fixed size of 24 bytes:
    *   `+0x00` (8 bytes): Unknown longlong field.
    *   `+0x08` (4 bytes): Original Size (`SIZE`). The size of the file after decompression (if compressed).
    *   `+0x0C` (4 bytes): Unknown size field (`IGNORE_SIZE`).
    *   `+0x10` (4 bytes): Stored Size (`XSIZE`). The size of the file's data block as it is stored in the archive (could be compressed size).
    *   `+0x14` (4 bytes): Unknown field.

**3. Padding:**

*   After the File Information Table, there might be padding bytes. The script calculates the start of the actual file data (`BASE_OFF`) based on the end of the header and the total size of the info table, then aligns this offset to the next 2048-byte (`0x800`) boundary.

**4. File Data Blocks:**

*   Start at the calculated and aligned `BASE_OFF`.
*   Contains the data for each file listed in the info table, stored contiguously.
*   The size of each file's block within the archive is specified by its `XSIZE` field in the info table entry.
*   **Compression:**
    *   Files may be compressed using the `dk2` (Dklibs) algorithm.
    *   To check for compression, the script reads the first 2 bytes of a file's data block.
    *   If these two bytes are `0x10fb`, the block is compressed. It needs to be decompressed using the `dk2` algorithm. The compressed data has size `XSIZE`, and the expected decompressed size is `SIZE`.
    *   If the first two bytes are not `0x10fb`, the data is stored uncompressed. The script reads `SIZE` bytes directly from the archive for this file. (Note: Typically, one might expect `XSIZE` bytes to be read if uncompressed and `XSIZE == SIZE`, but the script explicitly uses `SIZE` in the log command here).

**5. Internal Structure of Extracted Data (Important Nuance):**

*   After a file's data block is read (and potentially decompressed) from the `.str` archive, this extracted data block may itself contain further structure, including multiple sub-files with their own headers and names.
*   The script processes this extracted data block (`MEMORY_FILE` in BMS terms) by looking for internal 16-byte headers.
*   A field within this internal header (`HEADER_SIZE` at offset `+0x0C`) indicates whether filename metadata is present.
*   If `HEADER_SIZE > 0`, the script parses complex metadata including multiple length-prefixed strings (likely representing paths or multiple identifiers, with the last one used as the filename) and the final size of the sub-file data.
*   If `HEADER_SIZE == 0`, the script assumes the remaining data in the block is a single unnamed file.
*   The script then extracts these sub-files using the parsed name (if available) and size from the temporary data block.
*   There seems to be internal padding or specific offset calculations to navigate between these sub-files within the extracted data block.

**Tools:**

*   **QuickBMS:** Can be used with the `simpsons_str.bms` script (available on Aluigi's website) to extract the contents of these `.str` archives. The script handles the "SToc" signature, decompression (`dk2` via `0x10fb` check), and the extraction of potential sub-files as described above.
