File Format Documentation: Simpsons Game STR Archive (SToc)


this format is understood and can be easily extracted using an official quickbms script



Version: 1.0
Last Updated: 2025-05-04
1. Overview

    Format Name: Simpsons Game STR Archive Format
    Common File Extension(s): .str (Note: This specific format is identified by its signature)
    Purpose/Domain: Archive file format used to bundle multiple individual files together, potentially with compression.
    Originating Application/System: The Simpsons Game (Electronic Arts)
    Format Type: Binary Archive
    General Structure: Header containing metadata and offsets, followed by a File Information Table describing each contained file, optional padding, and finally the contiguous data blocks for each file.

2. Identification

    Magic Number(s) / Signature: "SToc"
        Hex: 0x53 0x54 0x6F 0x63
    Offset: 0x00
    Version Information: No specific format version field identified within the file structure. The "SToc" signature identifies this particular variant.

3. Global Properties (If Applicable)

    Endianness: Big-Endian (All multi-byte numerical values like offsets, sizes, etc., are stored in Big-Endian format).
    Character Encoding: ASCII for the "SToc" signature. Filenames extracted from internal data blocks appear to use length-prefixed strings (likely ASCII).
    Default Alignment: The start of the File Data Blocks section is aligned to a 2048-byte (0x800) boundary relative to the start of the file.
    Compression: Individual files within the archive may be compressed using the dk2 (Dklibs) algorithm. Compression is identified by a specific 2-byte marker at the start of a file's data block.
    Encryption: None mentioned or identified.

4. Detailed Structure

Section: Header
Offset (Hex)	Offset (Dec)	Size (Bytes)	Data Type	Endianness	Field Name	Description	Notes / Example Value
0x00	0	4	char[4]	N/A	Signature	File identifier signature	"SToc"
0x04	4	4	uint32_be	BE	Unknown (DUMMY1)	Unknown purpose.	
0x08	8	4	uint32_be	BE	Unknown (DUMMY2)	Unknown purpose, BUT its Most Significant Byte (at offset 0x08) = File Count.	MSB contains # of entries
0x0C	12	4	uint32_be	BE	Unknown (DUMMY3)	Unknown purpose.	
0x10	16	4	uint32_be	BE	Info Table Offset	Absolute offset to the start of the File Information Table.	e.g., 0x00000034
0x14	20	28	uint32_be	BE	Unknown (DUMMY5-12)	7 unknown 4-byte fields.	
0x30	48	4	uint32_be	BE	Unknown (DUMMY12)	Final unknown 4-byte field in this block.	

Section: File Information Table

    Location: Starts at Header.Info Table Offset.
    Count: Determined by the Most Significant Byte at file offset 0x08.
    Structure: An array of file entries.
    Total Size: File Count * 24 bytes.
    Entry Structure (Size: 24 bytes):

Offset (Relative)	Size (Bytes)	Data Type	Endianness	Field Name	Description	Notes / Example Value
+0x00	8	uint64_be	BE	Unknown	Unknown purpose.	
+0x08	4	uint32_be	BE	Original Size	Size of the file after decompression (if applicable).	
+0x0C	4	uint32_be	BE	Unknown Size	Unknown purpose (IGNORE_SIZE in script).	
+0x10	4	uint32_be	BE	Stored Size	Size of the file data as stored in the archive (compressed size).	
+0x14	4	uint32_be	BE	Unknown	Unknown purpose.	

Section: Padding

    Location: Immediately follows the File Information Table.
    Purpose: To align the start of the File Data Blocks section to a 2048-byte (0x800) boundary.
    Size: Variable (0 to 2047 bytes). Calculated based on the end of the Info Table.

Section: File Data Blocks

    Location: Starts immediately after the Padding, at the calculated 2048-byte aligned offset (BASE_OFF in script).
    Structure: Contains the raw data for each file listed in the File Information Table, stored contiguously one after another.
    Size per File: The size of each file's data block within this section is given by the Stored Size (XSIZE) field in its corresponding File Information Table entry.
    Compression Check:
        For each file block, the first 2 bytes are checked.
        If byte[0:2] == 0x10fb (Big Endian uint16_be), the data block (of size Stored Size) is compressed using the dk2 algorithm. It must be decompressed to obtain the final data, which should match Original Size.
        If byte[0:2] != 0x10fb, the data block is stored uncompressed. The script reads Original Size bytes directly (note: script observation suggests reading Original Size, although Stored Size might be expected if Original Size == Stored Size).

Section: Internal Structure of Extracted Data

    Context: This applies after a file's data block has been read from the .str archive and potentially decompressed.
    Structure: The extracted data block (treated as MEMORY_FILE in BMS) may contain one or more sub-files with internal headers and filenames.
    Parsing: The simpsons_str.bms script processes this block:
        Looks for internal 16-byte headers.
        A field at offset +0x0C within this internal header (HEADER_SIZE) determines if filename metadata exists.
        If HEADER_SIZE > 0: Parses complex metadata involving length-prefixed strings (potential paths/multiple IDs, last is used as filename) and the final sub-file size.
        If HEADER_SIZE == 0: Assumes the rest of the data block is a single, unnamed sub-file.
        Extracts these sub-files based on the parsed name and size. Internal offsets/padding might be involved.

5. Data Types Reference

    char[4]: 4-byte ASCII character sequence (e.g., "SToc").
    uint32_be: Unsigned 32-bit integer, Big-Endian byte order.
    uint64_be: Unsigned 64-bit integer, Big-Endian byte order.
    byte: 8-bit unsigned integer.
    uint16_be: Unsigned 16-bit integer, Big-Endian byte order (used for dk2 marker 0x10fb).
    dk2 (Dklibs): A specific compression algorithm. Detection relies on the 0x10fb marker.

6. Checksums / Integrity Checks


7. Known Variations / Versions

    The .str extension is common; this specific format is distinguished by the "SToc" signature and the described Big-Endian structure. No other versions of the "SToc" format itself are detailed.

8. Analysis Tools & Methods

    Tools Used:
        QuickBMS (with the simpsons_str.bms script).
        Hex Editor (implied for examining structure and offsets).
    Methodology: Analysis primarily based on the functionality implemented in the simpsons_str.bms QuickBMS script, likely derived from reverse engineering the game's file handling or direct structure analysis.

9. Open Questions / Uncertainties

    The exact purpose of the unknown fields in the header (0x04, 0x08 [excluding MSB], 0x0C, 0x14-0x30).
    The exact purpose of the unknown 8-byte field and the 4-byte "Unknown Size" (IGNORE_SIZE) field within the File Information Table entries.
    Precise specification of the length-prefixed string format used for filenames within the extracted data blocks.
    Confirmation of the exact read logic for uncompressed files (reading Original Size vs. Stored Size).

10. References

    Extraction Script: simpsons_str.bms for QuickBMS (by Aluigi, typically found on ZenHAX or related forums).
    Compression Library: dk2 / Dklibs (associated with the 0x10fb compression signature).

11. Revision History (of this document)
Version	Date	Author(s)	Changes Made
1.0	2025-05-04	[Analysis derived from provided text and script]	Initial document based on input
12. Other:

    Common Extension: Be aware that .str is used by many applications; rely on the "SToc" signature for identification.
    Two-Stage Extraction: Extracting useful content is often a two-step process:
        Use QuickBMS and simpsons_str.bms to extract the primary data blocks from the .str archive (handling dk2 decompression).
        Analyze the extracted data blocks, as they may contain further structured data (sub-files with headers/names) that the BMS script also attempts to parse and save individually.