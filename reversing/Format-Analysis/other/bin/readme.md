# File Format Documentation: HUD Layout Binary (“.hud.bin”)

**Version:** 0.3 (working notes)
**Last Updated:** 2025-09-29
**Author(s):** samarixum

---

## 1. Overview

* **Format Name:** PlayStation 3 HUD Layout Binary (engine-specific)
* **Common File Extension(s):** `.hud.bin`
* **Purpose/Domain:** Stores UI/HUD layout graphs (roots, background boxes, subtitle widgets, reticles, etc.) with transforms, sizes, colors, and a small set of typed properties.
* **Originating Application/System:** PS3 game content (assets extracted from `.str` package trees).
* **Format Type:** Binary
* **General Structure:**

  * **File-level header (big-endian u32 words)** with multiple canvas/viewport dimensions (see §2.1).
  * One or more **Node Records** forming a scene/graph.
    Each Node has:

    * a typed **name** (ASCII), prefixed by **u16 nameLen** and **u16 typeId**,
    * subsequent **numeric blocks** (floats/ints) for layout/transform,
    * occasional **RGBA** byte quads,
    * occasional **small integers** that behave like pixel sizes/margins.
  * In both observed files, **node sequences repeat** in consistent groups (same names in the same order with near-identical values), likely representing different UI states/localizations.

---

## 2. Identification

### 2.1 Header words (both files share the same header shape)

**Endian:** big-endian. The first 24 u32s decode to a repeating set of canvas/viewport sizes:

* `0x0120003F` (18874431) — **unknown header flag/version**
* `0x00000003`, `0x00000003` — **unknown counters/flags**
* **Dimensions (repeat in sets):**
  `0x00000280` = **640**, `0x00000140` = **320**
  `0x00000000`
  `0x000001E0` = **480**, `0x000001E0` = **480**, `0x000001E0` = **480**
  `0x00000000`
  `0x000002D0` = **720**, `0x000002D0` = **720**, `0x000002D0` = **720**
  `0x00000000`
  …then the first ASCII token “WHITE” appears soon after.

These 640/480/720 values look like base/half/double **render targets or reference resolutions**.

### 2.2 First clear ASCII identifier

* **String:** `WHITE`
* **Offset (frontend):** **0x58** (88)
* **Offset (all):** **0x58** (88)
  This string consistently follows the header dimension block and precedes the first `hud_root` group.

*No fixed “magic number” is present; recognition is via header pattern + early strings (`WHITE`, `hud_root`, `subtitlesBase`, etc.).*

---

## 3. Global Properties

* **Endianness:** **Big-endian** for integers and floats (verified across both files).
* **Character Encoding:** ASCII (null-terminated) for names/identifiers.
* **Default Alignment:** **4 bytes** (names padded to 4B boundary; numeric blocks aligned).
* **Compression:** **None** (both files are plainly readable).
* **Encryption:** **None** (no obfuscation; floats/ints/strings parse cleanly).

---

## 4. Observed / Example Files

There are only 3 .bin files in the game files (per your inventory):

* extracted from .str archives
* `STROUT\Assets_2_Characters_Simpsons\simpsons_chars_global_str\build\PS3\pal_en\assets\shared\ui\hud\hud_simpsons_all.hud.bin`

  * **Size:** **1,019,240 bytes (0xF8D68)** (confirmed)
* `STROUT\Assets_2_Frontend\frontend_str\build\PS3\pal_en\assets\shared\ui\hud\hud_simpsons_frontend.hud.bin`

  * **Size:** **6,272 bytes** (confirmed)

*Notes:* the EBOOT.BIN is a regular PS3 boot file and not covered here (`\USRDIR\EBOOT.BIN`).

---

## 5. Data Types Reference

**All numeric fields are big-endian unless stated otherwise.**

* **u16** — frequently used for **name length** and a **type id** immediately before each ASCII name.
  Examples from both files:

  * `00 09 00 03 "hud_root"` → nameLen=9, typeId=**0x0003**
  * `00 0E 00 02 "subtitlesBase"` → nameLen=14, typeId=**0x0002**
* **ASCII (NUL-terminated)** — node/asset identifiers. After the name, **NUL padding** extends to the next 4-byte boundary.
* **u32 blocks** — appear after the name (purpose unclear; often large non-small values, so **not child counts**; likely flags/offsets or packed fields).
* **float (IEEE-754, BE)** — layout/transform parameters; recurring values:

  * `3F 80 00 00` = **1.0** (identity)
  * `3D AA AA AB` ≈ **0.0833333** (1/12)
  * `3E 2A AA AB` ≈ **0.1666667** (1/6)
  * `3F 19 99 9A` ≈ **0.6**
  * `3F 51 C7 1C` ≈ **0.81944**
  * Tiny paddings: `3B 19 99 9A` ≈ **0.00234**, `3B 08 88 89` ≈ **0.00208**
  * Occasional negatives: `BE B9 99 9A` ≈ **−0.3625**
* **RGBA (bytes)** — inline near “Bg/Box” nodes:

  * `F0 F0 F0 FF` (light gray, opaque), `FF 00 00 00`, `FF 00 FF FF` (white/magenta-ish)
  * **Byte order appears to be R, G, B, A.**
* **u32 “pixel-like” ints** — small integers (e.g., **120**, **59**, **60**) adjacent to subtitle box nodes; likely **width/height/margins**.

---

## 6. Checksums / Integrity Checks


---

## 7. Known Variations / Versions

* **frontend:** multiple **repeated node groups** with identical name order and similar values → likely distinct frontend states/localizations.
* **all:** very large set of groups with HUD roots, pause HUD, normal HUD, reticle elements, etc., repeating in **predictable clusters**.

---

## 8. Analysis Tools & Methods

* `strings -a` to enumerate identifiers.
* Heuristic scanner for **[u16 nameLen][u16 typeId][ASCII name][NUL pad→4B]**, then collection of nearby u32/floats/colors to characterize fields.
* Manual hex inspection of header **u32** blocks → resolution sets (640/320, 480, 720).

Interactive dumps are provided above for your review.

---

## 9. Open Questions / Uncertainties

* **Header semantics:** `0x0120003F`, `0x00000003`, and the repetition pattern of dimension tuples (640,320 / 480 / 720) need labeling (platform targets? safe zones?).
* **Post-name u32s:** immediately after names we do **not** see small child/prop counts; values look like large bitfields or offsets. Exact meaning TBD.
* **Transforms:** whether the float block is **SRT** vs a fixed **matrix** (3×3/4×4) and the exact ordering still need proofing across more node types.
* **Grouping/duplication:** repeated node sequences likely correspond to **frontend/ingame states** or **localization variants**; final mapping unconfirmed.

---

## 10. References / Source Notes

All observations derive from the actual files:

* `hud_simpsons_frontend.hud.bin` (6,272 bytes)
* `hud_simpsons_all.hud.bin` (1,019,240 bytes)

Key identifier offsets (selected):

| Identifier        |                           Frontend offsets |                                    All-HUD offsets |
| ----------------- | -----------------------------------------: | -------------------------------------------------: |
| `WHITE`           |                                       0x58 |                                               0x58 |
| `hud_root`        |                                0xA0, 0xCB8 |                                      0xA0, 0x7C72C |
| `subtitlesBase`   |  0xEC, 0x4D4, 0x8BC, 0xD04, 0x114C, 0x1594 |  0xEC, 0x7BA80, 0x7C0FC, 0x7C7F8, 0xF86AC, 0xF8F38 |
| `subtitlesRoot`   | 0x16C, 0x554, 0x93C, 0xD84, 0x11CC, 0x1614 | 0x16C, 0x7BB10, 0x7C184, 0x7C880, 0xF8734, 0xF8FC8 |
| `subtitleBg*`     |                     many within each group |                                       many (dense) |
| `igc_subtitleBox` |                         present (repeated) |                                 present (repeated) |
| `hud_pause_root`  |                                          — |                                     0x708, 0x7CFA4 |
| `normal_HUD`      |                                          — |                                     0x758, 0x7CFF4 |

*(Full lists are visible in the interactive tables.)*

---

## 11. Revision History

| Version | Date       | Author(s) | Changes Made                                                                                                                             |
| :------ | :--------- | :-------- | :--------------------------------------------------------------------------------------------------------------------------------------- |
| 0.3     | 2025-09-29 | samarixum | Incorporated real-file parses: header dimensions, offsets for key identifiers, sizes; clarified that post-name u32s aren’t child counts. |

---

## 12. Other

### Provisional Node Record Layout (updated from live files)

```
Offset  Size  Type       Meaning
------  ----  ---------  ----------------------------------------------
+0x00   0x02  u16 (BE)   name_length (bytes, not incl. NUL)
+0x02   0x02  u16 (BE)   type_id (observed examples: 0x0002, 0x0003, …)
+0x04   var   ASCII      name (e.g., "hud_root", "subtitlesBase", …)
+..     pad   —          NUL padding to 4-byte boundary
+..     0x08  u32,u32    **Unknown** (NOT small counts; likely flags/offsets)
+..     var   float[]    layout & scaling (identity 1.0s common; BE floats)
+..     var   bytes[4]?  optional RGBA quads near “Bg/Box” nodes (R,G,B,A)
+..     var   u32        small pixel-ish ints (e.g., 120, 59, 60)
(repeats; nodes appear in stable, repeated sequences)
```

**Typical value patterns**

* **Identity transforms** (1.0 with surrounding zeros)
* **Fractional paddings/anchors** (1/12, 1/6)
* **Tiny paddings** (~0.002–0.003)
* **Inline RGBA** near background/box elements
* **Small ints** ≈ pixel sizes
