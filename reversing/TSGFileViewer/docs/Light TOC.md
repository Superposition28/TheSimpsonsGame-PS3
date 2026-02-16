
# 5. Light TOC

**Handled by:** `Scripts/Resources/LightTOC.cs`

**Type:** Embedded Resource

**Endianness:** Big-Endian

Table of Contents for lights in a scene.

## Header

| Type | Name | Description |
| --- | --- | --- |
| `uint16` | Magic |  |
| `uint16` | Version |  |
| `uint32` | pLightArr | Pointer to standard lights. |
| `uint32` | pBoxLightArr | Pointer to box lights. |
| `uint16` | nLights | Count of standard lights. |
| `uint16` | nBoxLights | Count of box lights. |

## Light Entry (`LightConstructParams`)

Contains `Guid128`, `RwMatrixTag` (Transform), `RwLightType`, Color, Intensity, Radius, and Cone Angle data.

---
