
### Format: **ACS** — per-character **A**rticulated **C**ollision **S**hapes (PS3)

`marge.acs.PS3` is a small, binary list of simple hit-shape primitives (mostly spheres/capsules) attached to a character’s bones. The game uses this to do lightweight gameplay collision (melee hits, pickups, proximity checks, cursor targeting, etc.) without touching the full Havok meshes.

#### Why this is ACS / hit-spheres

* The path: `assets\shared\collision\marge.acs.PS3` → per-character collision set.
* You see lots of IEEE-754 floats like:

  * `3F 80 00 00` = **1.0** (identity scale/weights),
  * `3E 99 99 9A` ≈ **0.30**, `3E 80 00 00` = **0.25**, `3F C0 00 00` = **1.5**, `3D CC CC CD` = **0.1** — typical **radii** for gameplay spheres.
* Repeating fixed-size records with very similar layouts (centers/flags/identity), suggesting “one primitive per bone”.

#### What the game uses it for

* **Hit detection / hurtboxes** for punches, kicks, and small overlaps.
* **Targeting helpers** for abilities and cursor hover.
* **Cheap per-bone checks** while Havok handles full body collision separately (your `.hkt` file).

#### Rough layout you’re seeing (per entry)

Not exact names, but the pattern maps like this for each shape:

* A small header/IDs (includes a bone or binding hash; EA often stores CRCs of bone names).
* A primitive **type** code (you’ll spot `0x73 00 00` → `'s'` = **sphere**; some titles also use `'c'` for capsule).
* Center/orientation-ish block (many `1.0` values → identity) and/or flags.
* A **radius** (those 0.25 / 0.30 / 0.10 / 1.50 values).
* Repeats for each bone hotspot (head, hands, forearms, torso, legs, etc.).

In short: **`.acs.PS3` = fast hit-shape set**—a handful of bone-attached spheres (and possibly capsules) used by the EA/RenderWare runtime for quick overlap tests and gameplay interactions on PS3.


