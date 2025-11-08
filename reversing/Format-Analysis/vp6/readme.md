File Format Documentation: Simpsons Game .vp6 Video

This format is understood and easily converted to ogv using vgmstream



Version: 0.1
Last Updated: 2025-05-04
Author(s): [Analysis derived from provided text]
1. Overview

    Format Name: Simpsons Game .vp6 Video Format
    Common File Extension(s): `.vp6`
    Purpose/Domain: Contains interleaved video and audio data for pre-rendered cutscenes, attract loops, and other in-game movies.
    Originating Application/System: The Simpsons Game (Electronic Arts - PAL PS3 Version analyzed, likely similar across platforms).
    Format Type: Binary, Chunk-based.
    General Structure: Utilizes a chunk-based structure common in EA formats. Files contain specific header chunks (`SCHl` or `SHxx` for audio, `MVhd` for video) followed by interleaved data chunks for audio and video streams.

2. Identification

    Magic Number(s) / Signature: While not a single universal signature, files often start with an audio header chunk.
        `SCHl` (`53 43 48 6C`) - Observed at the beginning of analyzed files.
        `SHxx` (e.g., `SHEN` = `53 48 45 4E`) - Language-specific audio header, can appear instead of or after `SCHl`.
        `MVhd` (`4D 56 68 64`) - Video header, might appear early if not preceded by an audio header.
        (Note: vgmstream also checks for `MADk` and `MPCh` as potential starting chunks for related EA video formats.)
    Offset: Typically `0x00` for the first chunk (e.g., `SCHl` in examples).
    Version Information: No specific overall file format version field identified.
        Video codec identified by a marker within the `MVhd` chunk.
    Location: Video codec marker (`vp60`) is within the `MVhd` chunk data.
    Data Type: `char[4]` for chunk IDs and the video codec marker.

3. Global Properties (If Applicable)

    Endianness: [Assumed Big-Endian for chunk headers/sizes based on typical EA formats, but needs confirmation. Data within chunks may vary.]
    Character Encoding: ASCII for chunk IDs and language codes (e.g., `EN`, `FR`).
    Default Alignment: [Unknown, though chunk structures often imply some alignment.]
    Compression:
        Video Stream: On2 TrueMotion VP6.
        Audio Stream(s): Electronic Arts EA-XA 4-bit ADPCM v2.
    Encryption: None mentioned or identified.

4. Detailed Structure

This format uses a sequence of chunks. Key identified header chunks are:

Chunk: `SCHl` (Sound Chunk Header - Standard)

    ID: `SCHl` (`53 43 48 6C`)
    Purpose: Header for the primary/standard audio stream. Contains metadata about the audio codec, sample rate, channels, etc.
    Location: Often found at the beginning of the file (Offset `0x00` in analyzed examples). vgmstream can also search for this chunk if the file starts differently.
    Structure: [Internal fields not detailed in provided text.]

Chunk: `SHxx` (Sound Header - Localized)

    ID: Base ID `0x53480000` combined with a 2-character language code (e.g., `EN=0x454E`, `FR=0x4652`). Example: `SHEN` = `53 48 45 4E`.
    Purpose: Header for language-specific audio streams. Contains similar metadata to `SCHl`.
    Location: Can appear instead of `SCHl`, or multiple `SHxx` chunks may appear sequentially after an initial `SCHl` or another `SHxx`. vgmstream can handle these multiple streams.
    Structure: [Internal fields not detailed in provided text, assumed similar to `SCHl`.]

Chunk: `MVhd` (Movie Header)

    ID: `MVhd` (`4D 56 68 64`)
    Purpose: Contains metadata about the video stream, including the codec identifier (`vp60`).
    Location: Observed shortly after the initial audio header chunk (e.g., offset `0x2C` in examples).
    Structure: Contains `vp60` marker identifying the On2 TrueMotion VP6 codec. [Other internal fields not detailed in provided text.]

Data Chunks:

    Following the header chunks, the file contains interleaved data chunks for audio and video.
    Known audio data chunk IDs include `SCDl`, `SCCl`.
    Known video data chunk IDs include `MV0K`.
    The exact interleaving pattern and structure of these data chunks are not detailed in the provided text.

5. Data Types Reference

    - `char[4]`: Fixed-size 4-byte array, used for Chunk IDs (e.g., `SCHl`, `MVhd`) and the Video Codec Identifier (`vp60`). Interpreted as ASCII characters.
    - EA-XA 4-bit ADPCM v2: Specific audio codec used for the sound streams within the EA `SCHl` container structure.
    - On2 TrueMotion VP6: Specific video codec used for the video stream, identified by the `vp60` marker.

6. Checksums / Integrity Checks

    - Type: None mentioned or identified.
    - Location: N/A
    - Scope: N/A
    - Algorithm Details: N/A

7. Known Variations / Versions

    - Audio Localization: Files may contain a single standard audio stream (`SCHl`) or multiple language-specific streams (`SHxx`).
    - Starting Chunk: While analyzed examples started with `SCHl`, the vgmstream tool suggests related files might start with `MVhd`, `MADk`, or `MPCh`, indicating potential variations in the initial file structure, possibly placing video header/data first in some cases.

8. Analysis Tools & Methods

    - Tools Used:
        - Hex Editor (implied by reference to hex dumps and offsets).
        - vgmstream (Specifically `vgmstream-cli` and examination of its `ea_schl_standard.c` source code).
        - FFmpeg.
    - Methodology:
        - Examination of hex dumps from game files (`attractloop.vp6`, `loc_igc01.vp6`).
        - Analysis of vgmstream source code to understand how it parses the audio (`SCHl`/`SHxx`) components within `.vp6` files.

9. Open Questions / Uncertainties

    - The precise internal structure and field definitions within the `SCHl`, `SHxx`, and `MVhd` header chunks.
    - The detailed structure, organization, and interleaving pattern of the audio data chunks (`SCDl`, `SCCl`, etc.) and video data chunks (`MV0K`, etc.).
    - Definitive confirmation of endianness for various data fields within the chunks.
    - The exact nature and structure of related files that might start with `MADk` or `MPCh` chunks.

10. References

    - Analyzed files: `attractloop.vp6`, `loc_igc01.vp6` (from The Simpsons Game, PAL PS3 Version).
    - Tool Source Code: vgmstream (`ea_schl_standard.c`).
    - Related EA Formats: EA `SCHl` (audio container structure), EA BNK (sound banks).

11. Revision History (of this document)
Version | Date       | Author(s)                             | Changes Made
------- | ---------- | ------------------------------------- | ------------------------------------
0.1     | 2025-05-04 | [Analysis derived from provided text] | Initial document based on input

12. Other:

    - File Size Significance: These `.vp6` files constitute a large portion (~50%) of the total data size for The Simpsons Game.
    - Typical Video Specifications: Often 1280x720 resolution at 29.97 frames per second (can vary).
    - Typical Audio Specifications: EA-XA 4-bit ADPCM v2 codec within `SCHl` structure, typically 48000 Hz sample rate, stereo channels, resulting in bitrates around 411 kb/s.
    - Tool Usage Notes:
        - FFmpeg can analyze (`-i`) and convert (`ffmpeg -i input.vp6 output.mp4`), but may only extract the first detected audio stream by default if multiple language (`SHxx`) streams exist.
        - `vgmstream-cli` is recommended for accurate audio handling, especially multi-language files. It can analyze, play specific streams (`-s N`), and convert audio (`-o output.wav`).
    - Related `SCHl` Extensions: vgmstream associates the standalone `SCHl`/`SHxx` audio format with numerous extensions: `.asf`, `.lasf`, `.str`, `.chk`, `.eam`, `.exa`, `.sng`, `.aud`, `.strm`, `.stm`, `.sx`, `.xa`, `.hab`, `.xsf`, `.gsf`, `.r`, and extensionless files.