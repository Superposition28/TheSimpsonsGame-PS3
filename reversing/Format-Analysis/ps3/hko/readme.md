
#### `.hko.ps3` — Havok Physics Files (PS3 Version)

**Purpose:**

The `.hko.ps3` files define physics setups for characters, props, and other objects in the game using the Havok Physics Engine. They contain all necessary data for how an object interacts physically within the world — including collision detection, joint constraints, movement behaviors, and material properties.

These files are specifically formatted for the PlayStation 3 architecture to optimize performance (e.g., memory layout, endian formats).

**Context:**

This game uses RenderWare for graphics and world rendering.

It integrates Havok 4.1.0-r1 as its physics simulation middleware.

`.hko.ps3` files serve as the bridge between RenderWare-rendered objects and Havok-simulated physical behavior.

**Example path:**

...\chars++lisa_hog\bound++export\lisa_hog.hko.PS3

Here, `lisa_hog.hko.ps3` likely contains the complete physics setup for the character Lisa, defining how her body reacts to forces, impacts, and movement.

**Contents:**

Analysis of `.hko.ps3` file internals shows it contains:

*   **Physics Bodies**

    `hkRigidBody`, `hkCollidable`, `hkShape`, `hkSphereShape`, `hkConvexShape`

    Define the physical shapes and collision volumes for parts of the object (e.g., limbs, torso, props).
*   **Constraints & Joints**

    `hkConstraintData`, `hkConstraintAtom`, `hkModifierConstraintAtom`, `hkConstraintInstance`

    Define joints (shoulders, elbows, knees) and rules for how connected bodies can move relative to each other.
*   **Motion & Movement**

    `hkMotion`, `hkKeyframedRigidMotion`, `hkMaxSizeMotion`, `hkMotionState`

    Describe how each body part moves, including keyframed (animated) motion or fully simulated physics motion (e.g., ragdolls).
*   **Physics Systems**

    `hkPhysicsSystem`, `EAPhysicsSystem`

    Group multiple bodies and constraints into complete physical "systems" (e.g., a character's full body or a destructible object).

    `EAPhysicsSystem` suggests custom EA extensions to base Havok functionality.
*   **Materials**

    `hkMaterial`, `EAMaterial`

    Define physical properties like friction and bounciness (important for realism when surfaces interact).
*   **Properties & Metadata**

    `hkProperty`, `hkPropertyValue`

    Store additional settings for rigid bodies, shapes, and materials.
*   **Naming & Tagging**

    Found strings like `CHARACTER`, `MODEL`, `reference`, `AITrajectory`, `JO_shoulder`, `JO_elbow`, `JO_wrist`, and `ignore_DynamicObject`

    These link physics parts to animation bones or AI systems and control behaviors like collision ignoring.

**Key Takeaways:**

*   `.hko.ps3` files are essential for physics simulation in the game.
*   Without them, characters and objects would either not react physically or behave incorrectly (e.g., no ragdoll on death, no proper collision).
*   Files are tied closely to RenderWare models, character skeletons, and game-specific animations.
*   They ensure physical realism and gameplay interactions are accurate and efficient on PS3 hardware.

**Additional Notes:**

The `.ps3` suffix means the data is already optimized for PlayStation 3: possibly endian-corrected, tightly memory-aligned, and tailored for the console's SPUs (co-processors).

Full parsing of `.hko.ps3` files would require either:

*   Havok 4.1.0-r1 SDK tools (very rare now)
*   Custom reverse engineering based on public Havok 4.x documentation
