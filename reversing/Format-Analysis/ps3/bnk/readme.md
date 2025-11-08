
`.bnk.PS3` is a **character animation bank** (“BNK” = bank) compiled for PS3. It’s part of EA’s RenderWare/EA-Character pipeline (CCT export path is in the filename) and contains **charactor specific motion data + tables** that the runtime uses to drive his state machine.

* Clear **animation/state names** in the string table:

  * `idle_frink`, `walk_frink`, `jump_frink`, `airstate_fall_frink`, `taunt_frink`, plus generic `idle`, etc.
* Repeated **record blocks** pairing a name with ranges/offsets and parameters, with floats like `3F 80 00 00` (= 1.0) typical for **blend weights/speeds**.
* Lots of **offset tables** near the top, then per-clip chunks (start/end pointers like `00 00 01 90 … 00 00 01 A0`, etc.)—classic bank layout: header → indices → clip payloads.
* Small tags like `C3`, `Co`, and numeric tuples following entries—these show up in banks as **channels/curves** (e.g., 3-component transforms, coefficients) and **per-clip metadata** (rates, durations).
* Big mid/end blobs of compact numbers/patterns (e.g., long runs of `0x078C`, `AA/55` bitmasks) typical of **compressed keyframes/bit-packed event tracks** tuned for SPU/PPU playback on PS3.

### What the game uses it for

* Provides the **runtime animations and blend data** for Dr. Frink:

  * Base loops (`idle_*`, `walk_*`), locomotion variants, air/fall, jump, taunt.
* Contains **transition definitions** and **blend params** the character controller reads to switch states smoothly.
* Packs **curves/events** (timings, notifies, maybe footstep markers) in a CPU/SPU-friendly format.
* Loaded alongside the character’s CCT asset so gameplay code can request “play `jump_frink`”, “blend to `idle_frink`”, etc., without touching source `.anm/.skel` files.
