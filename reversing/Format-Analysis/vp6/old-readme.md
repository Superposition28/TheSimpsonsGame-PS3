# Simpsons Game `.vp6` Video Format

**File Extension:** `.vp6`

**Origin:** The Simpsons Game (PAL PS3 Version analyzed, likely similar across platforms).

**Purpose:** Contains interleaved video and audio data, primarily used for pre-rendered cutscenes, attract loops, and other in-game movies.

**Structure:** These files use a chunk-based structure common in EA formats. Key chunks identified include:

* **`SCHl` (Sound Chunk Header - lowercase 'l'):** Header for the primary/standard audio stream. Contains metadata about the audio codec, sample rate, channels, etc. Hex: `53 43 48 6C`.
* **`SHxx` (Sound Header - Localized):** Header for language-specific audio streams (e.g., `SHEN` for English, `SHFR` for French). These share a common base ID (`0x53480000`) combined with a 2-character language code (e.g., `EN` = `0x454E`). Multiple `SHxx` chunks can exist in a single file for different languages.
* **`MVhd` (Movie Header):** Contains metadata about the video stream, including the codec identifier. Hex: `4D 56 68 64`.
* Other chunks related to audio data (`SCDl`, `SCCl`, etc.) and video data (`MV0K`, etc.) follow their respective headers.

**Observations from Hex Dumps (`attractloop.vp6`, `loc_igc01.vp6`):**

* In the analyzed files from *The Simpsons Game*, the `SCHl` audio header chunk appears **at the very beginning** of the file (offset 0x00).
* The `MVhd` video header chunk appears shortly after the `SCHl` chunk (offset 0x2C in the examples).

**Characteristics:**

* **File Size:** These `.vp6` files constitute a significant portion of the game's total data size (~50%).
* **Video Stream:**
    * **Codec:** Uses the **On2 TrueMotion VP6** video codec, identified by the `vp60` marker within the `MVhd` chunk in the hex dumps.
    * **Typical Specs:** Often 1280x720 resolution at 29.97 frames per second (though this can vary).
    * **Header Chunk:** `MVhd`.
* **Audio Stream(s):**
    * **Container:** Uses the **EA SCHl** structure, indicated by the presence of `SCHl` or `SHxx` header chunks.
    * **Codec:** Typically **Electronic Arts EA-XA 4-bit ADPCM v2** (as commonly found within SCHl streams). Based on typical SCHl usage, expect sample rates like 48000 Hz, stereo channels, resulting in bitrates around 411 kb/s.
    * **Localization:** Files may contain a single `SCHl` chunk or multiple `SHxx` chunks for different languages (e.g., `SHEN`, `SHFR`, `SHDE`, etc.). The `vgmstream` code explicitly handles these multi-language variations.

### Related EA Formats & vgmstream Handling

The `vgmstream` source code reveals how it interprets these `.vp6` files and related EA audio formats:

* **`ea_schl_standard.c` Logic:**
    * `init_vgmstream_ea_schl`: Handles **standalone** audio files using the `SCHl` or `SHxx` structure. It associates many extensions with this format:
        * `.asf`, `.lasf`, `.str`, `.chk`, `.eam`, `.exa`, `.sng`, `.aud`, `.strm`, `.stm`, `.sx`, `.xa`, `.hab`, `.xsf`, `.gsf`, `.r`, and extensionless files.
    * `init_vgmstream_ea_bnk`: Handles EA sound banks (collections of sounds). Extensions:
        * `.bnk`, `.sdt`, `.hdt`, `.ldt`, `.abk`, `.ast`, `.cat`, and extensionless files.
    * `init_vgmstream_ea_schl_video`: Specifically designed to find and parse `SCHl`/`SHxx` audio streams **within video container files**.
        * It checks for `.vp6` extensions if the file *starts* with header IDs like `SCHl`, `MADk`, `MVhd`, or `MPCh`.
        * Crucially, even if the file doesn't start with an audio header (e.g., starts with `MVhd`), this function *searches within the file* to locate the first `SCHl` or `SHxx` block to treat as the start of the audio stream(s).
        * It correctly identifies and handles multiple language streams (`SHxx` blocks appearing sequentially) allowing selection of a specific stream (subsong).

**Tools:**

* **FFmpeg:**
    ```bash
    # Analyze the file structure (should show VP6 video and one or more EA-XA audio streams)
    ffmpeg -i input.vp6

    # Convert to MP4 (includes video and usually the *first* detected audio stream)
    # Note: If multiple SHxx language streams exist, FFmpeg might only extract the first one by default.
    ffmpeg -i input.vp6 output.mp4
    ```
* **vgmstream-cli:** Highly recommended for accurately handling the EA SCHl audio structure, especially with multiple languages.
    ```bash
    # Analyze and play the audio stream(s)
    vgmstream-cli input.vp6

    # Play a specific language stream if multiple SHxx blocks exist (e.g., stream 2)
    vgmstream-cli -s 2 input.vp6

    # Convert the audio (e.g., the first stream) to WAV
    vgmstream-cli -o output.wav input.vp6
    ```