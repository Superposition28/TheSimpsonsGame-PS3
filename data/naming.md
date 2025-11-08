
2 Levels
    1.1 Springfield Hub
    1.2 Game Engine hub

    2.1 The Land of Chocolate
    2.2 Bartman Begins
    2.3 Around the World in 80 Bites
    2.4 Lisa the Tree Hugger
    2.5 Mob Rules
    2.6 Enter the Cheatrix
    2.7 The Day of the Dolphin
    2.8 Shadow of the Colossal Donut
    2.9 Invasion of the Yokel-Snatchers
    2.10 Bargain Bin
    2.11 NeverQuest
    2.12 Grand Theft Scratchy
    2.13 Medal of Homer
    2.14 Big Super Happy Fun Fun Game
    2.15 Five Characters in Search of an Author
    2.16 Game Over

# Level folder → code → Level title

* `spr_hub` → ` ` → Springfield Hub (home/backyard/free-roam start points)
* `gamehub` → ` ` → Game Engine hub (Bargain Bin (neverquest, grand_theft_scratchy, medal_of_homer, bigsuperhappy) entry space)

* `loc` → `loc` → **The Land of Chocolate**
* `brt` → `brt` → **Bartman Begins**
* `eighty_bites` → `80b` → **Around the World in 80 Bites**
* `tree_hugger` → `hug` → **Lisa the Tree Hugger**
* `mob_rules` → `mob` → **Mob Rules**
* `cheater` → `che` → **Enter the Cheatrix**
* `dayofthedolphins` → `dod` → **The Day of the Dolphin**
* `colossaldonut` → `scd` → **Shadow of the Colossal Donut**
* `dayspringfieldstoodstill` → `sss` → **Invasion of the Yokel-Snatchers**
* `bargainbin` → `gamehub` → **Bargain Bin**
* `neverquest` → `nvq` → **NeverQuest**
    - `dungeon` - `dung`
    - `shire` - `shir`



* `grand_theft_scratchy` → `gts` → **Grand Theft Scratchy**
* `medal_of_homer` → `moh` → **Medal of Homer**
* `bigsuperhappy` → `bsh` → **Big Super Happy Fun Fun Game**
* `rhymes` → `rwc` → **Five Characters in Search of an Author**
* `meetthyplayer` → `mtp` → **Game Over**

# Audio/file prefix codes → Level/area

(From `file_patterns.file_pattern` prefixes)

* `80b_` → **Around the World in 80 Bites**
  e.g., `amb_80b_crowd_qd_01.exa.snu`
* `brt_` → **Bartman Begins**
  e.g., `amb_brt_diorama_4ch_lp.exa.snu`
* `hug_` → **Lisa the Tree Hugger**
  e.g., `hug_amb_forest_qd_01.exa.snu`
* `mob_` → **Mob Rules**
  e.g., `mob_amb_garage_qd_01.exa.snu`, `mob_amb_vent_qd_01.exa.snu`
* `che_` → **Enter the Cheatrix**
  e.g., `amb_che_market_qd.exa.snu`
* `dod_` → **The Day of the Dolphin**
  e.g., `amb_dod_docks_qd.exa.snu`
* `moh_` → **Medal of Homer**
  e.g., `moh_amb_aircraft_carrier_qd.exa.snu`, `moh_amb_french_village_night_qd.exa.snu`
* `bsh_` → **Big Super Happy Fun Fun Game**
  e.g., `amb_bsh_fire_qd.exa.snu`, `amb_bsh_air_qd.exa.snu`
* `gts_` → **Grand Theft Scratchy**
  e.g., `amb_gts_fullcity_qd.exa.snu`, `amb_gts_vents_qd.exa.snu`
* `rwc_` → **Five Characters in Search of an Author**
  e.g., `rwc_amb_mansion_qd_02.exa.snu`, `rwc_mus_simpsons_theme_song.exa.snu`
* `sss_` → **Invasion of the Yokel-Snatchers** (a.k.a. “The Day Springfield Stood Still”)
  e.g., `amb_sss_control_room_qd.exa.snu`, `amb_sss_mall_lot_qd.exa.snu`
* `spr_` → **Springfield hub/house/interiors**
  e.g., `spr_amb_int_house_qd_01.exa.snu`, `spr_amb_ext_garage_qd_01.exa.snu`
* `gamehub_` → **Bargain Bin / Game Engine hub**
  e.g., `amb_gamehub_amb_qd.exa.snu`, `amb_gamehub_siegehouse_rev1_qd.exa.snu`
* `nvq_` → **NeverQuest**
  e.g., `nvq_amb_dungeon_qd_02.exa.snu`, `nvq_amb_shire_qd_01.exa.snu`
* `mtp_` → **Meet Thy Player / Game Over (Heaven)**
  e.g., `amb_mtp_heaven_full_qd.exa.snu`

# OLD_DIR_NAME → meaning (+ where it points)

* `80b_crow` → crowd ambience for **Around the World in 80 Bites** (✔ you already mapped)
* `amb_airc` → ambience: **aircraft carrier** (→ **Medal of Homer**)
* `amb_chao` → ambience: **chaos harbor/area** (used near alien siege sequences; ties into **Bargain Bin/Gamehub** intro or invasion-adjacent scenes)
* `amb_cour` → ambience: **courtyard** (used with `rwc_` → **Five Characters…**)
* `amb_dung` → ambience: **dungeon** (→ `nvq_` **NeverQuest**)
* `amb_ext_` → ambience: **exterior** (Springfield hub outdoor beds → `spr_`)
* `amb_fore` → ambience: **forest** (→ `hug_` **Lisa the Tree Hugger**)
* `amb_fren` → ambience: **French** (castle/village night → `moh_` **Medal of Homer**)
* `amb_gara` → ambience: **garage** (`mob_` **Mob Rules** setups)
* `amb_int_` → ambience: **interior** (generic/house/vents → `spr_`)
* `amb_mans` → ambience: **mansion** (`rwc_` **Five Characters…**)
* `amb_nort` → ambience: **North Africa** (`moh_` **Medal of Homer**)
* `amb_riot` → ambience: **riot** (`mob_` **Mob Rules** crowd/protest beds)
* `amb_shir` → ambience: **shire** (`nvq_` **NeverQuest**)
* `amb_vent` → ambience: **vents** (`mob_` **Mob Rules** with Maggie vents)
* `bin_rev0` → **Bargain Bin** ambience rev 01
* `brt_dino` / `brt_dior` / `brt_myst` / `brt_plan` / `brt_temp` → **Bartman Begins** sub-areas (dino room, diorama, mystical, planet, temple)
* `bsh_air_` → **Big Super Happy** airship
* `bsh_beac` / `bsh_figh` / `bsh_fire` / `bsh_ice_` / `bsh_vill` / `bsh__air` → **Big Super Happy** beach/fight/fire/ice/village/airship
* `che_cart` / `che_cent` / `che_mark` / `che_mo_b` / `che_q_an` → **Enter the Cheatrix** (cart, central, market, “bloody” area, Q&A hall)
* `dod_aqua` / `dod_dock` → **Day of the Dolphin** aquarium/docks
* `gamehub_` → **Game Engine/Bargain Bin hub** ambience (incl. siege-house)
* `gts_full` / `gts_seas` / `gts_stat` / `gts_subu` / `gts_vent` / `gts_viol` → **Grand Theft Scratchy** city/seaside/station/suburbs/vents/violent sea
* `mtp_heav` → **Meet Thy Player/Game Over** heaven (full/lite mixes)
* `mus_simp` → **Simpsons Theme Song** cue (`rwc_` level’s music)
* `sss_cont` / `sss_lab_` / `sss_mall` → **Invasion of the Yokel-Snatchers** control room/lab/mall lot
