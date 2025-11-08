

### TL;DR

`*.sbk` is the **compiled sound bank** for the Game Hub.
Magic `6B 6E 62 73` = `"knbs"` → **“sbnk” (sound bank) on a big-endian platform (PS3)**.
It stores the **playback graph** (events/containers), **mix/bus routing**, **distance/volume/pitch curves**, flags, and IDs that the audio runtime uses to play the actual audio streams referenced by the companion **`.smb`/`.exa`** files.


* **Header magic:** `6B 6E 62 73` = `k n b s` → “**sbnk**” reversed by endianness (PS3 is big-endian). It’s a very common naming for “sound bank”.
* **Global tables → nodes:** After the header you get a **dense offset table** (monotonically increasing pointers), then a series of **variable-length node chunks** starting ~`0x01F0`.
* **Audio-ish floats & defaults:** Tons of BE floats: `41A00000` (**20.0**), `42C80000` (**100.0**), `3F800000` (**1.0**), `3E4CCCCD` (~0.2), `3F333333` (~0.7)… exactly the kind of values you see in **attenuation, pitch/volume, send levels, crossfades**.
* **Per-node control fields:** Repeating small enums/flags (`… 03 00 04 01 … FF 00 …`), plus IDs/hashes near each node. These align with **event types/containers** (one-shot, loop, random, sequence, switch), **bus/category** assignments, and **ducking** rules.

---

## What it’s probably used for

* The **SBK** defines the **logic/mix**:

  * Which **event IDs** exist for the hub (VO lines, UI beeps, ambience beds, props).
  * For each event/container: **routing to mix buses**, **priority/virtualization**, **voice limits**, **randomization**, **looping**, **ducking**, **reverb sends**, **occlusion/obstruction response**.
  * **Curves** for 3D rolloff, pitch/volume modulation, LFO/envelopes, crossfade/transition timings.
* At runtime, when the game triggers an event:

  1. The engine looks it up in **`*.sbk`** to get **how** to play it (graph, curves, routing).
  2. It then resolves the **actual audio data** via **`*.smb`** entries that point to **`*.exa`** streams (voice, SFX, ambience).

---

## How this relates to other formats

* **`.sbk` (this file):** **What** and **how** to play (events, graphs, mix, curves, rules).
* **`.smb`:** **Where** the data lives (a TOC that points to the **`.exa`** sound files and basic per-clip metadata).
* **`.exa`:** The **actual audio streams** (voice/SFX/ambience).


