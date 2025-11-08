

The file appears to be a Big-Endian, customized BSP format, likely from RenderWare used in The Simpsons Game.
It starts with a small header (possibly giving version 11 and a count of 6 somethings).
There's an unknown section (0x10-0x6F) that might be a lump directory or other metadata.
A series of 6 identical-looking 16-byte metadata blocks (0x70-0xCF) follows, marked with PE0.
The main data starting at 0xD0 consists of 64-byte structures, highly likely representing BSP nodes, containing plane data (normal+distance), child node offsets/indices, and other unknown floats and integers.


Okay, based on the detailed analysis performed so far, here's a summary of what these .bsp files (specifically zone01.bsp and zone13.bsp) from The Simpsons Game appear to contain:

In essence, it's a custom 3D level file format that uses a Binary Space Partitioning (BSP) tree structure to organize the level's geometry and spatial information.

Here's a breakdown of the known contents:

    File Header (Offsets 0x00 - 0x0F):
        A magic number or version identifier (0x0000000B - maybe Version 11).
        A "Count" field (at offset 0x08) that varies between files (6 for zone01, 1 for zone13) and seems to control the structure of the subsequent metadata section.
        An offset (at 0x0C, value 0x70) pointing to the start of the next data section.

    Lump Directory (Offsets 0x10 - 0x6F):
        This section acts like a directory, containing entries that point to different data chunks ("lumps") within the file.
        While not fully decoded, the entry at index 3 (file offset 0x30) reliably points to the start (Offset) and size (Length) of the main BSP node data chunk (Lump 3). Other entries likely point to vertices, faces, textures, etc.

    Variable Metadata Section (Starts at 0x70):
        The structure and content of this section depend on the 'Count' field from the header.
        In zone01 (Count=6), this contained 6 blocks marked with PE0.
        In zone13 (Count=1), it contained different data (C8 FD CE AB...).
        The exact purpose of this metadata isn't fully clear yet, but it precedes the main node data.

    Main BSP Node Data (Lump 3 - Starts at 0xD0 in zone01, 0x80 in zone13):
        This is the core of the spatial partitioning information.
        It consists of a tightly packed array of 64-byte node structures.
        Each node follows an 8 float, 8 int format (Big Endian).
        Node Contents:
            Plane Data (Floats 1-4): Defines the splitting plane for that node (likely Nx, Ny, Nz, D, though normals are unnormalized and the exact D value needs final confirmation).
            BBox/Tex? Data (Floats 5-8): Additional geometric data, possibly bounding box coordinates or texture projection vectors.
            Flags? (Int 1): An integer flag field that varies between nodes.
            Child Pointers (Ints 2 & 3): Crucial for navigating the BSP tree.
                Positive values are very likely byte offsets relative to the start of this node lump, pointing to the front (ChildF) and back (ChildB) child nodes.
                Values <= 0 indicate leaf nodes. Negative values likely encode a leaf identifier, while (0, 0) indicates a different type of leaf.
            Other Integers (Ints 4-8 / Unk1-5): Often hold default values (0, 65535, -1, -2147483648, 0) in internal nodes, but store leaf-specific data in leaf nodes.

    Leaf Node Data (Implicit within Integers):
        When a node is identified as a leaf (via child pointers <= 0), the integer fields (Flags?, Unk1-5) store information about the contents of the 3D space represented by that leaf (e.g., solid, empty, water, trigger, references to visible geometry faces).

    Trailing Data (Sometimes):
        zone01.bsp has 16 extra bytes after the last node in Lump 3. Its purpose is unknown.

Overall Purpose:

The BSP tree structure defined in Lump 3 allows the game engine to efficiently:

    Determine Visibility: Quickly figure out which parts of the level are potentially visible from the player's viewpoint (by traversing the tree).
    Perform Collision Detection: Efficiently check if the player or objects collide with the level geometry.
    Organize Level Data: Associate specific regions of space (leaves) with properties, lighting, and renderable geometry (like faces/polygons).

Missing Pieces (Likely in Other Lumps):

While the BSP structure is becoming clear, the file must also contain the actual geometry data, likely in other lumps pointed to by the directory section (0x10-0x6F):

    Vertex List (X, Y, Z coordinates)
    Face/Polygon List (which vertices make up each surface, texture assignments, lighting info)
    Texture Information
    Collision Data
    Entity Information (spawn points, items, etc.)
    Visibility Data (Precomputed Visibility Set - PVS)

In summary, the .bsp file is a structured container holding the spatial layout (BSP tree) and associated data needed to represent and interact with a 3D game level zone in The Simpsons Game. Your analysis has successfully deciphered the format of the core BSP node structure.