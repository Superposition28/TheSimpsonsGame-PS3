
# 3. MetaModel Format (.mmdl)

**Handled by:** `Scripts/Resources/MetaModel.cs`

**Type:** Embedded Resource

**Endianness:** Big-Endian

A scripting/logic definition format defining states, variables, and predicates for game logic.

## Header

| Type | Name | Description |
| --- | --- | --- |
| `uint32` | Magic | `MMdl` (`0x4D4D646C`). |
| `uint32` | Version | Expected: `0xA`. |
| `uint32` | Size | Total size. |
| `uint32` | Flags |  |
| `Guid128` | GUID | Resource ID. |
| `uint32` | uName | Name hash/offset. |
| `uint32` | uPath | Path hash/offset. |
| `uint32` | uSourcePath | Source path hash/offset. |

## Data Sections

The header is followed by offsets (int32) to the following arrays:

1. **Assets**: External references.
2. **States**: Logic states (contain Parts and Predicates).
3. **Variables**: Typed variables (Bool, Uint32, Float).
4. **Attributes**: Properties of objects.
5. **Predicates**: Conditional logic comparing variables.
6. **Parts**: Components of a state (e.g., ModelPart, MetaModelPart).

---
