# Directory normalizer UID contract

Asset UIDs are persistent identifiers. Future changes **must never change an
existing asset's output UID**. Folder flattening, camelCase, TXD export folder
names, rename-map loading, platform/region handling and output format changes
must preserve the current identifiers. Do not regenerate IDs from output paths.

The current baseline hashes the canonical **original source-relative path stem**
with MD5 and takes the first six lowercase hexadecimal characters. Canonical
identity uses the renamed base folder from `config/RenameMap.db`, forward
slashes, and the existing platform/region normalization in
`normalize_to_canonical`. Original and already-renamed base folders must produce
the same UID. Preserve those canonical hash inputs when refactoring; if a source
export layout changes, retain compatibility with the established identity.
Embedded audio UIDs remain unchanged. TXD export folders share the partner TXD's
UID; each exported texture retains its own source-path UID.

The October 2026 UID transition is accepted as a one-time migration. The Godot
PreBuilt references were migrated from the September backup maps to this
baseline. This does not authorize future UID changes.

`tests.lua` pins representative baseline UIDs and checks path-rule invariance.
Run it with the engine Lua script runner before changing normalization or UID
resolution. Add regression cases for affected assets instead of updating pinned
UIDs to accommodate an accidental identity change.
