# TXD File Format Documentation

**Version**: Based on analysis dated `2025-05-11` (incorporating exporter script insights)
**Endianness**: Primarily Little-Endian, but specific metadata fields are Big-Endian.

## 1. Overview

A TXD file serves as a texture dictionary or archive, containing one or more texture images. Each image within the file includes a header, various metadata fields (such as texture name, dimensions, format flags), and the raw/compressed pixel data, which may be Morton swizzled for certain formats.

The file structure distinguishes between the very first image entry and all subsequent image entries using different initial header signatures. The provided exporter script further details how texture entries are identified and parsed within these broader segments.

## 2. General File Structure

A TXD file is a concatenation of image entries.

*   **Overall Segmentation**:
    *   The file may start with a `16000000` signature (First Image Header). Data associated with this generally extends until an `0300000014000000` marker.
    *   Subsequent image data blocks often start after an `0300000014000000` marker (where `14000000...` is the start of the Subsequent Image Header, and `03000000` is the terminator of the previous image's data).
    *   The exporter script uses these markers (`sig_file_start = b'\x16\x00\x00\x00'` and `sig_block_start = b'\x03\x00\x00\x00\x14\x00\x00\x00'`) to define "data segments" which are then scanned for individual texture entries.
    *   A fallback rule (Noesis-style) might process data from offset `0x28` if the file starts with `16000000` but other segmentation rules fail.

*   **Individual Texture Entries (within segments)**:
    *   Are identified by a specific texture name signature (`2D00021C0000000A`).
    *   Include fields for texture name, platform/format flags, a detailed 16-byte metadata block (dimensions, mipmap count, data size, format code), and pixel data.

*   **End of File (EOF)**: There is no explicit EOF marker. Parsing stops when no more valid image entries/segments are found. Truncated entries might exist.

## 3. Initial File Headers (Defining Segments)

These headers define large segments of the file, which are then further parsed for individual textures.

### 3.1. First Image Header Segment (Corresponds to `BYTES_A` of Script 1 in prior analysis)

This structure applies if the TXD file starts with `16000000`.

| Offset (Bytes) | Size (Bytes) | Value (Hex) / Description                                  | Notes                                                                                                |
|----------------|--------------|------------------------------------------------------------|------------------------------------------------------------------------------------------------------|
| 0              | 4            | `16000000`                                                 | First Image Segment Magic/Signature Start                                                            |
| 4              | 4            | Varies                                                     | Unknown flags or ID.                                                                                 |
| 8              | 4            | `2D00021C`                                                 | Signature Part                                                                                       |
| 12             | 4            | `01000000`                                                 | Constant                                                                                             |
| 16             | 4            | `04000000`                                                 | Constant                                                                                             |
| ...            | ...          | Data for the first image texture(s) follows.               | This segment often extends up to the first `0300000014000000` marker.                                  |

### 3.2. Subsequent Image Header Segment (Corresponds to `BYTES_A` of Script 2 in prior analysis)

These segments typically start after an `03000000` marker from a previous image.

| Offset (Bytes) | Size (Bytes) | Value (Hex) | Notes                                                                                                         |
|----------------|--------------|-------------|---------------------------------------------------------------------------------------------------------------|
| 0              | 4            | `14000000`  | Part of the Subsequent Image Header Block Signature                                                           |
| 4              | 4            | `2D00021C`  |                                                                                                               |
| 8              | 4            | `2FEA0000`  |                                                                                                               |
| 12             | 4            | `08000000`  |                                                                                                               |
| 16             | 4            | `2D00021C`  |                                                                                                               |
| ...            | ...          | Data for subsequent image texture(s) follows. | This segment often extends up to the next `0300000014000000` marker or EOF.                               |

## 4. Individual Texture Entry Structure (Within Segments)

Once a data segment is identified (as per section 3), it's scanned for individual texture entries using the following structure:

| Field Description                 | Size (Bytes) | Value (Hex) / Details                                                                 | Notes (Prior Script Ref if applicable)                                                                      |
|-----------------------------------|--------------|---------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------|
| Texture Name Signature Start      | 8            | `2D00021C0000000A`                                                                    | (Was `BYTES_G`) This signature indicates a potential texture name following.                                |
| Platform/Texture Format Flags     | 4            | One of: `00001102`, `00001106`, `00003302`, `00003306`                                  | (Was `BYTES_H`) Immediately follows the Name Signature Start. See Section 6.1 for values.                   |
| Texture Name                      | Variable     | UTF-8 encoded string, terminated by `0000` (double null).                               | (Was `BYTES_I`) Starts 4 bytes after the `...0000000A` part of the signature (i.e., after Platform/Format Flags). |
| (Padding/Unknown)                 | Variable     | Zero bytes until the first non-zero byte leading to the Metadata Block search markers.  |                                                                                                             |
| Metadata Block Pre-marker         | 2            | Unknown/Varies. These are the first 2 bytes of the 16-byte Metadata Block.              | Part of search logic: `meta_offset = offset_of_01_marker - 2`.                                              |
| Metadata Marker                   | 1            | `01`                                                                                  | Byte 3 of the 16-byte Metadata Block.                                                                       |
| Format Code                       | 1            | One of: `02`, `52`, `53`, `54`, `86`                                                    | (Was `BYTES_K`) Byte 4 of Metadata Block. See Section 6.2.                                                  |
| Texture Width                     | 2            | Image width in pixels.                                                                | Bytes 5-6 of Metadata Block. Big-Endian (`>H`).                                                             |
| Texture Height                    | 2            | Image height in pixels.                                                               | Bytes 7-8 of Metadata Block. Big-Endian (`>H`).                                                             |
| (Unknown/Padding)                 | 1            | Unknown.                                                                              | Byte 9 of Metadata Block.                                                                                   |
| Mipmap Count                      | 1            | Number of mipmap levels.                                                              | Byte 10 of Metadata Block.                                                                                  |
| (Unknown/Padding)                 | 2            | Unknown.                                                                              | Bytes 11-12 of Metadata Block.                                                                              |
| Total Pixel Data Size             | 4            | Total size in bytes for all mipmap levels of this texture's pixel data.                 | Bytes 13-16 of Metadata Block. Little-Endian (`<I`).                                                         |
| Pixel Data                        | Variable     | Raw or compressed pixel data, potentially Morton swizzled. Size given by Total Pixel Data Size. | Starts immediately after the 16-byte Metadata Block.                                                        |
| End of Current Image Data Marker  | 4            | `03000000`                                                                            | Marks the end of the current texture's complete data (including pixel data).                                |

**Note**: The fields previously identified as `BYTES_J` (5 bytes, Texture Parameters) and `BYTES_L` (12 bytes, Image Metadata) are now superseded by the more detailed 16-byte Metadata Block structure and the surrounding parsing logic described above.

## 5. Pixel Data Details

*   **Swizzling**:
    *   Format Code `0x86` (BGRA8888): Pixel data is Morton ordered. Requires unswizzling and channel conversion (BGRA to RGBA) for standard DDS output. Bytes per pixel for unswizzle: 4.
    *   Format Code `0x02` (A8 or P8A8/L8A8): Pixel data is Morton ordered.
        *   If `Total Pixel Data Size == Width * Height * 1`, it's A8 (1 byte per pixel for unswizzle). Converted to RGBA (R=G=B=0, Alpha=A8).
        *   If `Total Pixel Data Size == Width * Height * 2`, it's P8A8/L8A8 (2 bytes per pixel for unswizzle). Converted to RGBA (R=G=B=P8/L8, Alpha=A8).
*   **DXT Formats**:
    *   Format Codes `0x52` (DXT1), `0x53` (DXT3), `0x54` (DXT5): Pixel data is standard DXT compressed data and does not require unswizzling.

## 6. Observed Values for Specific Fields

### 6.1. Platform/Texture Format Flags (4 bytes, following Name Signature Start)

*   `00001102`
*   `00001106`
*   `00003302`
*   `00003306` (Notably more common in "Subsequent Image Entries") These likely indicate aspects like presence of mipmaps, perhaps related to the DXT compression type, or target platform/renderer capabilities.

### 6.2. Format Code (Byte 4 of 16-byte Metadata Block)

| Hex  | Decimal | Probable Format     | Swizzled | Notes in Exporter Script                                  |
|------|---------|---------------------|----------|-----------------------------------------------------------|
| `02` | 2       | A8 / P8A8 (L8A8)    | Yes      | Interpreted as Alpha8 or Palette8/Luminance8+Alpha8       |
| `52` | 82      | DXT1                | No       | Standard DXT1                                             |
| `53` | 83      | DXT3                | No       | Standard DXT3                                             |
| `54` | 84      | DXT5                | No       | Standard DXT5                                             |
| `86` | 134     | BGRA8888            | Yes      | Unswizzled to linear, then BGRA->RGBA for DDS (RGBA8888)  |

(The 5-byte "Texture Parameters" field (`BYTES_J`) from the previous documentation is not explicitly parsed by the new exporter script's metadata logic, its role and exact location relative to the new 16-byte metadata block are now less clear, possibly part of the "Padding/Unknown" before the `01 <fmt_code>` scan or incorporated into undocumented bytes within the 16-byte block.)

## 7. Notes and Further Observations

*   **Endianness for Metadata Block**:
    *   Texture Width: Big-Endian (`>H`)
    *   Texture Height: Big-Endian (`>H`)
    *   Total Pixel Data Size: Little-Endian (`<I`)
    *   Other single-byte fields (Format Code, Mipmap Count) are inherently endian-neutral.
*   **File Integrity**: Some TXD files may end with a truncated image entry.
*   **Morton Unswizzling**: The `morton_encode_2d` function in the exporter indicates a standard Z-order curve interleaving for swizzled formats. The `unswizzle_data` function reverses this.