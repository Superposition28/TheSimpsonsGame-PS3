A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\STROUT\Assets_2_Characters_Simpsons\GlobalFolder\chars\marge_mm2_h2_mtp_str\build\PS3\pal_en\assets\shared\collision\marge.acs.PS3
A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\STROUT\Assets_2_Characters_Simpsons\GlobalFolder\chars\marge_mm2_h2_mtp_str\build\PS3\pal_en\assets\shared\collision\char_collision_spheres.hko.PS3

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


only 267 .acs.PS3 files found in the game data, here is
every possible file name found with this extension at some paths:
GameFiles/STROUT/Assets_2_Characters_Simpsons/GlobalFolder/chars/bart_bc0_grp0_ss1_h0_str/build/PS3/pal_en/assets/shared/collision/bart.acs.PS3
GameFiles/STROUT/Assets_2_Characters_Simpsons/GlobalFolder/chars/homer_fh0_gh0_hh0_h0_str/build/PS3/pal_en/assets/shared/collision/homer.acs.PS3
GameFiles/STROUT/Assets_2_Characters_Simpsons/GlobalFolder/chars/lisa_str/build/PS3/pal_en/assets/shared/collision/lisa.acs.PS3
GameFiles/STROUT/Assets_2_Characters_Simpsons/GlobalFolder/chars/marge_mm0_h0_str/build/PS3/pal_en/assets/shared/collision/marge.acs.PS3
GameFiles/STROUT/Map_3-00_SprHub/spr_hub/design/Act_2_folderstream_str/build/PS3/pal_en/assets/shared/collision/npc_alien.acs.PS3
GameFiles/STROUT/Map_3-01_LandOfChocolate/loc/Challenge_Mode/Challenge_Mode_Design_str/build/PS3/pal_en/assets/shared/collision/npc_bunny.acs.PS3
GameFiles/STROUT/Map_3-00_GameHub/gamehub_str/build/PS3/pal_en/assets/shared/collision/npc_dash.acs.PS3
GameFiles/STROUT/Map_3-00_GameHub/gamehub_str/build/PS3/pal_en/assets/shared/collision/npc_default.acs.PS3
GameFiles/STROUT/Map_3-07_DayOfTheDolphin/dayofthedolphins/challenge_mode/challenge_mode_design_str/build/PS3/pal_en/assets/shared/collision/npc_dolphin.acs.PS3
GameFiles/STROUT/Map_3-08_TheColossalDonut/colossaldonut/story_mode/Story_mode_design_str/build/PS3/pal_en/assets/shared/collision/npc_lardlad.acs.PS3
GameFiles/STROUT/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets/shared/collision/npc_selmatty.acs.PS3
GameFiles/STROUT/Map_3-16_MeetThyPlayer/meetthyplayer/story_mode/story_mode_design_str/build/PS3/pal_en/assets/shared/collision/npc_shakespeare.acs.PS3
GameFiles/STROUT/Map_3-14_BigSuperHappy/bigsuperhappy_str/build/PS3/pal_en/assets/shared/collision/npc_sumo_dash.acs.PS3
GameFiles/STROUT/Map_3-02_BartmanBegins/brt/story_mode/story_mode_design_str/build/PS3/pal_en/assets/shared/collision/weapons/weapon_baton.acs.PS3
GameFiles/STROUT/Map_3-12_GrandTheftScratchy/grand_theft_scratchy/story_mode/story_mode_design_str/build/PS3/pal_en/assets/shared/collision/weapons/weapon_brokenbottle.acs.PS3
GameFiles/STROUT/Map_3-00_SprHub/spr_hub/design/Act_1_folderstream/stream_c_str/build/PS3/pal_en/assets/shared/collision/weapons/weapon_cane.acs.PS3
GameFiles/STROUT/Map_3-05_MobRules/mob_rules/story_mode/story_mode_design_str/build/PS3/pal_en/assets/shared/collision/weapons/weapon_cattleprod.acs.PS3
GameFiles/STROUT/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets/shared/collision/weapons/weapon_club.acs.PS3
GameFiles/STROUT/Map_3-00_SprHub/spr_hub/zone16_str/build/PS3/pal_en/assets/shared/collision/weapons/weapon_hammer.acs.PS3
GameFiles/STROUT/Map_3-05_MobRules/mob_rules/story_mode/story_mode_design_str/build/PS3/pal_en/assets/shared/collision/weapons/weapon_kids_bat.acs.PS3
GameFiles/STROUT/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets/shared/collision/weapons/weapon_morc_club.acs.PS3
GameFiles/STROUT/Map_3-00_SprHub/spr_hub/design/Act_2_folderstream/stream_a_str/build/PS3/pal_en/assets/shared/collision/weapons/weapon_pipe.acs.PS3
GameFiles/STROUT/Map_3-00_SprHub/spr_hub/design/Act_2_folderstream/stream_b_str/build/PS3/pal_en/assets/shared/collision/weapons/weapon_pitchfork.acs.PS3
GameFiles/STROUT/Map_3-02_BartmanBegins/brt/story_mode/story_mode_design_str/build/PS3/pal_en/assets/shared/collision/weapons/weapon_purse.acs.PS3
GameFiles/STROUT/Map_3-00_SprHub/spr_hub/zone14_str/build/PS3/pal_en/assets/shared/collision/weapons/weapon_saw.acs.PS3
GameFiles/STROUT/Map_3-11_NeverQuest/neverquest/story_mode/story_mode_design_str/build/PS3/pal_en/assets/shared/collision/weapons/weapon_shovel.acs.PS3
GameFiles/STROUT/Map_3-00_SprHub/spr_hub/design/Act_2_folderstream/stream_b_str/build/PS3/pal_en/assets/shared/collision/weapons/weapon_torch.acs.PS3

---

clearly some relation to collision, characters and weapons



---
related extensions:
* `.hkt.PS3` all regular collision files have this extension
* `.hko.PS3` all animated collision files have this extension, and all character collision spheres use this extension
* `.acs.PS3` always contained within collision folders (or subfolders of it) often alongside `.hko.PS3` files
