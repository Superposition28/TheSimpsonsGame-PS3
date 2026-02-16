
# 8. RenderWare Resources

**Handled by:** `Scripts/RWReader/*` and `Scripts/Resources/EARS_MESH_Handler.cs`

**Endianness:** Little-Endian (Standard RW) or Big-Endian (Console specific)

The code contains a full RenderWare binary stream reader (`RWReader`). It supports standard RW sections (Clump, Geometry, Atomic, Texture, etc.) and custom EARS plugins.

**Custom EARS Sections:**

* **EARS Mesh (`0x0000EA33`)**: Contains submesh info, shader hashes, and vertex data (positions, normals, tangents, UVs, colors).
* **EARS Texture Plugin (`0x0000EA2F`)**: Associates hashes/paths with textures.

**Texture Dictionary (`rwID_TEXDICTIONARY`):**
A standard RenderWare container for textures. `TextureNative` sections inside handle specific texture formats (BC1, BC2, BC3, BGRA32, A8), often "swizzled" using Morton encoding (common on consoles like PS3).

