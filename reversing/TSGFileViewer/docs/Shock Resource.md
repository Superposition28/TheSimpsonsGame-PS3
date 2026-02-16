
# 7. Shock Resource (SHK)

**Handled by:** `Scripts/Resources/ShockResource.cs`

**Type:** Embedded Resource

**Endianness:** Big-Endian

Defines controller vibration/rumble patterns.

## Structure

| Type | Name | Description |
| --- | --- | --- |
| `uint32` | NameHash |  |
| `int16` | Version |  |
| `int16` | CmdCount | Number of commands. |
| `uint32` | Ptr | Runtime memory address (unused). |
| `Array` | Commands | Array of `ShockCommand` (TimeOffset, MotorId, ActuatorValue). |

---
