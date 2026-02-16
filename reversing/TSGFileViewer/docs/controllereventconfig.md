
# 4. Controller Event Config (CEC)

**Handled by:** `Scripts/Resources/ControllerEventConfig.cs`

**Type:** Embedded Resource

**Endianness:** Big-Endian

Defines controller input sequences (combos) and events.

## Header

| Type | Name | Description |
| --- | --- | --- |
| `byte` | Version |  |
| `byte` | Pad |  |
| `int16` | Size | Number of Event Descriptors. |
| `uint32` | ConfigNameHash | SDBM Hash. |
| `byte` | RefCount |  |
| `char[33]` | ConfigName | Name of the configuration. |
| `char[143]` | FileLocation | Source file path. |

## Event Descriptor (`CtrlEventDesc`)

| Type | Name | Description |
| --- | --- | --- |
| `uint32` | HashID | SDBM Hash of event name. |
| `byte` | SeqLen | Length of input sequence. |
| `char[26]` | Name | Event Name. |
| `char[13]` | Category | Event Category. |
| `Struct[7]` | Sequence | Array of `PadPattern` (Stick/Button requirements). |

---
