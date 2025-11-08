File Format Documentation:.shk.PS3

Version: 0.1 (Preliminary Analysis)
Last Updated: 2025-05-04
Author(s):
1. Overview

    Format Name: Simpsons Game Vibration Data (PS3)
    Common File Extension(s): .shk.PS3
    Purpose/Domain: Intended to store controller vibration (rumble) parameters for specific in-game actions (e.g., "shooting"). However, reports indicate vibration was disabled in the final PS3 release, making the actual use of these files uncertain. They might be unused assets or placeholders.   

Originating Application/System: The Simpsons Game (2007), specifically the PlayStation 3 version developed by EA Redwood Shores.  
Format Type: Binary, Custom/Proprietary. Does not appear to follow standard RenderWare chunk structure.  

    General Structure: Small binary file (approx. 29 bytes based on shooting_tommy_gun.shk.PS3 example). Likely contains a sequence of parameters defining vibration characteristics (e.g., motor intensity, duration), possibly preceded by an identifier or header. The exact structure is unknown.

2. Identification

    Magic Number(s) / Signature: Potentially 49 13 64 B1 (first 4 bytes of shooting_tommy_gun.shk.PS3), but this is unconfirmed and not a standard signature.
        Offset: 0
    Version Information: No known method for identifying format version within the file.
        Location: [Unknown]
        Data Type: [Unknown]

3. Global Properties (If Applicable)

    Endianness: Likely Big-Endian (Consistent with PlayStation 3's PowerPC Cell architecture). This is an assumption based on the platform.
    Character Encoding: N/A (Binary data assumed).
    Default Alignment: [Unknown]
    Compression: None known or suspected.
    Encryption: None known or suspected.

4. Detailed Structure

(The precise structure is unknown due to lack of documentation and reverse engineering. The following is based solely on the single provided example: shooting_tommy_gun.shk.PS3 with hex content 49 13 64 B1 00 01 00 04 E4 AE 61 00 00 00 01 96 00 32 01 00 00 64 01 96 00 DC 01 00 - 29 bytes total).

Section: Vibration Parameters

It is not possible to provide a reliable table mapping offsets to specific fields, data types, or meanings without further analysis (e.g., comparing multiple .shk.PS3 files, comparing with Xbox 360 vibration files, or disassembling game code). The 29 bytes likely encode parameters for the DualShock 3's two vibration motors , potentially including:  

    Left motor intensity (0-255)
    Right motor intensity (0-255)
    Duration(s)
    Pattern information (e.g., fade, pulse)
    Flags or identifiers

Example Hex Data (shooting_tommy_gun.shk.PS3):
49 13 64 B1 00 01 00 04 E4 AE 61 00 00 00 01 96 00 32 01 00 00 64 01 96 00 DC 01 00
5. Data Types Reference

(Specific data types used within the file are unknown. Could include standard integer types like uint8, uint16, potentially float32 depending on how parameters are stored. Endianness would apply as noted in Section 3).

    uint8: Unsigned 8-bit integer.
    uint16_be: Unsigned 16-bit integer, Big-Endian byte order (Assumed).
    uint32_be: Unsigned 32-bit integer, Big-Endian byte order (Assumed).
    float32_be: 32-bit IEEE 754 floating-point number, Big-Endian byte order (Assumed).

6. Checksums / Integrity Checks

    Type: None known or suspected.
    Location: [N/A]
    Scope: [N/A]
    Algorithm Details: [N/A]

7. Known Variations / Versions

    [Unknown]. All 16 reported .shk.PS3 files are described as being small (approx. 1KB or less), suggesting a consistent basic structure, but internal variations are possible.

8. Analysis Tools & Methods

    Tools Used: Hex Editor (for viewing raw byte content).
    Methodology: Analysis based on file path context (controller/vibrations), file extension (.shk.PS3), comparison of file existence vs. reported game features (lack of PS3 vibration ), examination of provided hex data sample, and knowledge of the target platform (PS3).   

9. Open Questions / Uncertainties

    What is the exact meaning and structure of the bytes within the file?
    What do the initial bytes (e.g., 49 13 64 B1) signify? Is it a magic number or part of the data?
    Are these files actually loaded or used by the PS3 game code, or are they entirely vestigial assets?
    If unused, why were they included in the final build? (Possible remnant from Xbox 360 asset base?)
    What does the .shk part of the extension specifically mean in the context of this EA Redwood Shores / RenderWare project? It does not align with standard RenderWare extensions or known relevant uses like Unreal Engine's .shk or Apple II ShrinkIt.   

10. References

    Analysis based on conversation history, including initial research report and provided hex data.
    User reports on lack of PS3 vibration in The Simpsons Game.   

General information on RenderWare file structures.  
Information on PS3 architecture (Big-Endian) and DualShock 3 controller capabilities.  
Information on The Simpsons Game developers and platforms.  

11. Revision History (of this document)
Version	Date	Author(s)	Changes Made
0.1	2025-05-04	[Your Name]	Initial draft based on preliminary analysis.
12. Other:

    There are reportedly 16 .shk.PS3 files in total within the game's assets, all located under .../controller/vibrations/.
    The small file size (approx. 29 bytes) is consistent across at least one example.