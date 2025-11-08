

analysis based on a single file


EA UIX file—EA’s compiled APT/“UIX” user-interface layout format. In The Simpsons Game (PS3, RenderWare-based), these files define and wire up menu/screens, widgets, animations, and references to shared UI assets.

Why we know:

Magic/signature: first 4 bytes are 75 69 78 66 → "uixf".

APT hints: you can see Apti and "Apt Data:74" in the text; “APT” is EA’s in-house UI system used across many EA titles of that era (360/PS3/Wii).

Screen name & properties: immediately after header you get chunk tags like titl (“bus_stop”), alig (“align”), and then a block of structured offsets—typical of compiled UI layout tables.

Symbol/library references: lots of strings like SharedLibrary, SelectButton, BackButton, TV_scanline_group, Arrow, Locked, pulsingButton—these are exported symbols the layout instantiates from a shared UI asset pack.

Game-specific wires: ui_thumbnail_swap, ui_char_select_tone, ui_char_select_move, ui_bus_stop_go, Bus_Stop_Marker, and character names (Homer, Bart, Marge, Lisa). That’s exactly the Bus Stop (character swap) hub UI.

Pointer tables & data blocks: repeated patterns of 00 00 00 XX followed by big-endian offsets (e.g., 00 00 00 70, 00 00 00 80, …) point to subchunks (widgets, timelines, styles). The tail region has float-y looking values (e.g., 3F 8A 3D 80) used for transforms/timings/colors, separated by FF FF FF FF sentinels.

What it’s for (in this game):

It’s the compiled layout/logic for the Game Hub “Bus Stop” menu: lays out the background (“Bgnd”), scanline overlay, lock/arrow icons, the Select/Back buttons mapping to platform actions, and hooks named ui_* that the engine calls to animate thumbnails, move selection, start travel (“bus_stop_go”), or show popups (popup_style3).

At runtime, the RenderWare game code loads the UIX chunk, resolves its symbol references from the SharedLibrary, and drives the screen via the exported ui_* handlers and data tables.



