
`basic_player.cec.PS3` is a **compiled controller-mapping/config file** (“CEC” = *Controller Event/Configuration*) for the PS3 build. Designers authored a text `.cec` (you can see its original path embedded), and the build pipeline compiled it into this binary. At runtime the game’s input layer loads it to map **gamepad inputs → named gameplay actions** (with categories, contexts, and masks), e.g. `JumpKick`, `Activate`, `walk_run`, debug “HandOfGod” cursor tweaks, etc.



* The file starts with the asset name **`basicplayer`** and an embedded authoring path:

  ```
  x:\assets\shared\controller\configurations\basic_player.cec
  ```
* Then a long list of **action names** grouped by **categories** you’d expect from an input map:

  * ACTION: `Activate`, `PushPhysicsObject`, `HomerEat`, `DeployMaggie`, `Mob_MobUseSingle`, …
  * ATTACK: `PowerChargeUp`, `JumpKick`, …
  * MOVEMENT: `walk_run`, `idle`, `HomerballDashAttack`, …
  * SWITCH / CSA / debug tools: `SwitchToLisa`, `DoorCSAActivate`, `HOG_CursorMoveSpeedUp/Down`, `HOG_RotateObjectUp/Down`, `HOG_Ice`, menu inputs like `TextMenuScrollUp`.
* Each entry is immediately followed by compact numeric fields that behave like **device/button masks, modifiers, and flags** (e.g., `00 05 FF FF 04 00 FB FF`, `00 01 FF FF 02 00 CD FF`, `00 05 27 10 00 40 CF BF`, etc.), which is typical of an input binding table.

---

## What the game uses it for

* **Bind DS3/PS3 controller inputs** to high-level verbs used by the animation/ability/state machines.
* **Context gating:** many rows include a short context tag then `!!!!` (or other short tokens). The binary that follows contains **bitfields** to enable/disable a binding depending on state (e.g., in-air vs on-ground, in menu vs in game, in a “CSA” context).
* **Multiple mappings per action:** same verb can have alternate bindings (e.g., left/right variants, debug vs retail) with different masks/priorities.
* **Debug/cheat/dev tools**: the “HOG_*” (Hand-of-God) entries adjust a dev cursor/camera/object manipulator, typical for internal builds.

---

## Rough binary layout (what you’re seeing)

Not exact field names, but this will get you parsing quickly:

1. **Header**

   * A small version/magic + a 64-bit-ish cookie.
   * Asset name (`basicplayer\0`).
   * Zero padding.
   * **Source path** to the authoring text `.cec` (null-terminated).
   * More padding/alignment.

2. **Entry table (repeats)**
   For each mapped action you’ll see a block like:

   ```
   [nameHash-ish (4B)] [some ID/flags (1B)] [ActionName (ASCII, NUL)]
   [Category (e.g., "ACTION","ATTACK","MOVEMENT","SWITCH","CSA"), NUL]
   [Context tag (short), often "!!!!"]  // sometimes a mode tag instead
   [Device/Button/Modifier/State masks (several 16-bit/32-bit little-endian ints)]
   [padding]
   ```

   Examples from your dump:

   * `SpecialModelSwap` → `ACTION` → masks `00 05 FF FF 04 00 FB FF …`
   * `walk_run` → `MOVEMENT` → masks `00 05 FF FF 00 00 00 00 …`
   * `DoorCSAActivate` → `CSA` → masks `00 05 00 C8 00 10 FF EF …`
   * `HOG_CursorMoveSpeedUp` → `HandOfGod` → masks `00 01 FF FF 08 00 C7 FF …`
   * `SwitchToLisa` → `SWITCH` (note the repeated pair immediately after; looks like pressed/released variants)

3. **Alignment & tables**

   * You’ll see runs of zeros between groups (alignment).
   * Some 32-bit values near the top look like **offsets to string blocks** or **hashes** of names/categories.

> Endianness: strings are ASCII; the small integers (masks/flags) read **little-endian** as they sit (the patterns line up as typical bitmasks).

---

## How to reverse it quickly

* **String scan**: pull all NUL-terminated strings to get the action list and categories.
* **Block detection**: actions appear in fixed-pattern blocks: *[hash?]* → *ActionName* → *Category* → *Context/Tag* → *mask fields*. Use the category NUL terminator as an anchor.
* **Mask meaning**: map the 16-bit pairs by trial:

  * Build a small dumper that prints the hex quads following each category and log which change when you rebind buttons (if you can produce another dump from a different controller layout) — you’ll recover the **button bit positions** quickly.
  * Values like `FF F7`, `CF EF`, `FF 7F`, `C7 FF`, `27 10`, etc., are very *bitfield-ish* and consistent with DS3 button/axis masks (one or two 16-bit words for “buttons down”, “modifiers held”, “forbidden/required states”, etc.).
* **Context filtering**: the short token before the masks (often `!!!!`) appears to be a **mode/scope string**. Treat it as a tag you can match against the player’s state machine to gate a binding.

---

## Where it fits in the EA RenderWare + Havok PS3 game

* RenderWare handles **rendering/scene**, Havok handles **physics**, and this `.cec.PS3` feeds the **input system** that drives the player controller and ability logic. Other systems (animation state machines, scripted “Mob_” interactions, CSA set-pieces) hook onto these named actions rather than polling raw buttons.

