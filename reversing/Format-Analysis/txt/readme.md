# Documentation: Usage of .txt Files in The Simpsons Game (2007)


## Overview

While `.txt` is a standard plain text file format, within the extracted assets of 'The Simpsons Game (2007)', these files are primarily observed serving specific, structured roles related to game configuration and metadata, rather than containing large blocks of narrative text or raw game data directly. They often act as human-readable configuration or mapping files used by the game engine.

Two distinct `.txt` formats are present in the samples attached here:

- `localereftable*.txt` — a locale reference table that maps language codes to language resource IDs and a numeric hash/checksum (this is described in detail in the next section).
- `localetable.txt` — a small table describing available locales and some metadata (newly observed; example included below).

## Primary Observed Use Case: Locale Reference Tables

The most prominent example identified is the `localereftable*.txt` file format (e.g., `localereftableD4815ED6.txt`).

### Purpose:

*   These files function as master indices or mapping tables for the game's localization system.
*   They link abstract language identifiers (like locale codes) to specific game resources that contain the actual translated text strings.

### Structure and Usage of localereftable*.txt

This file acts as the Locale Reference Table, mapping language codes to their corresponding resource packages within the game's assets. It dictates which data to load based on the selected language. The two `localereftableD4815ED6.txt` examples we have (one from frontend, one from character assets) both show a leading header value of `2`, followed by per-language blocks that match the format described below.



**Element Breakdown:**

*   **Header Value (Line 1): `2`**
    *   **Type:** Integer.
    *   **Usage:** The exact purpose of this initial number is unclear from the data alone. It could potentially represent:
        *   A version number for the `localereftable` format itself.
        *   A flag or type identifier used by the engine's parsing logic.
        *   A count of some property (though it doesn't obviously match field counts).
    *   **Conclusion:** Treat as engine-specific metadata; its precise function requires deeper analysis or engine reverse-engineering. The two attached `localereftableD4815ED6.txt` samples both start with `2`.

*   **Language Definition Blocks (Lines 2 onwards):**
    *   The rest of the file consists of repeating blocks, each defining one available language. Each block has three lines:

    *   **Line 1: Language Code (e.g., `en`)**
        *   **Type:** String (typically 2 characters).
        *   **Usage:** Represents the specific language (e.g., `en` for English, `fr` for French, `es` for Spanish). These are standard or internal codes used to identify the language setting.
        *   **Note:** The code `ss` is non-standard and likely serves as an internal placeholder or identifier for a specific variant or test language.

    *   **Line 2: Resource Identifier String (e.g., `frontend\text\81DE1738`)**
        *   **Type:** String.
        *   **Usage:** This line contains the crucial Language Resource ID.
            *   **Hexadecimal ID (e.g., `81DE1738`):** This part is the core identifier. It's a unique ID (likely a hash) assigned to the data package containing the strings for the language specified on the previous line (`en` in this case). This ID is used consistently across different game modules (maps, frontend, characters, etc.) to refer to the English language assets for that module.
            *   **Path Prefix (e.g., `frontend\text\`):** The significance of this prefix is less certain. It might indicate a base or default path, perhaps relevant primarily for frontend assets or reflecting where the table was generated. The game likely extracts the Hexadecimal ID and uses it in conjunction with the current module's path (e.g., `Map_3-01_LandOfChocolate\text\`) to find the actual resource directory (e.g., `Map_3-01_LandOfChocolate\text\81DE1738_str...`).
        *   **Function:** The engine parses this line primarily to extract the Hexadecimal Language Resource ID.

    *   **Line 3: Numerical Hash / Checksum (e.g., `-2116151496`)**
        *   **Type:** Signed 32-bit Integer.
        *   **Usage:** This number is highly likely a checksum or hash value associated with the language resource package. Potential uses include:
            *   **Data Integrity:** The engine might load the resource package identified by the Hexadecimal ID (e.g., `81DE1738`) and compute its hash, comparing it against this stored value (`-2116151496`) to verify that the data files are not corrupted or modified.
            *   **Internal Indexing:** Could potentially be used as a secondary key or identifier within the game's internal asset management system.
            *   **Version Check:** The hash might change if the language pack contents are updated, providing a simple version check mechanism.
        *   **Basis:** It's most plausible that this hash is calculated based on the contents of the actual language resource files associated with the Hexadecimal ID.

**Overall Workflow:**

The game likely uses this file as follows:

1.  Reads the player's language setting (e.g., `es`).
2.  Scans the `localereftable` for the `es` code line.
3.  Reads the next line to get the Resource Identifier String (`frontend\text\2919CD42`).
4.  Extracts the Hexadecimal Language Resource ID (`2919CD42`).
5.  Reads the next line to get the Numerical Hash (`689556802`).
6.  Determines the current game module context (e.g., `Map_3-05_MobRules`).
7.  Constructs the path to the required resource (e.g., `Map_3-05_MobRules\text\2919CD42_str...`).
8.  Loads the data from that location.
9.  Optionally, calculates a hash of the loaded data and compares it with the Numerical Hash (`689556802`) for validation.


## Observed file: `localetable.txt`

Location (example): `USRDIR\text\localetable.txt`

Contents (example extracted):

```
5
BLES00142
pal_en
0
1
en
en
English
1
(none)
fr
fr
French
0
FR
it
it
Italian
0
IT
es
es
Spanish
0
ES
ss
en
StringIDs
0
(none)
```

Interpretation (tentative):

- The file begins with a small integer (`5` in the sample). This likely denotes a count or version identifier related to how many language blocks or entries follow, although the number's exact meaning is ambiguous without engine parsing logic.
- The next entries (`BLES00142`, `pal_en`) look like identifiers for the build/region and the primary locale pack used for that build (`pal_en` in this example).
- Following that are repeating blocks describing languages. Each language block in the sample appears to contain several short lines with the following recurring items (order inferred from the sample):
    - a short code (e.g., `en`, `fr`, `it`, `es`, `ss`)
    - a resource/locale alias or fallback code (e.g., `en`, `fr`)
    - a human-readable display name (e.g., `English`, `French`)
    - an integer flag or ordering value (e.g., `1` / `0`), possibly indicating default/available/priority
    - an optional region suffix or uppercase country code (e.g., `FR`, `IT`, `ES`) or `(none)` when not present

- The `ss` entry in the sample appears to be a special or internal entry. It pairs `ss` with `en` and `StringIDs`, which suggests an internal mapping used by the engine (for example, a placeholder or alternate string-id based mapping). The `StringIDs` token looks like a label or group name rather than a language name.

Usage hypothesis:

- `localetable.txt` appears to provide a compact list of locales supported by the build along with small per-locale metadata (display name, fallback code, flags, and optional region code). The engine likely reads this file early to populate language selection UI and to decide which language packs are permitted/available for the running build/region.

Note: precise semantics (what each small integer or field exactly means) requires additional engine reverse-engineering or cross-referencing with code that reads this file. The above interpretation is based purely on the observed sample and common patterns in game locale tables.

### Filename Convention:

*   The filenames typically include `localereftable` and end with a hexadecimal hash (e.g., `D4815ED6`), likely identifying the table itself or the asset group it belongs to.

### Location & Scope:


locations
USRDIR\text\localetable.txt
(these two are extracted from the .str archive files)
STROUT\Assets_2_Characters_Simpsons\simpsons_chars_global_str\build\PS3\pal_en\assets_rws\simpsons_chars\simpsons_chars\text\localereftableD4815ED6.txt
STROUT\Assets_2_Frontend\frontend_str\build\PS3\pal_en\assets_rws\frontend\frontend\text\localereftableD4815ED6.txt


*   These files were found within specific asset directories related to text (e.g., `ASSET_RWS\text` within `frontend_str` and `simpsons_chars_global_str`).
*   The observation of identical `localereftable*.txt` files in multiple locations suggests they may represent a global or core definition of supported languages and their primary resources, potentially duplicated across different asset packages for accessibility during loading.

### Functionality:

*   The game engine likely reads this file upon initialization or when loading relevant assets.
*   When the player selects a language, the engine uses the corresponding language code to look up the associated Resource Identifier in this table.
*   It then uses that identifier (e.g., `81DE1738`) to locate and load the appropriate package/directory containing the actual localized strings (e.g., the directory `81DE1738_str++EU_EN++assets++localization`).

## Other Potential Uses (Requires Further Investigation)

While not directly observed in the provided examples, `.txt` files could potentially be used for:

*   **Simple Configuration:** Storing basic key-value settings, although formats like `.ini` or custom binary formats are also common.
*   **Debug Information:** Leftover debug flags or logs (less likely in final release builds).
*   **Basic Data Lists:** Simple lists of items, properties, or other data points not complex enough to warrant a database or binary format.
*   **Actual String Data:** It is possible that the final string files located within the language-specific directories (e.g., inside `81DE1738_str++...`) could themselves be plain `.txt` files. This needs to be verified by examining the contents of those directories. Often, however, games use formats like `.xml`, `.csv`, or custom binary formats for the actual string tables for efficiency or added features.

## Summary

In 'The Simpsons Game (2007)', `.txt` files, particularly the `localereftable` variants, serve a critical role in the localization system by providing a structured, human-readable map between language codes and the game's localized text resources. Their usage appears focused on configuration and metadata rather than direct storage of extensive game content.