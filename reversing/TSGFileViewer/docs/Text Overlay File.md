
# 6. Text Overlay File (TOB)

**Handled by:** `Scripts/Resources/TextOverlayFile.cs`

**Type:** Embedded Resource

**Endianness:** Big-Endian

Handles timing and synchronization for text overlays (subtitles/UI).

## Header

| Type | Name | Description |
| --- | --- | --- |
| `uint32` | ChunkID |  |
| `uint32` | FileSize |  |
| `uint32` | Version |  |
| `uint32` | NumEntries | Number of text entries. |

## Entry

| Type | Name | Description |
| --- | --- | --- |
| `uint32` | HashID | Text ID hash. |
| `uint32` | StartTimeMS | Start time in milliseconds. |
| `uint32` | DurationMS | Duration in milliseconds. |
| `int32` | UserData |  |

---
