-- Isolated local project builder; Lua counterpart of build_local_variant.py.
-- Set GodotVariantImportOnly=true before importing to expose the typed global
-- functions without executing a build. No import result is assigned to a table.

local PreviousRefreshMode = _G.GodotRefreshImportOnly
_G.GodotRefreshImportOnly = true
local Imported, ImportFailure = pcall(import, join(Game_Root, "operations", "godot", "RefreshGodotTSCNPaths.lua"))
_G.GodotRefreshImportOnly = PreviousRefreshMode
assert(Imported, tostring(ImportFailure or ""))

import(join(Game_Root, "operations", "godot", "local_variant", "VariantUtils.lua"))
import(join(Game_Root, "operations", "godot", "local_variant", "VariantScenes.lua"))
import(join(Game_Root, "operations", "godot", "local_variant", "VariantBuilder.lua"))
import(join(Game_Root, "operations", "godot", "local_variant", "VariantBuild.lua"))

if not _G.GodotVariantImportOnly then
    local Success, Message = pcall(BuildLocalVariant, argv or {})
    if not Success then
        GodotReportError(Message)
        os.exit(1)
    end
end
