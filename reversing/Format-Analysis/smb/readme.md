

`*.smb` is an **EA sound stream bank**—a compact **Table-of-Contents + per-entry metadata** file that tells the engine which **`.exa` audio streams** to load/play in the current level and with what parameters (IDs/hashes, 3D attenuation, routing/flags, etc.). Think **“Stream Meta Bank”**: one small index file that points to many external `.exa` assets (voice lines, SFX, ambience) and supplies playback settings for each.

---


* The records literally point to `.exa` assets (EA’s streamed audio format in this title):

  * e.g. `d_frin_xxx_0004f66.exa`, `d_lis8_xxx_0004fcd.exa`, `d_mar8_xxx_0004fc3.exa`, `d_homr_xxx_005be4.exa`, `d_gegf_xxx_003ab3.exa`, etc.
* The file structure is a typical **header → offset table → fixed-size records** layout used by EA for small TOC files that index content within a larger pack or external assets.
* Inside each record you can see **repeated IDs/hashes**, a few **float-looking values** (big-endian IEEE-754) that match common audio parameters (e.g., min/max distance like ~20.0, ~100.0), then an **8-byte hash** and the **null-terminated path** to the `.exa`.

