--[[

Reset the game module to its original state by deleting all generated files or moving them to a backup folder.
first prompt user to confirm they understand this
then ask to delete or move to backup folder both irriversable but moving to backup folder is safer and allows manual recovery if needed
then perform the operation

here are the steps to reset the game module:
remove these (if exists): (preserve folder structure in backup if moving to backup folder)
operation_execution.log
game.toml
config.toml (init will recreate it with default placeholders, or import the init code and manually execute that component?, better since init only acts if user exists and reopens the module menu)
Source/ (contains the original game files, this should be prompted as well, as the user may want to keep the original game files in place since they are not modified by the tools)
operations/Blender/blend.log
Godot/GodotGame/PreBuilt/assets/
Godot/GodotGame/PreBuilt/.godot/
GameFiles/

reset wont beable to reset any installed tools, there controlled by the engine not the module, module can only request they be installed not removed

]]

-- Bootstrap the Utils module

---@type SharedUtils
require("SharedUtils")
---@type SharedUtilsColours
local Colours = Colours

---@type init
import("init/util")

---@class ResetOptions
---@field confirmed boolean
---@field include_source boolean
---@field mode "backup"|"delete"

---@class ResetTarget
---@field relative_path string
---@field is_directory boolean

---@param arguments table<integer, string>
---@return ResetOptions
local function parse_args(arguments)
    ---@type ResetOptions
    local options = { confirmed = false, include_source = false, mode = "backup" }
    local index = 1
    while index <= #arguments do
        local argument = arguments[index]
        if argument == "--confirmed" then
            options.confirmed = true
        elseif argument == "--include-source" then
            options.include_source = true
        elseif argument == "--mode" and arguments[index + 1] then
            local mode = string.lower(arguments[index + 1])
            if mode == "backup" or mode == "delete" then
                options.mode = mode
            else
                error("Invalid reset mode: " .. tostring(arguments[index + 1]))
            end
            index = index + 1
        end
        index = index + 1
    end
    return options
end

---@param root string
---@param options ResetOptions
---@return ResetTarget[]
local function build_targets(root, options)
    ---@type ResetTarget[]
    local targets = {
        { relative_path = "operation_execution.log", is_directory = false },
        { relative_path = "game.toml", is_directory = false },
        { relative_path = "config.toml", is_directory = false },
        { relative_path = "operations/Blender/blend.log", is_directory = false },
        { relative_path = "Godot/GodotGame/PreBuilt/assets", is_directory = true },
        { relative_path = "Godot/GodotGame/PreBuilt/.godot", is_directory = true },
        { relative_path = "GameFiles", is_directory = true },
    }
    if options.include_source then
        table.insert(targets, { relative_path = "Source", is_directory = true })
    end
    return targets
end

---@param path string
---@param is_directory boolean
---@return boolean
local function remove_target(path, is_directory)
    if is_directory then
        return sdk.remove_dir(path)
    end
    return sdk.remove_file(path)
end

---@param root string
---@return boolean
local function initialize_module(root)
    _G.__tsg_init_import_only = true
    local initializer = import(join(root, "operations", "init.lua"))
    _G.__tsg_init_import_only = nil
    if type(initializer) ~= "function" then
        error("Unable to load the module initializer.")
    end
    return initializer()
end

---@param root string
---@param options ResetOptions
---@return boolean
local function main(root, options)
    if not options.confirmed then
        colour_print{ colour = Colours.YELLOW, message = "Reset cancelled: confirmation was not provided." }
        return true
    end

    local targets = build_targets(root, options)
    local backup_root = nil
    if options.mode == "backup" then
        local timestamp = os.date("%Y-%m-%d_%H-%M-%S")
        backup_root = join(root, ".backup", timestamp)
        if sdk.path_exists(backup_root) then
            error("Backup path already exists: " .. backup_root)
        end
        if not sdk.ensure_dir(backup_root) then
            error("Unable to create backup directory: " .. backup_root)
        end
    end

    local existing_count = 0
    for _, target in ipairs(targets) do
        local source_path = join(root, target.relative_path)
        if sdk.path_exists(source_path) then
            existing_count = existing_count + 1
        end
    end

    progress.script.start(existing_count, "Resetting game module")
    for _, target in ipairs(targets) do
        local source_path = join(root, target.relative_path)
        if sdk.path_exists(source_path) then
            progress.script.step(target.relative_path)
            local success = false
            if options.mode == "backup" then
                ---@cast backup_root string
                local backup_path = join(backup_root, target.relative_path)
                if not sdk.ensure_dir(dirname(backup_path)) then
                    error("Unable to create backup parent directory: " .. dirname(backup_path))
                end
                success = sdk.rename_file(source_path, backup_path, false)
            else
                success = remove_target(source_path, target.is_directory)
            end
            if not success then
                error("Unable to " .. options.mode .. " reset target: " .. source_path)
            end
            colour_print{ colour = Colours.GREEN, message = options.mode .. ": " .. target.relative_path }
        end
    end
    progress.script.finish()

    if options.mode == "backup" then
        colour_print{ colour = Colours.GREEN, message = "Reset complete. Backup created at: " .. backup_root }
    else
        colour_print{ colour = Colours.GREEN, message = "Reset complete. Generated files were deleted." }
    end

    colour_print{ colour = Colours.BLUE, message = "Running module initialization..." }
    return initialize_module(root)
end

local root = normalize(Game_Root)
local options = parse_args(argv or {})
local ok, result = pcall(main, root, options)
if not ok or not result then
    colour_print{colour=Colours.RED, message="reset failed with error: " .. tostring(result)}
    os.exit(1)
end

