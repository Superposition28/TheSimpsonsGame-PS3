A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\STROUT\Map_3-00_SprHub\spr_hub\zone06_str\build\PS3\pal_en\assets\props\eps_mob_rules\mob_scaffolding\geo\export\mob_scaffolding_mr_unbuilt\collisionmodel.hkt.PS3


`collisionmodel1.hkt.PS3` likly a **Havok HKX packfile** (big-endian PS3 build) that contains the **physics/collision data** for the prop *spr_margesalonchair*. The game's Havok runtime loads this alongside the RenderWare-rendered mesh to provide **static collision**, **raycasts**, and **physics queries** in the Game Hub interior.

---

* **Magic & header:** starts with `48 6B 78` → **"Hkx"**, followed by `Havok-4.1.0-r1`. That's Havok Content Tools 4.1 packfile metadata.
* **Packfile sections:** literal section labels:

  * `__classnames__`, `__data__`, `__types__` -- classic Havok **tagfile/packfile** layout.
* **Havok class table:** many baked type names:

  * `hkClass`, `hkClassMember`, `hkClassEnum`, ...
  * Physics/shape types: `hkRigidBody`, `hkBvTreeShape`, `hkMoppBvTreeShape`, `hkSimpleMeshShape`, `hkStorageMeshShape`, `hkShapeContainer`, `hkMotion`, etc.
* **Asset name string:**
  `spr_margesalonchair|MetaModel|Asset|CollisionModel1|...|v3` -- clearly labels this file as the **collision model** for that prop.
* **Geometry + tree:** you can see BE floats and index lists (vertex data / triangle indices) and a **MOPP BVTree** block -- Havok's static-mesh acceleration structure for collisions.

---

## What it's for

* Acts as the **physics representation** of the chair prop:

  * A **static rigid body** (fixed motion) built from a **mesh shape** wrapped in a **BVTree/MOPP** for fast queries.
  * Used for **character/controller collision**, **line-of-sight/raycasts**, **projectile hits**, and **placement/blocking**.
* Loaded by the game's Havok integration while the **RenderWare** side draws the visual mesh. The two are associated via the shared asset naming/path.


---
related extensions:
* `.hkt.PS3` all regular collision files have this extension
* `.hko.PS3` all animated collision files have this extension, and all character collision spheres use this extension
* `.acs.PS3` always contained within collision folders (or subfolders of it) often alongside `.hko.PS3` files
