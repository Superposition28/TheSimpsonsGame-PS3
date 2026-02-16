
# 2. SimGroup Format

**Handled by:** `Scripts/SimGroup.cs`

**Chunk Type:** `0x2207`

**Endianness:** Big-Endian

Defines a group of entities (game objects) and their attributes (scripts/components).

## Header

| Offset | Type | Name | Description |
| --- | --- | --- | --- |
| 0x00 | `byte[8]` | Padding | Skipped bytes. |
| 0x08 | `uint32` | Magic | `SimG` (`0x53696D47`). |
| 0x0C | `uint32` | Version |  |
| 0x10 | `uint32` | GUID | SimGroup ID (Guid32). |
| 0x14 | `uint32` | Flags |  |
| 0x18 | `uint32` | nEnts | Number of entities defined. |
| 0x1C | `uint32` | nEntsDispatched |  |
| 0x20 | `uint32` | SharedDataSize |  |
| 0x24 | `uint32` | DictionarySize |  |
| 0x28 | `uint32` | ppEntPackets | Offset to the pointer to Entity Packets. |

## Entity Packet

Describes a single object instance.

| Type | Name | Description |
| --- | --- | --- |
| `byte` | Flags | Attribute handler flags. |
| `byte` | SpawnMask | `1` = Active/Spawned. |
| `byte` | nAttachedRes | Number of attached resource GUIDs. |
| `byte` | nAttrPackets | Number of Attribute Packets (components). |
| `int32` | GUIDOffset | Relative offset to the Entity's Guid128. |
| `Guid128` | GUID | 128-bit unique identifier for the entity. |
| `Guid32` | BehaviorID | Identifier for the entity's behavior class. |

## Attribute Packet

Describes a specific component attached to an entity (e.g., `FuncSpawn`, `TriggerBase`).

| Type | Name | Description |
| --- | --- | --- |
| `Guid32` | GUID | ID of the Attribute Handler (Script type). |
| `uint16` | nAttrs | Number of attributes (fields) serialized. |
| `varies` | BitField | `uint16` or `uint32` (if nAttrs > 16). Bitmask indicating which attributes are present. |

**Attribute Data:**
Based on the `BitField`, attributes are read sequentially. Each attribute typically consists of 4 bytes. If the value acts as a pointer (e.g., to a string), it is often a relative offset from the current reader position.

---
