--[[
Lua counterpart of copyassets.ps1. Populate an empty Godot assets/ directory
with supported GameFiles exports and their JSON maps, preserving relative paths.
Existing assets (including their maps) are left unchanged. Add missing logos
from the parent of MainSourcePath and invalidate each new logo's import cache.

Options: --assets-source-path DIR, --main-source-path DIR, --prebuilt-path DIR
(alias --project), --help/-h. Missing source paths come from config.toml's
placeholders. The default destination is Godot/GodotGame/PreBuilt in this module.
]]

import(join(Game_Root, "operations", "godot", "GodotProgress.lua"))

---@class GodotCopyOptions
---@field AssetsSourcePath string|nil
---@field MainSourcePath string|nil
---@field PreBuiltPath string
---@field Help boolean

---@type table<string, boolean>
local AssetExtensions = { [".png"] = true, [".glb"] = true, [".ogv"] = true,
    [".graph"] = true, [".fnt"] = true, [".json"] = true }
---@type table<string, boolean>
local LogoExtensions = { [".png"] = true, [".dat"] = true }
---@type table<string, string>
local PathOptions = {
    ["--assets-source-path"] = "AssetsSourcePath",
    ["--main-source-path"] = "MainSourcePath",
    ["--prebuilt-path"] = "PreBuiltPath",
    ["--project"] = "PreBuiltPath",
}

---@param Arguments string[]
---@return GodotCopyOptions
local function ParseArguments(Arguments)
    ---@type GodotCopyOptions
    local Options = { PreBuiltPath = join(Game_Root, "Godot", "GodotGame", "PreBuilt"), Help = false }
    local Index = 1
    while Index <= #Arguments do
        local Argument = Arguments[Index]
        local Option, InlineValue = Argument:match("^(%-%-[^=]+)=(.*)$")
        Option = Option or Argument
        local Field = PathOptions[Option]
        if Field then
            if InlineValue == nil then
                Index = Index + 1
            end
            local Value = InlineValue or Arguments[Index]
            assert(Value and Value:match("%S") and Value:sub(1, 1) ~= "-", Option .. " requires a directory.")
            Options[Field] = Value
        elseif (Option == "--help" or Option == "-h") and InlineValue == nil then
            Options.Help = true
        else
            assert(false, "Unknown argument: " .. Argument)
        end
        Index = Index + 1
    end
    return Options
end

---@param Placeholders table<string, any>
---@param Name string
---@return string
local function PlaceholderValue(Placeholders, Name)
    local Value = Placeholders[Name]
    assert(type(Value) == "string" and Value:match("%S"), "Missing or invalid '" .. Name .. "' string in config.toml.")
    return Value
end

---@param Options GodotCopyOptions
---@return nil
local function ResolvePaths(Options)
    if not Options.AssetsSourcePath or not Options.MainSourcePath then
        local ConfigPath = join(Game_Root, "config.toml")
        assert(sdk.is_file(ConfigPath), "Game config was not found: " .. ConfigPath)
        local Config = sdk.text.toml.read_file(ConfigPath)
        assert(type(Config) == "table", "Could not read game config: " .. ConfigPath)
        local Placeholders = Config.placeholders
        assert(type(Placeholders) == "table", "Missing placeholders in " .. ConfigPath)
        -- Init writes [[placeholders]]; also accept the [placeholders] form.
        Placeholders = Placeholders[1] or Placeholders
        assert(type(Placeholders) == "table", "Invalid placeholders in " .. ConfigPath)
        if not Options.AssetsSourcePath then
            local Parts = {}
            for _, Name in ipairs({ "Platform", "Region", "Type", "audio_state", "isRenamed" }) do
                Parts[#Parts + 1] = PlaceholderValue(Placeholders, Name)
            end
            Options.AssetsSourcePath = join(Game_Root, "GameFiles", table.concat(Parts, "-"))
        end
        if not Options.MainSourcePath then
            Options.MainSourcePath = PlaceholderValue(Placeholders, "MainSourcePath")
        end
    end
    Options.AssetsSourcePath = sdk.absolute_path(Options.AssetsSourcePath)
    Options.MainSourcePath = sdk.absolute_path(Options.MainSourcePath)
    Options.PreBuiltPath = sdk.absolute_path(Options.PreBuiltPath)
end

---@param Path string
---@return string
local function ParentDirectory(Path)
    local Normalized = Path:gsub("\\", "/"):gsub("/+$", "")
    local Parent = Normalized:match("^(.*)/[^/]+$")
    assert(Parent, "Cannot find parent directory of " .. Path)
    if Parent == "" or Parent:match("^%a:$") then
        Parent = Parent .. "/"
    end
    return Parent
end

---@param Name string
---@return string
local function Extension(Name)
    return (Name:match("(%.[^.]+)$") or ""):lower()
end

--- Collect before copying so generated output cannot enter the traversal.
---@param SourceRoot string
---@param RelativeDirectory string
---@param Files string[] Relative paths beneath SourceRoot.
---@return nil
local function FindAssets(SourceRoot, RelativeDirectory, Files)
    local Directory = RelativeDirectory == "" and SourceRoot or join(SourceRoot, RelativeDirectory)
    local Names = sdk.list_dir(Directory)
    GodotProgressDiscover(#Names)
    for _, Name in ipairs(Names) do
        local RelativePath = RelativeDirectory == "" and Name or join(RelativeDirectory, Name)
        local Path = join(SourceRoot, RelativePath)
        if sdk.is_dir(Path) then
            if Name:lower() ~= ".history" and Name:lower() ~= ".backup" and not sdk.is_symlink(Path) then
                FindAssets(SourceRoot, RelativePath, Files)
            end
        elseif AssetExtensions[Extension(Name)] and sdk.is_file(Path) then
            Files[#Files + 1] = RelativePath
        end
        GodotProgressAdvance(RelativePath)
    end
end

---@param Source string
---@param Destination string
---@return nil
local function CopyFile(Source, Destination)
    local Parent = ParentDirectory(Destination)
    assert(sdk.ensure_dir(Parent), "Cannot create destination directory: " .. Parent)
    assert(sdk.copy_file(Source, Destination, false), "Cannot copy " .. Source .. " to " .. Destination)
end

---@param AssetsDestination string
---@return boolean
local function HasAssetMaps(AssetsDestination)
    for _, Name in ipairs(sdk.list_dir(AssetsDestination)) do
        local LowerName = Name:lower()
        if (LowerName == "normalized_map.json" or LowerName:match("^map_.*%.json$"))
            and sdk.is_file(join(AssetsDestination, Name)) then
            return true
        end
    end
    return false
end

---@param Options GodotCopyOptions
---@return nil
local function CopyAssets(Options)
    local SourceRoot = Options.AssetsSourcePath
    ---@cast SourceRoot string
    assert(sdk.is_dir(SourceRoot), "Flattened asset source directory was not found: " .. SourceRoot)
    local AssetsDestination = join(Options.PreBuiltPath, "assets")
    local LogosDestination = join(Options.PreBuiltPath, "logos")
    assert(sdk.ensure_dir(AssetsDestination), "Cannot create assets directory: " .. AssetsDestination)
    assert(sdk.ensure_dir(LogosDestination), "Cannot create logos directory: " .. LogosDestination)

    local Files = {}
    local Populate = #sdk.list_dir(AssetsDestination) == 0
    GodotProgressStage("Discover supported GameFiles assets")
    if Populate then
        FindAssets(SourceRoot, "", Files)
        table.sort(Files)
    end
    GodotProgressStage("Copy assets and matching maps to Godot")
    GodotProgressActivity("Copy assets", #Files)
    if Populate then
        for Index, RelativePath in ipairs(Files) do
            GodotProgressDetail(RelativePath, Index == 1)
            CopyFile(join(SourceRoot, RelativePath), join(AssetsDestination, RelativePath))
            GodotProgressAdvance(RelativePath)
        end
        print(string.format("Copied %d supported asset file(s) into '%s'.", #Files, AssetsDestination))
    else
        print("Leaving '" .. AssetsDestination .. "' unchanged because it is not empty.")
    end

    GodotProgressStage("Check copied normalization maps")
    GodotProgressActivity("Check normalization maps", 1)
    -- Never repair a populated project's missing maps from another dataset.
    if not HasAssetMaps(AssetsDestination) then
        print("[WARNING] No normalization maps found in '" .. AssetsDestination
            .. "'. RefreshGodotTSCNPaths.lua requires normalized_map.json or map_*.json copied with the matching asset dataset.")
    end
    GodotProgressAdvance("Normalization maps checked")

    GodotProgressStage("Add missing source logos")
    local CopiedLogos = 0
    local MainSourcePath = Options.MainSourcePath
    ---@cast MainSourcePath string
    local IconSourceDirectory = ParentDirectory(MainSourcePath)
    if sdk.is_dir(IconSourceDirectory) then
        local Names = sdk.list_dir(IconSourceDirectory)
        table.sort(Names)
        GodotProgressActivity("Check and copy source logos", #Names)
        for _, Name in ipairs(Names) do
            local Source = join(IconSourceDirectory, Name)
            local Destination = join(LogosDestination, Name)
            if LogoExtensions[Extension(Name)] and sdk.is_file(Source) and not sdk.path_exists(Destination) then
                CopyFile(Source, Destination)
                local ImportPath = Destination .. ".import"
                if sdk.path_exists(ImportPath) and not sdk.remove_file(ImportPath) then
                    print("[WARNING] Could not remove logo import cache: " .. ImportPath)
                end
                CopiedLogos = CopiedLogos + 1
                GodotProgressAdvance(Name)
            else
                GodotProgressAdvance(Name, true)
            end
        end
    end
    print(string.format("Copied %d missing logo file(s).", CopiedLogos))
end

---@return nil
local function Main()
    local Options = ParseArguments(argv or {})
    if Options.Help then
        print("Copy supported GameFiles assets and matching maps into an empty Godot assets/ directory; add missing logos.\n"
            .. "Options: --assets-source-path DIR, --main-source-path DIR, --prebuilt-path/--project DIR, --help/-h\n"
            .. "Default sources: config.toml placeholders. Default project: " .. Options.PreBuiltPath)
        return
    end
    ---@return nil
    local function Work()
        GodotProgressStage("Resolve asset sources and destination")
        ResolvePaths(Options)
        CopyAssets(Options)
    end
    GodotProgressRun(5, "Copy GameFiles Assets to Godot", Work)
end

local Success, Message = pcall(Main)
if not Success then
    GodotReportError(Message)
    os.exit(1)
end
