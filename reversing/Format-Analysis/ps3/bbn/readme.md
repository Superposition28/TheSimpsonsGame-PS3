

### Format: **BBN** — Bone Bindings (PS3 build)

Your `player_default.bbn.PS3` is a **bone-binding table** compiled for PS3. It defines the canonical skeleton joints, their IDs, names, and lookup tables used by animation, IK, and gameplay systems.

### Why this fits

* The filename path: `.../assets/shared/bonebindings/player_default.bbn.PS3` → shared skeleton bindings.
* Clear joint names & aliases in the string block:

  * Short rig names: `m_pelvis`, `m_lumbar`, `m_thoracic`, `l_hip`, `r_knee`, `l_wrist`, `r_clav`, `m_neck2`, `m_jaw`, `r_weapon`, etc.
  * Friendly labels: `right elbow`, `pelvis`, `left clavicle`, `right eyelid top/bottom`, etc.
* Small header with counts/offsets, then a sequence of **offset tables** followed by the **name table**.
* Presence of special tags like `AITrajectory` and `r_eye/l_eye` shows extra bindings for look/aim vectors and AI helpers.

### What the game uses it for

* **Consistent bone ID ↔ name mapping** across characters and tools.
* **Attachment points** for props/weapons (`r_weapon`, hands, head).
* **Animation retarget/IK** constraints (knees, hips, wrists, spine chain).
* **Facial/eye controls** (`r_eye`, eyelids, `m_jaw`) for look-at and lip/eye cues.
* **AI & camera helpers** (`AITrajectory`).
* Acts as the **shared “player” skeleton contract** that animation banks (e.g., your `.bnk`) and controllers (`.cec`) reference at runtime.

