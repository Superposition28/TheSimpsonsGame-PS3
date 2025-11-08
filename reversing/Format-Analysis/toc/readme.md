

Table of Contents

more than one kind of .toc format

header
6F 63 74 63
marker
6F 63 63 6C

based on only two files further analysis needed




spr_hub.str.occ.toc — Occlusion Table of Contents

Magic: 6F 63 74 63 → "octc".

What it indexes: entries inside the occlusion (.occ) stream for the Springfield Hub. It’s a tiny index the engine uses to seek into a larger occlusion blob and to attach some metadata for each occlusion set/cell.

Layout you can rely on (big-endian):

Header:

octc (4B)

a few u32s (version / counts / header size; e.g., 00 00 00 03, 00 00 00 2E, 00 00 00 10).

Then a repeating 12-byte triplet per entry:

u32 name/hash/CRC (looks like CRC32-ish values: e.g., 3A E1 D2 5A, 39 F4 12 5B, …).

u32 file offset into the backing occlusion stream (e.g., 00 00 02 70, 00 00 02 A0, …).

u32 flags/count (commonly 00 00 00 01 here).

After the directory, you hit one or more occlusion blocks:

Tag: 6F 63 63 6C → "occl".

Likely version (00 00 00 05) and a small fixed header.

Then float triplets (you can see clean IEEE-754 values): these read like AABBs/OBBs/portals for the occlusion volumes or PVS cells (min/max XYZ or center/extent sets).
Example floats in your dump: C2 14 16 BC (~−36.33), 42 64 FD BE (~57.24), etc., coming in groups you can parse as vectors.

Purpose in runtime: a fast seek table for occlusion data. Streamer opens the occlusion blob, reads octc, and for the current map sector/cell pulls the right "occl" chunk (volumes/planes/portals) to feed the visibility solver and quickly cull draw calls.

2) stream.toc — Generic Streaming TOC for the map’s big “.str” pack

Label context: spr_hub_global_str\stream.toc → this is the master TOC for the global stream bundle used by the Springfield Hub (geometry, instances, rigid sets, collision, light/probe banks, etc.—whatever that global pack contains).

No ASCII magic at start: first dword 9C BA 7B 28 is not text; treat the file as big-endian with a small header that includes a count (you can see 00 00 00 09 early on).

What the records look like: highly regular records repeating all the way down:

You keep seeing patterns like:

a couple of offset/size pairs that strictly increase (… 00 00 03 F4, 00 00 04 78, later 00 00 05 35, 00 00 05 53, …),

small type/flag fields (e.g., 01 00 0F 00, 01 00 0A 00, 01 00 02 00),

tile-ish coordinates pop up early (00 28 00 27 → 0x28/0x27) which is very typical of EA’s regionized streaming where each record is tied to a world-grid tile or sector,

repeated constants like 00 00 03 F4 (1012) and 00 00 03 DC (988) that look like block sizes or header sizes for specific resource classes.

How to think of it structurally:

Header: seed/check (the first dword), entry count, and a few fixed params.

For each entry (resource/subpack):

u32 file offset (into the big .str bundle),

u32 size (or compressed size),

u16/u16 style type + flags (your 01 00 0F 00 patterns),

sometimes an uncompressed size or second size (you often see two close-by size-ish fields),

optional tile indices or stream group id (those 00 28 00 27-style pairs).

Purpose in runtime: this is the index the EA stream loader uses to:

resolve which sub-lump to fetch (by id/type/tile),

seek to the correct offset in the .str file,

know how much to read (and sometimes how to decompress),

pick the correct handler for that resource type (driven by the type/flag field).