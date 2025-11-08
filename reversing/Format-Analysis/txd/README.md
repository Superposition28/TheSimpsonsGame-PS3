
this format is mostly understood
the extraction scripts can always be improved but from tests seem to work reliably

can be extracted using one of three extractors
1 - RemakeEngine txd built in handler (EngineNet\Core\FileHandlers\TxdExtractor\Main.cs)
2 - my custom all in one py script (Export_txd.py)
3 - Noesis plugin (tex_TheSimpsonsGame_PS3_txd.py)

the noesis plugin is dependent on the noesis software (https://richwhitehouse.com/index.php?content=inc_projects.php&showproject=91)
however it was the original extractor that my extractors are based on



# File Format Documentation: `.txd` (EA/RenderWare variant, PS3—“The Simpsons Game”)

**Version:** 1.0
**Last Updated:** 2025-10-09
**Author(s):** samarixum

---

## 1. Overview

* **Format Name:** EA/RenderWare-era “Texture Dictionary” (custom variant used by *The Simpsons Game* on PS3)
* **Common File Extension(s):** `.txd`
* **Purpose/Domain:** Texture container (dictionary of textures) with console-native payloads (DXT, swizzled raw, etc.)
* **Originating Application/System:** EA title built on/around RenderWare-era tooling. Confirmed target: PS3 build of *The Simpsons Game*.
* **Format Type:** Binary
* **General Structure:** A leading 0x16 marker (RenderWare “Texture Dictionary” ID) followed by one or more **segments** containing repeated **Texture Records**. Segments and end-of-file are delimited by bespoke marker sequences rather than canonical RW chunk headers.

---

## 2. Identification

* **Magic Number(s) / Signature:** `16 00 00 00` (little-endian `0x00000016`) at file start.

  * **Offset:** `0x00`

* **Version Information:**
  No explicit human-readable or numeric “version” field is exposed. The format relies on marker patterns and ad-hoc metadata; fields such as width/height/mip count are embedded in per-texture metadata blocks.

---

## 3. Global Properties (If Applicable)

* **Endianness:** Mixed

  * Global markers and most counters: **Little-Endian**
  * Texture metadata width/height: **Big-Endian** (`>H`)
  * Texture metadata data-size field: **Little-Endian** (`<I`)
* **Character Encoding:** UTF-8 for texture names (NUL-terminated by **double** `00 00`)
* **Default Alignment:** Not formally defined; zero padding occurs between fields. Texture names followed by zero runs up to the next non-zero control byte.
* **Compression:** None at container level. Texture payloads may be **block-compressed** (DXT1/3/5) or raw/swizzled (BGRA, A8, P8A8).
* **Encryption:** None observed.

---

## 4. Detailed Structure

### 4.1. File-Level Markers

**Primary file/segment markers:**

| Name                                          | Bytes (hex)                                    | Notes                                                                                |
| --------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------ |
| **SIG_FILE_START**                            | `16 00 00 00`                                  | At `0x00`. Indicates RW Texture Dictionary ID reused as a file preamble.             |
| **SIG_BLOCK_START / SIG_COMPOUND_END_MARKER** | `03 00 00 00 14 00 00 00`                      | Used both to mark starts of “0x14 blocks” and as a generic “compound end” delimiter. |
| **EOF Signature (composite)**                 | `EOF_PREFIX` + 8 variable bytes + `EOF_SUFFIX` | See below. Treated as hard terminator.                                               |

**EOF composite pattern:**

* `EOF_PREFIX`
  `03 00 00 00 14 00 00 00 2D 00 02 1C 2F EA 00 00 08 00 00 00 2D 00 02 1C`
* **8 variable bytes**
* `EOF_SUFFIX`
  `03 00 00 00 00 00 00 00 2D 00 02 1C`

> The scanner insists there is **exactly one** EOF composite in a valid file.

---

### 4.2. High-Level Layout (observed)

1. **Header stub (0x16)**
   If the file starts with `0x16 00 00 00`, scanning begins after this dword (often the first “segment” is the bytes immediately following).
   The implementation may also fall back to scanning from `0x28` if markers/EOF aren’t cleanly found.

2. **One or more “segments”**
   A segment is simply a contiguous byte range selected by the scanner: from after a file/marker position up to the next **SIG_BLOCK_START** (or EOF composite). The container uses **SIG_BLOCK_START** both as a delimiter and as a “compound end” marker.

3. **Inside each segment: repeated Texture Records**
   Each record comprises:

   * A **Texture Name Signature**
   * A **UTF-8 name** (double-NUL terminated)
   * Zero padding (one or more `0x00`)
   * A **metadata preamble** with an `0x01 <fmt_code>` tag
   * A **16-byte metadata block** (see table below)
   * The **pixel data blob** of `total_pixel_data_size` bytes

---

### 4.3. Texture Name Signature & Name String

**Texture Name Signature:** `2D 00 02 1C 00 00 00 0A` (8 bytes)

Immediately following the signature:

| Offset (rel. to signature start) |     Size | Type             | Field                    | Description                                                          |
| -------------------------------- | -------: | ---------------- | ------------------------ | -------------------------------------------------------------------- |
| `+0x00`                          |        8 | bytes            | `TEXTURE_NAME_SIGNATURE` | Constant                                                             |
| `+0x08`                          |        4 | bytes            | (unknown)                | Skipped by parser (name starts after 12 bytes total)                 |
| `+0x0C`                          | variable | `char[]` (UTF-8) | **TextureName**          | Read until **double** `00 00`. Parser then steps past the `00 00`.   |
| (next)                           |       ≥1 | zero bytes       | padding                  | Parser scans forward to the first non-zero to begin metadata search. |

**Notes:**

* The name is sanitized to produce a filesystem-safe filename for export.
* If parsing fails or yields empty, a fallback like `texture_at_0xXXXXXXXX` is used.

---

### 4.4. Metadata Discovery Preamble

After the zero padding following the name, the parser searches forward for the sequence:

```
0x01 <fmt_code>
```

If found at offset `X`, the **metadata block start** is defined as `X - 2`, and the 16-byte metadata block is read from there. If this pattern isn’t found, the texture is considered malformed.

---

### 4.5. 16-Byte Texture Metadata Block

**Layout (relative to start of the 16-byte block):**

| Off (hex) | Size | Type     | Endian | Name                      | Description                                                               |
| --------- | ---: | -------- | ------ | ------------------------- | ------------------------------------------------------------------------- |
| `0x00`    |    1 | `uint8`  | —      | `meta0`                   | Unknown/marker (precedes 0x01)                                            |
| `0x01`    |    1 | `uint8`  | —      | `meta1`                   | Unknown/marker                                                            |
| `0x02`    |    1 | `uint8`  | —      | `marker01`                | **Expected to be `0x01`** (aligns with the discovered preamble)           |
| `0x03`    |    1 | `uint8`  | —      | `fmt_code`                | Pixel format code (see table below). Must match the scanned `<fmt_code>`. |
| `0x04`    |    2 | `uint16` | **BE** | `width`                   | Texture width                                                             |
| `0x06`    |    2 | `uint16` | **BE** | `height`                  | Texture height                                                            |
| `0x08`    |    1 | `uint8`  | —      | `meta8`                   | Unknown/flags                                                             |
| `0x09`    |    1 | `uint8`  | —      | `mip_map_count_from_file` | Mip count byte as stored                                                  |
| `0x0A`    |    1 | `uint8`  | —      | `metaA`                   | Unknown/flags                                                             |
| `0x0B`    |    1 | `uint8`  | —      | `metaB`                   | Unknown/flags                                                             |
| `0x0C`    |    4 | `uint32` | **LE** | `total_pixel_data_size`   | Size in bytes of the subsequent pixel data blob                           |

**Validation rules (as enforced by the script):**

* `width` and `height` must be non-zero (both zero → placeholder; skip).
* `total_pixel_data_size` must be non-zero and must fit within the segment.
* The `fmt_code` in this block **must** match the `fmt_code` discovered by the `0x01 <fmt_code>` preamble.

---

### 4.6. Pixel Data Blob

* **Location:** Immediately after the 16-byte metadata block.
* **Length:** `total_pixel_data_size` bytes (from metadata).

**Formats (by `fmt_code`):**

| `fmt_code` | Meaning                      | Handling                                                                                                                                                                   |
| ---------: | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|     `0x52` | DXT1                         | Exported directly as DDS with DXT1 header; payload copied verbatim.                                                                                                        |
|     `0x53` | DXT3                         | As above (DXT3).                                                                                                                                                           |
|     `0x54` | DXT5                         | As above (DXT5).                                                                                                                                                           |
|     `0x86` | Swizzled BGRA8               | Morton (Z-order) unswizzle (4 bpp) → channel swap to RGBA → DDS (uncompressed RGBA).                                                                                       |
|     `0x02` | Swizzled A8 **or** P8A8/L8A8 | Size check determines sub-case: A8 (`W*H*1`) → RGBA with A; P8A8 (`W*H*2`) → expand to grayscale RGB + alpha. Both require Morton unswizzle, then DDS (uncompressed RGBA). |

**Morton/Z-order Unswizzle:**
Indexing uses `morton_encode_2d(x, y)` with interleaved bits. The script iterates all `x ∈ [0..W-1], y ∈ [0..H-1]`, reads `bytes_per_pixel` at `morton_idx * BPP`, and writes to linear `((y*W) + x) * BPP`.

**Mipmaps:**
A `mip_map_count_from_file` byte is present in metadata; the pixel blob as exported by this tool appears to contain **only the base payload** (no per-mip size table inside this variant). DDS headers are synthesized to include the reported mip count where applicable, but additional mip levels are **not** individually parsed/written from this container in the provided script.

---

## 5. Data Types Reference

* `uint8`, `uint16`, `uint32`: Standard unsigned integers.
* Endianness is **field-specific** (see tables).
* `char[]` (UTF-8): Name string, terminated by **`00 00`**.
* **Morton ordering**: Interleaved-bit indexing (`x` spread to even bits, `y` to odd bits).

---

## 6. Checksums / Integrity Checks

* **Type:** None observed.
* **Location/Scope:** N/A
* **Algorithm Details:** N/A

---

## 7. Known Variations / Versions

* **This document:** PS3 variant used by *The Simpsons Game*.
* **How it differs from “standard” RW TXD:**

  * Uses bespoke marker sequences and a compact 16-byte metadata block instead of canonical nested RW chunk headers.
  * Mixed endianness in metadata (BE dims, LE sizes).
  * Platform-native payloads with explicit **Morton swizzle** handling.
* **Other ecosystems (not covered here):** GTA/PC TXD (classic RW) uses proper RW chunking, FourCCs/flags inside chunk data, and fully little-endian streams.

**How to Differentiate (detection strategy):**

1. Try parsing as canonical RenderWare chunks (12-byte headers with consistent `id/size/version`).
2. If that fails but `0x16` exists and the bespoke markers & EOF composite appear, treat as **EA/Simpsons PS3 TXD** and use this spec.

---

## 8. Analysis Tools & Methods

* **Tools Used:** Python 3, custom scanners/converters (provided scripts), hex editor.
* **Methodology:** Static binary analysis; signature counting; controlled extraction using deterministic rules; format inference from constant patterns; validation via successful DDS exports per texture.

---

## 9. Open Questions / Uncertainties

* **Unknown metadata bytes:** `meta0`, `meta1`, `meta8`, `metaA`, `metaB`—likely flags/stride/tiling hints or platform plugin remnants.
* **Mipmaps:** Whether additional mip levels are ever present/encoded and how they would be delimited (no per-mip table is parsed in this variant).
* **Marker semantics:** Dual use of `SIG_BLOCK_START` as both “start” and “compound end” delimiter is unconventional; exact authoring intent is unknown.
* **EOF composite 8-byte variable area:** Purpose unspecified (timestamp? size? checksum seed?).

---

## 10. References

* **Primary sources:**

  * *Noesis* loader snippet (initial prototype).
  * **Full Python exporter** in the prompt (scanner + metadata + converter + DDS writer).
* **Artifacts:** Real `.txd` samples from *The Simpsons Game* (PS3) analyzed by the provided scripts.

---

## 11. Revision History (of this document)

| Version | Date       | Author(s) | Changes Made                                     |
| :------ | :--------- | :-------- | :----------------------------------------------- |
| 1.0     | 2025-10-09 | samarixum | Completed field tables & detection guidance      |

---

## 12. Other

### DDS Export Notes

* **DXT (0x52/0x53/0x54):**
  DDS header uses `DDSD_LINEARSIZE`; FourCC set to `DXT1`/`DXT3`/`DXT5`. Pixel data is copied verbatim.
* **RGBA paths (0x86, 0x02):**
  DDS header uses uncompressed `RGBA8888` masks. For `0x86`, channels are **BGRA→RGBA** post-unswizzle. For `0x02`, either expand **A8** to RGBA(0,0,0,A) or **P8A8** to RGBA(L,L,L,A).

### Error Policy (as implemented)

* The extractor treats many anomalies as **fatal** (missing markers, size mismatches, name parse failure without fallback, metadata mismatch).
* For automation or batch processing, consider adding “warn and skip” modes for resilience.

---

### Quick Field Summary (cheat sheet)

* **File start:** `16 00 00 00`
* **Texture name sig:** `2D 00 02 1C 00 00 00 0A` → skip 12 bytes → UTF-8 name until `00 00`
* **Find meta preamble:** scan to first non-zero → search `01 <fmt>`; metadata at `(preamble_offset - 2)`
* **Metadata (16 bytes):**
  `?? ?? 01 fmt | width_BE height_BE | ?? mip ?? ?? | size_LE`
* **Payload:** `size_LE` bytes immediately after metadata
* **Formats:** `52=DXT1, 53=DXT3, 54=DXT5, 86=swizzled BGRA, 02=A8/P8A8 (swizzled)`
* **Unswizzle:** Morton/Z-order (per-pixel, BPP=1/2/4 as per format)
