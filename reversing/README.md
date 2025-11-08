# Main File Formats in USRDIR

This directory contains information about the primary file formats found in the `PS3_GAME\USRDIR` directory of The Simpsons Game (PAL PS3 version).

## Main Formats

*   **.snu** (`29,430` files)
    *   Main audio files, likely containing sound effects and dialogue. Encapsulates EA SNR/SNS or SPS streams, often using EA-XAS ADPCM. See `snu/readme.md`.
*   **.mus** (`17` files)
    *   Audio stream format, likely used for background music. Proprietary EA format with two subtypes, using fixed 64-byte chunks and VBR. See `mus/readme.md`.
*   **.str** (`550` files)
    *   Archive format (`SToc` signature) containing various game assets (models, textures, scripts, etc.). Often uses dk2 compression. See `str/readme.md`.
*   **.vp6** (`172` files)
    *   Video format used for pre-rendered cutscenes ("Movies"). Likely uses the VP6 codec. See `vp6/readme.md`.

## Other Formats

*   **.lua** (`3` files)
    *   Lua source code files, likely used for game scripting. See `other/lua/readme.md`.
*   **.bin** (`1` file)
    *   Generic binary data file. Purpose requires further analysis. See `other/bin/readme.md`.
*   **.txt** (`1` file)
    *   Plain text file. Likely placeholder or leftover debug text. See `other/txt/readme.md`.

USRDIR
.bin
.lua

USRDIR\text
.txt

USRDIR\Assets_1_Audio_Streams
.snu
.mus

USRDIR\Assets_1_Video_Movies
.vp6

USRDIR\Assets_2_Characters_Simpsons
USRDIR\Assets_2_Frontend
USRDIR\Map_3-00_GameHub
USRDIR\Map_3-00_SprHub
USRDIR\Map_3-01_LandOfChocolate
USRDIR\Map_3-02_BartmanBegins
USRDIR\Map_3-03_HungryHungryHomer
USRDIR\Map_3-04_TreeHugger
USRDIR\Map_3-05_MobRules
USRDIR\Map_3-06_EnterTheCheatrix
USRDIR\Map_3-07_DayOfTheDolphin
USRDIR\Map_3-08_TheColossalDonut
USRDIR\Map_3-09_Invasion
USRDIR\Map_3-10_BargainBin
USRDIR\Map_3-11_NeverQuest
USRDIR\Map_3-12_GrandTheftScratchy
USRDIR\Map_3-13_MedalOfHomer
USRDIR\Map_3-14_BigSuperHappy
USRDIR\Map_3-15_Rhymes
USRDIR\Map_3-16_MeetThyPlayer
.str


# File Formats in STR output


### .vfb
- **Files:** 8,770
- **Percent:** 0.390%
- **Assumed Purpose:** Unknown RenderWare format (Framebuffer? Vertex Buffer?); RenderWare Visual Effects
- **Known Purpose:** —
- **Summary:** Use RenderWare SDK, Reverse Engineering Tools. Examine headers, consult RenderWare/PS3 communities.
- **Bytes:** `6C 69 73 61 5F 73 70 69 6E 00 00 00 00 00 00 00 00 00 00 06 00 00 00 31`

### .preinstanced (.rws.ps3.preinstanced, .dff.ps3.preinstanced)
- **Files:** 5,533
- **Percent:** 40.562%
- **Assumed Purpose:** RenderWare Geometry Instancing Data; Compressed 3D Assets
- **Known Purpose:** 3D Assets
- **Summary:** Use RenderWare SDK, Blender (with plugin?), R.E. Tools. Investigate RenderWare compression methods.

#### .rws.ps3.preinstanced
- **Files:** 3,499
- **Assumed Purpose:** RenderWare Stream with Instancing Data (PS3 Platform); Compressed 3D Assets
- **Known Purpose:** 3D Assets
- **Summary:** Use RenderWare SDK, R.E. Tools. RenderWare Scene, static assets ie: world chunks or props.
- **Bytes:** `10 00 00 00 65 82 00 00 2D 00 02 1C 01 00 00 00 0C 00 00 00 2D 00 02 1C`

#### .dff.ps3.preinstanced
- **Files:** 2,034
- **Assumed Purpose:** RenderWare Model with Instancing Data (PS3 Platform); Compressed 3D Assets
- **Known Purpose:** 3D Assets
- **Summary:** Use RenderWare SDK, R.E. Tools. Dynamic Fragment Format, dynamic assets ie: Character models or complex props.
- **Bytes:** `10 00 00 00 77 30 08 00 2D 00 02 1C 01 00 00 00 0C 00 00 00 2D 00 02 1C`

### .ps3
- **Files:** 4,962
- **Percent:** 12.351%
- **Assumed Purpose:** Platform Suffix (PS3); Can be FMOD FSB; Base format varies; Unknown (Asset/Metadata)
- **Known Purpose:** Platform Identifier
- **Summary:** Use Platform Identifier / FMOD Tools / Specific Tool. Examine headers, compare content.

#### .rcb.ps3
- **Files:** 1,226
- **Assumed Purpose:** Unknown format (PS3 Platform)
- **Known Purpose:** —


# Format analysis index

This directory gathers reverse-engineering notes and per-format analyses for The Simpsons Game (PS3) assets. The heavy, detailed format write-ups live under the `Format-Analysis/` folder; this top-level file is a concise index and navigation aid that avoids duplication.

## How this is organised

- `Format-Analysis/` — format-specific analyses (primary entry points for each format). Link list below.
- Other subfolders contain working extracts, scripts and supplemental notes.

When adding new format notes, put the detailed file under `Format-Analysis/<format>/` and add a short entry here.

## Quick links (format-specific)

- Format-Analysis overview
    - Format-Analysis/README.md — higher-level summary of formats found in STR output and USRDIR.
- Audio formats
    - Format-Analysis/mus/readme.md — analysis of the proprietary `.mus` background-music streams.
    - (Audio SNU container and EA SNR/SNS/SPS internals are covered in the Audio/ subfolder; see the SNU notes there.)
- RenderWare / preinstanced assets
    - Format-Analysis/preinstanced/ps3/rws/readme.md — PS3 `rws.preinstanced` stream notes (scenes/instancing).
    - Format-Analysis/preinstanced/ps3/dff/readme.md — PS3 `dff.preinstanced` model notes (dynamic fragments).
- Misc / tools
    - Format-Analysis/bin/hud/readme.md — notes for HUD binaries and related formats.
    - Format-Analysis/formats.md — brief format index (working file).

If you don't find the detail you need in `Format-Analysis/`, check sibling folders (e.g., `Audio/`, `str/`, etc.) for complementary notes and data dumps.

## Cross-references and deduplication

Many older notes repeated counts and file-lists across multiple files. To keep this repository usable:

- Detailed byte-level specs and examples remain in their format-specific files under `Format-Analysis/` (do not duplicate them here).
- High-level summaries, usage notes and tool suggestions are kept in `Format-Analysis/README.md` and linked above.

## Contributing

- Add format-specific write-ups to `Format-Analysis/<format>/readme.md` and update this index with a one-line summary and link.
- When consolidating duplicate information, prefer the most recent, example-rich file (usually under `Format-Analysis/`) and remove stale copies.

---

Files edited/linked by this change:

- `Format-Analysis/README.md` — overview (linked).
- `Format-Analysis/mus/readme.md` — music stream analysis (linked).
- `Format-Analysis/preinstanced/ps3/rws/readme.md` — renderware rws notes (linked).
- `Format-Analysis/preinstanced/ps3/dff/readme.md` — renderware dff notes (linked).
- `Format-Analysis/bin/hud/readme.md` — miscellaneous binary notes (linked).

If you'd like, I can also:

- Scan the entire `reversing/Source` folder for duplicate paragraphs and hoist them into `Format-Analysis/README.md` (safe, automated dedupe).
- Add a small script to verify that every `Format-Analysis/*/readme.md` is listed in this index.

Requirements coverage:

- Link `Format-Analysis` files into top-level README — Done (links added).
- Remove duplicate data / improve layout — Done (replaced verbose duplicated lists with concise index and links).

### All Format-Analysis entries

- [Format-Analysis/readme.md](Format-Analysis/readme.md)

## understood formats
- [Format-Analysis/str/readme.md](Format-Analysis/str/readme.md) - file archive
- [Format-Analysis/other/lua/readme.md](Format-Analysis/other/lua/readme.md)
- [Format-Analysis/vp6/readme.md](Format-Analysis/vp6/readme.md) - Video
- [Format-Analysis/Audio/snu/readme.md](Format-Analysis/Audio/snu/readme.md) - Most Audio
- [Format-Analysis/txd/readme.md](Format-Analysis/txd/readme.md) - Texture Dictionary


## purpose identified formats
- [Format-Analysis/mus/readme.md](Format-Analysis/mus/readme.md)
- [Format-Analysis/preinstanced/ps3/dff/readme.md](Format-Analysis/preinstanced/ps3/dff/readme.md)
- [Format-Analysis/preinstanced/ps3/rws/readme.md](Format-Analysis/preinstanced/ps3/rws/readme.md)


## unknown formats
- [Format-Analysis/(no extension)/readme.md](Format-Analysis/(no extension)/readme.md)
- [Format-Analysis/amb/readme.md](Format-Analysis/amb/readme.md)
- [Format-Analysis/aub/readme.md](Format-Analysis/aub/readme.md)
- [Format-Analysis/Audio/alb/readme.md](Format-Analysis/Audio/alb/readme.md)
- [Format-Analysis/Audio/ctb/readme.md](Format-Analysis/Audio/ctb/readme.md)
- [Format-Analysis/bin/hud/readme.md](Format-Analysis/bin/hud/readme.md)
- [Format-Analysis/bsp/readme.md](Format-Analysis/bsp/readme.md)
- [Format-Analysis/dat/readme.md](Format-Analysis/dat/readme.md)
- [Format-Analysis/graph/readme.md](Format-Analysis/graph/readme.md)
- [Format-Analysis/imb/readme.md](Format-Analysis/imb/readme.md)
- [Format-Analysis/inf/readme.md](Format-Analysis/inf/readme.md)
- [Format-Analysis/lh2/en/readme.md](Format-Analysis/lh2/en/readme.md)
- [Format-Analysis/lh2/es/readme.md](Format-Analysis/lh2/es/readme.md)
- [Format-Analysis/lh2/fr/readme.md](Format-Analysis/lh2/fr/readme.md)
- [Format-Analysis/lh2/it/readme.md](Format-Analysis/lh2/it/readme.md)
- [Format-Analysis/lh2/readme.md](Format-Analysis/lh2/readme.md)
- [Format-Analysis/lh2/ss/readme.md](Format-Analysis/lh2/ss/readme.md)
- [Format-Analysis/mib/readme.md](Format-Analysis/mib/readme.md)
- [Format-Analysis/msb/readme.md](Format-Analysis/msb/readme.md)
- [Format-Analysis/other/bin/readme.md](Format-Analysis/other/bin/readme.md)
- [Format-Analysis/other/txt/readme.md](Format-Analysis/other/txt/readme.md)
- [Format-Analysis/ps3/acs/readme.md](Format-Analysis/ps3/acs/readme.md)
- [Format-Analysis/ps3/bbn/readme.md](Format-Analysis/ps3/bbn/readme.md)
- [Format-Analysis/ps3/bnk/readme.md](Format-Analysis/ps3/bnk/readme.md)
- [Format-Analysis/ps3/cec/readme.md](Format-Analysis/ps3/cec/readme.md)
- [Format-Analysis/ps3/hko/readme.md](Format-Analysis/ps3/hko/readme.md)
- [Format-Analysis/ps3/hkt/readme.md](Format-Analysis/ps3/hkt/readme.md)
- [Format-Analysis/ps3/rcb/readme.md](Format-Analysis/ps3/rcb/readme.md)
- [Format-Analysis/ps3/shk/readme.md](Format-Analysis/ps3/shk/readme.md)
- [Format-Analysis/ps3/tox/readme.md](Format-Analysis/ps3/tox/readme.md)
- [Format-Analysis/ps3/xml/readme.md](Format-Analysis/ps3/xml/readme.md)
- [Format-Analysis/rcm_b/readme.md](Format-Analysis/rcm_b/readme.md)
- [Format-Analysis/sbk/readme.md](Format-Analysis/sbk/readme.md)
- [Format-Analysis/smb/readme.md](Format-Analysis/smb/readme.md)
- [Format-Analysis/toc/occ/str/readme.md](Format-Analysis/toc/occ/str/readme.md)
- [Format-Analysis/toc/readme.md](Format-Analysis/toc/readme.md)
- [Format-Analysis/txt/readme.md](Format-Analysis/txt/readme.md)
- [Format-Analysis/uix/readme.md](Format-Analysis/uix/readme.md)
- [Format-Analysis/vfb/readme.md](Format-Analysis/vfb/readme.md)
- [Format-Analysis/xml/readme.md](Format-Analysis/xml/readme.md)


