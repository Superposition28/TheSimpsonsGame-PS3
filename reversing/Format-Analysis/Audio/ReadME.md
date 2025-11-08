# Documentation: Game Audio File Formats (ALB/CTB/SNU System)

## Introduction

This document provides an overview of the audio file system used in The Simpsons Game, focusing on the relationship between the .alb, .ctb, and .snu file types often found within the extracted audio asset directories.

These three formats work together: .alb and .ctb files form a directly related pair managing the metadata and control logic for audio events, while .snu files primarily serve to store the actual compressed audio stream data. Understanding their distinct roles and how they connect is crucial for analysing or modifying game audio.

Detailed byte-level specifications for each format can be found in the README.md files located within their respective subdirectories (alb/README.md, ctb/README.md, and snu/README.md). This document focuses on their high-level purpose and interaction.

## Directory Structure

You will typically find these files organized in parallel or related structures, often based on game map/level, character/category, or audio type:

.../assets/shared/audio/streams++dialog/
├── alb/
│   └── [map_or_category]/
│       └── [character_or_group].alb
│       └── README.md  <-- Detailed ALB format specs
├── ctb/  (or sometimes cht/)
│   └── [map_or_category]/
│       └── [character_or_group].ctb
│       └── README.md  <-- Detailed CTB format specs
...

.../assets/[audio_streams_location]/
├── snu/  (or directly in streams folder)
│   └── [stream_name].snu (or .exa.snu, etc.)
│   └── README.md  <-- Detailed SNU format specs
...

Notice that corresponding .alb and .ctb files often share the same base filename (e.g., global_marg.alb and global_marg.ctb), indicating they manage the same set of audio events. .snu files often represent the actual audio streams referenced indirectly by the ALB/CTB system or used for background music/ambience, and might be located in different asset directories.

## Role of .alb Files (Alias/Library Banks)

*   **Purpose:** Defines the "What". These files act as libraries or banks that define individual sound events or aliases.
*   **Content:**
    *   Typically contain a list of entries, each representing a specific sound cue (e.g., a line of dialogue).
    *   Each entry usually includes one or more internal Identifiers (IDs) or Hashes. These unique values are used by the game engine to reference the sound. You might see the same hash repeated within an entry.
    *   May contain basic Metadata per entry, such as flags, type identifiers, or constants related to the sound group.
    *   **Crucially, .alb files generally do not contain the raw audio waveform data itself.** They are metadata files pointing *towards* the audio.
*   **Format Details:** See `alb/README.md`.

## Role of .ctb Files (Chart/Cue/Control Tables)

*   **Purpose:** Defines the "When" and "How". These files act as control tables that link game logic to the sound definitions in the .alb files.
*   **Content:**
    *   Often contain a list of the same Identifiers (IDs) or Hashes found in the corresponding .alb file, acting as a manifest or index.
    *   Link these low-level sound IDs to higher-level Game Event Triggers or script names (often found as readable ASCII strings within the file, e.g., `player_jump`, `maggie_activated`).
    *   May include Rules, Conditions, Priorities, or Sequences governing when and how a sound is played (e.g., defining conversational flow, prerequisites, randomization).
    *   Can contain pointers, offsets, and structured data defining this control logic.
*   **Format Details:** See `ctb/README.md`.

## Role of .snu Files (SNU Audio Stream Container)

*   **Purpose:** Provides the "Where" (the actual audio data storage). These files act as containers specifically designed to store compressed audio streams.
*   **Content:**
    *   Typically contain a small Header with basic information like channel count, offsets, and potentially other metadata (like embedded filenames or loop points in some variants).
    *   The bulk of the file consists of the Compressed Audio Data itself, usually encoded with an Electronic Arts codec (like EA-XAS ADPCM).
    *   The internal structure of the audio data often follows older EA formats like SNR/SNS or the newer SPS format. The SNU header helps identify which internal structure is used and where it starts.
*   **Key Point:** Unlike .alb and .ctb, the .snu file **contains the actual sound waveform data**, albeit in a compressed format.
*   **Format Details:** See `snu/README.md`.

## The Relationship: How They Work Together

The .alb, .ctb, and .snu files form a key part of the game's audio system:

1.  **Metadata/Control Pair:** The `.alb` file defines sound cues with unique IDs/hashes (What), and the corresponding `.ctb` file provides the control logic, linking those IDs to game events (When/How). These two formats are directly related and manage the information about and logic for triggering the sound events.
2.  **Audio Data Storage:** The `.snu` files (or potentially larger archives) serve as the storage containers for the actual compressed audio waveform data (Where).
3.  **Execution Flow (Simplified):**
    *   A game event occurs (e.g., Marge interacts with Maggie's puzzle).
    *   The engine checks the relevant `.ctb` file for a matching event trigger (e.g., `maggie_puzzle_complete`).
    *   The `.ctb` file provides the rules and points to the appropriate sound ID/hash.
    *   The engine uses this ID/hash to look up the specific sound entry in the corresponding `.alb` file.
    *   The `.alb` file provides necessary metadata.
    *   The engine uses this information (potentially combined with data from the `.ctb`) to locate and load the actual audio data (e.g., from an `.snu` file or archive).
    *   The engine plays the loaded audio stream.
4.  **Direct Playback:** Note that `.snu` files can also be used directly for audio like background music or ambient loops, independent of the specific ALB/CTB event triggering system.

## Conclusion

In essence, the .alb and .ctb files form a tightly coupled metadata and control system for audio events, defining what sounds exist and when/how they play based on game logic. The .snu files are primarily storage containers for the actual compressed audio waveforms themselves. Understanding all components is essential for a complete picture of the game's audio implementation. For detailed structure analysis, refer to the specific README files within the `alb`, `ctb`, and `snu` folders.

