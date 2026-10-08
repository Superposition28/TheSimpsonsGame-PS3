-- RemakeEngine Module Init (The Simpsons Game - PS3)
-- Entrypoint for initialization. Argument parsing and source orchestration live
-- in dedicated modules so callers can use the same flow interactively or by CLI.

---@type SharedUtils
import(join(Game_Root, "operations", "SharedUtils.lua"))

---@type SharedUtilsColours
local Colours = Colours

---@type init
import("util.lua")

---@type InitCli
local Cli = import("cli.lua")
---@type InitCore
local Core = import("core.lua")

if _G.__tsg_init_import_only then
    return Core.main
end

local ok, result = pcall(Core.main, Cli.parse_args())
if not ok or not result then
    colour_print({
        colour = Colours.RED,
        message = "Initialization failed with error: " .. tostring(result)
    })
    os.exit(1)
end