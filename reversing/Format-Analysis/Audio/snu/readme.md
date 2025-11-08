# File Format Documentation: .snu

This format is understood and easily converted to wav using vgmstream


**Version:** 2.0  
**Last Updated:** 2025-05-05  
**Author(s):** Analysis based on user-provided data  

---

## 1. Overview

*   **Format Name:** Electronic Arts SNU Audio Stream Container  
*   **Common File Extension(s):** `.snu` (Often observed with preceding extensions, e.g., `.exa.snu`)  
*   **Purpose/Domain:** Container or wrapper for Electronic Arts compressed game audio streams (dialogue, ambience, music). It typically encapsulates audio data structured according to either the older EA SNR/SNS format or the newer EA SPS format, both part of the EAAC (Electronic Arts Audio Compression) family.  
*   **Originating Application/System:** Electronic Arts games, particularly associated with titles from EA Redwood Shores/Visceral Games (e.g., Dead Space, Dante's Inferno, The Godfather 2) and other EA games like The Simpsons Game (PS3 version observed).  
*   **Format Type:** Binary.  
*   **General Structure:** Consists of a small Header providing basic information and an offset to the main audio data block. This main block follows either the EA SPS structure or the older EA SNR/SNS structure.  

---

## 2. Identification

*   **Magic Number(s) / Signature:** No definitive universal magic number identified for the SNU wrapper itself. The first bytes often vary. vgmstream identifies the format based on header heuristics and potentially the structure of the contained data. (The previously observed `01 0C 00 00` might be specific to certain files/variants).  
    *   **Offset:** 0  
*   **Version Information:** The method for identifying specific SNU wrapper format versions is unclear. Identification relies more on parsing the header fields and the structure of the contained data (SPS vs SNR/SNS).  
    *   **Location:** N/A  
    *   **Data Type:** N/A  

---

## 3. Global Properties (If Applicable)

*   **Endianness:** Varies (Big-Endian or Little-Endian). Crucially, the 4-byte integer fields within the header (offsets 0x04, 0x08, 0x0C) can be either BE or LE, typically depending on the original game platform (e.g., PS3/Xbox 360 often use BE, PC often uses LE). Tools like vgmstream often deduce the correct endianness by examining the validity of the Start Offset value at 0x08.  
*   **Character Encoding:** ASCII (Observed for the embedded filename string within some SNU headers, Null-terminated).  
*   **Default Alignment:** Not definitively determined, but likely standard structure alignment is used.  
*   **Compression:** The Audio Data encapsulated within the SNU file is compressed. The specific codec (e.g., Electronic Arts EA-XAS 4-bit ADPCM v1) is determined by the contained SNR/SNS or SPS data structure. The SNU header itself is not compressed.  
*   **Encryption:** None observed.  

---

## 4. Detailed Structure

The .snu file consists of a Header followed by the main Audio Data block (structured as either SPS or SNR/SNS).  

**Section: SNU Header (First 16 Bytes)**  

The initial bytes provide offsets and basic hints about the contained stream.  

| Offset (Hex) | Offset (Dec) | Size (Bytes) | Data Type | Endianness | Field Name       | Description                                                                                                         | Notes / Example Value                       |
| :----------- | :----------- | :----------- | :-------- | :--------- | :--------------- | :------------------------------------------------------------------------------------------------------------------ | :------------------------------------------ |
| `0x00`       | 0            | 1            | `uint8`   | N/A        | Unknown Byte 0   | Purpose unclear. Potentially related to sample rate (e.g., observed 0x03 might correlate with 48000 Hz).             | `0x01`, `0x03` observed                     |
| `0x01`       | 1            | 1            | `uint8`   | N/A        | Unknown Byte 1   | Purpose unclear. Possibly flags or a count. May influence use of field at 0x0C or indicate extra data before main audio block. | `0x0C`, `0x00` observed                     |
| `0x02`       | 2            | 1            | `uint8`   | N/A        | Unknown Byte 2   | Purpose unclear. Often observed as 0x00.                                                                            | `0x00` observed                             |
| `0x03`       | 3            | 1            | `uint8`   | N/A        | Channel Count (?) | Usually indicates the number of audio channels (e.g., 1 for mono, 2 for stereo, 4 for quad). May sometimes be 0 (requiring check of internal header). | `0x01`, `0x02`, `0x04` observed             |
| `0x04`       | 4            | 4            | `uint32`  | BE or LE   | Size Value       | Exact meaning unclear. May relate to the number of audio frames (size >> 2 ~= number of frames noted by vgmstream). | e.g., `0x00000477`                          |
| `0x08`       | 8            | 4            | `uint32`  | BE or LE   | Start Offset     | Crucial Field: Byte offset within the SNU file where the main audio data block (SNS body or SPS header) begins. Used for endianness detection. | e.g., `0x00000B00`, `0x00000080`             |
| `0x0C`       | 12           | 4            | `uint32`  | BE or LE   | Sub-offset (?)   | Optional? Used in some cases (maybe indicated by byte at 0x01). Purpose uncertain, might point to secondary data. | e.g., `0x00000000`, `0x00000020`             |

*Note: Some SNU files observed in The Simpsons Game contain more extensive headers beyond these first 16 bytes, including metadata like the embedded filename, loop points, total samples, etc., before the main audio data block defined by the Start Offset.*  

**Section: Internal Structure Variants**  

The SNU header primarily points to the location of the main audio stream. The format of that stream determines how the rest of the file is parsed. This is typically identified by the first byte found at the Start Offset (from SNU header 0x08):  

*   **Contained SPS Structure:**  
    *   **Identifier:** The byte at Start Offset is `0x48` (ASCII 'H'). This signifies the start of an EA SPS header (EAAC_BLOCKID1_HEADER).  
    *   **Parsing:** The data from Start Offset onwards is parsed as an EA SPS stream.  
    *   **Examples:** Dead Space 3 (PC).  

*   **Contained SNR/SNS Structure:**  
    *   **Identifier:** The byte at Start Offset is NOT `0x48`.  
    *   **Parsing:** This indicates the older SNR/SNS structure. vgmstream typically assumes:  
        *   An SNR header (containing metadata like sample rate, channels, codec info) is located at a fixed offset (e.g., 0x10 within the SNU file).  
        *   The SNS audio body (containing the compressed audio data) begins at the Start Offset read from the SNU header (0x08).  
        *   The file is parsed according to EA SNR/SNS format rules.  
    *   **Examples:** The Simpsons Game (PS3 examples confirm this variant).  

**Section: Audio Data**  

*   **Location:** Starts at the Start Offset (if SNS) or follows the SPS header (if SPS).  
*   **Content:** Contains the actual audio samples, compressed using the codec specified by the internal SNR or SPS header (e.g., EA-XAS 4-bit ADPCM v1).  
*   **Layout:** The layout is defined by the internal format. For SNR/SNS, this is often "blocked (EA SNS)". For SPS, it might be different (potentially interleaved or other structures). Segmented layouts are also possible.  

---

## 5. Data Types Reference

*   **`uint8`:** Unsigned 8-bit integer.  
*   **`uint16_be` / `uint16_le`:** Unsigned 16-bit integer, Big-Endian / Little-Endian.  
*   **`uint32_be` / `uint32_le`:** Unsigned 32-bit integer, Big-Endian / Little-Endian.  
*   **`char[N]`:** Fixed-size array of N bytes, typically interpreted as a null-terminated ASCII string (for embedded filename).  
*   **`EA-XAS ADPCM`:** Electronic Arts Extended Audio Scheme ADPCM. A lossy audio compression codec.  
*   **`SNR` / `SNS`:** Older Electronic Arts audio format components; SNR is typically the header/metadata, SNS is the audio sample data body (often in blocks).  
*   **`SPS`:** Newer Electronic Arts audio format, often header-based and potentially containing various EAAC codecs.  

---

## 6. Checksums / Integrity Checks

*   None observed or known for the SNU wrapper format itself. The contained SPS/SNR formats might have internal checks.  

---

## 7. Known Variations / Versions

*   **Endianness:** Header fields (0x04, 0x08, 0x0C) can be Big or Little Endian.  
*   **Internal Structure:** Major variation between containing SPS vs SNR/SNS data.  
*   **Header Content:** Observed variations in header size and included metadata beyond the first 16 bytes (e.g., presence of filename, loop points).  
*   **Audio Parameters:** Variations in Sample Rate, Channel Count, and potentially the specific EAAC codec used internally.  

---

## 8. Analysis Tools & Methods

*   **Tools Used:** Hex Editor (e.g., HxD, 010 Editor), vgmstream / vgmstream-cli (Essential for decoding audio and extracting confirmed metadata).  
*   **Methodology:** Analysis of hex dumps, comparison between files, interpretation of output from vgmstream, cross-referencing documentation/source code related to EA formats (like vgmstream's implementation).  

---

## 9. Open Questions / Uncertainties

*   Confirmation of a universal SNU magic number/signature.  
*   Precise purpose and interpretation of header bytes 0x00, 0x01, 0x02.  
*   Exact meaning and calculation related to the Size Value at offset 0x04.  
*   Conditions under which the Sub-offset at 0x0C is used and what it points to.  
*   Are internal structures other than SPS and SNR/SNS possible within an SNU wrapper?  
*   The exact significance, if any, of intermediate file extensions like `.exa`.  

---

## 10. References

*   **Files Analyzed:**  
    *   `d_as01_xxx_0003bb5.exa.snu`  
    *   `amb_80b_crowd_qd_01.exa.snu`  
    *   `d_as01_xxx_000580c.exa.snu`  
*   **Tools:**  
    *   vgmstream (Source code provides implementation details).  

---

## 11. Revision History (of this document)

| Version | Date       | Author(s)                         | Changes Made                                                         |
| :------ | :--------- | :-------------------------------- | :------------------------------------------------------------------- |
| 1.0     | 2025-05-05 | Analysis based on user-provided data | Initial draft based on hex dump and vgmstream examples               |
| 2.0     | 2025-05-05 | Analysis based on user-provided data | Integrated detailed header info, endianness variations, SPS/SNR variants |

---

## 12. Other

**Conversion Example using vgmstream-cli:**  
To convert an SNU file to a standard WAV file:  

```powershell
# Example using PowerShell syntax
.\vgmstream-cli.exe -o "output_audio.wav" "input_audio.exa.snu"
```

**vgmstream Metadata Examples (The Simpsons Game - SNR/SNS Variant):**  

```
# Example 1: Mono Dialogue
> vgmstream-cli.exe -m .\d_as01_xxx_0003bb5.exa.snu
metadata for .\d_as01_xxx_0003bb5.exa.snu
sample rate: 48000 Hz
channels: 1
stream total samples: 54901 (...)
encoding: Electronic Arts EA-XAS 4-bit ADPCM v1
layout: blocked (EA SNS)
metadata from: Electronic Arts SNU header
...

# Example 2: Mono Dialogue
> vgmstream-cli.exe -m .\d_as01_xxx_000580c.exa.snu
metadata for .\d_as01_xxx_000580c.exa.snu
sample rate: 48000 Hz
channels: 1
stream total samples: 67200 (...)
encoding: Electronic Arts EA-XAS 4-bit ADPCM v1
layout: blocked (EA SNS)
metadata from: Electronic Arts SNU header
...

# Example 3: Quad Ambience
> vgmstream-cli -m .\amb_80b_crowd_qd_01.exa.snu
metadata for .\amb_80b_crowd_qd_01.exa.snu
sample rate: 32000 Hz
channels: 4
loop start: 1 samples (0:00.000 seconds)
loop end: 664812 samples (0:20.775 seconds)
stream total samples: 664812 (0:20.775 seconds)
encoding: Electronic Arts EA-XAS 4-bit ADPCM v1
layout: segmented (2 segments)
metadata from: Electronic Arts SNU header
bitrate: 610 kbps
play duration: 1649623 samples (0:51.551 seconds)