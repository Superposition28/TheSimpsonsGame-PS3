--[[
Refresh quoted res://assets/ paths in Godot scenes using the maps copied with
that project's assets. No region-specific
GameFiles maps or historical UID migrations are used.

Run operation 17 (Copy GameFiles Assets to Godot) first. Options: --project DIR, --dry-run,
--help/-h. The default project is {{Game_Root}}/Godot/GodotGame/PreBuilt.
Unresolved references remain unchanged and cause the operation to fail after
reporting all findings. Dry runs report the same findings without writing files.
Set GodotRefreshImportOnly=true before import() to expose the typed Godot*
helpers as globals without running the operation. Restore the flag afterward.
]]

import(join(Game_Root, "operations", "godot", "GodotProgress.lua"))

---@class GodotRefreshOptions
---@field ProjectRoot string
---@field DryRun boolean
---@field Help boolean

---@class GodotAssetMapping
---@field uid string
---@field original_path string
---@field new_path string

---@class GodotRefreshResults
---@field Stats table<string, integer>
---@field Unresolved table<string, table<string, boolean>>

local AssetPrefix = "res://assets/"
local Utf8Bom = "﻿"
local BinaryUtf8Bom = string.char(239, 187, 191)
---@type table<string, table<string, boolean>>
local ConvertedExtensions = {
    [".preinstanced"] = { [".glb"] = true, [".fbx"] = true, [".blend"] = true },
    [".inf"] = { [".fnt"] = true },
    [".vp6"] = { [".ogv"] = true },
}
---@type table<string, boolean>
local ExcludedDirectories = { assets = true, [".godot"] = true, [".history"] = true, [".backup"] = true }

---@param Values table<string, any>
---@return string[]
function GodotSortedKeys(Values)
    local Keys = {}
    for Key in pairs(Values) do
        Keys[#Keys + 1] = Key
    end
    table.sort(Keys)
    return Keys
end

---@param Arguments string[]
---@return GodotRefreshOptions
local function ParseArguments(Arguments)
    ---@type GodotRefreshOptions
    local Options = { ProjectRoot = join(Game_Root, "Godot", "GodotGame", "PreBuilt"), DryRun = false, Help = false }
    local Index = 1
    while Index <= #Arguments do
        local Argument = Arguments[Index]
        local InlineProject = Argument:match("^%-%-project=(.*)$")
        if Argument == "--project" or InlineProject ~= nil then
            if InlineProject == nil then
                Index = Index + 1
            end
            local Value = InlineProject or Arguments[Index]
            assert(Value and Value:match("%S") and Value:sub(1, 1) ~= "-", "--project requires a directory.")
            Options.ProjectRoot = Value
        elseif Argument == "--dry-run" then
            Options.DryRun = true
        elseif Argument == "--help" or Argument == "-h" then
            Options.Help = true
        else
            assert(false, "Unknown argument: " .. Argument)
        end
        Index = Index + 1
    end
    Options.ProjectRoot = sdk.absolute_path(Options.ProjectRoot)
    return Options
end

---@param Value any
---@param Context string
---@return string
function GodotRelativeAssetPath(Value, Context)
    assert(type(Value) == "string" and Value:match("%S"), Context .. ": expected a nonempty relative path")
    ---@cast Value string
    local Path = Value:gsub("\\", "/")
    assert(Path:sub(1, 1) ~= "/" and not Path:find(":", 1, true), Context .. ": unsafe relative path: " .. Value)
    local Parts = {}
    for Part in Path:gmatch("[^/]+") do
        assert(Part ~= "..", Context .. ": unsafe relative path: " .. Value)
        if Part ~= "." then
            Parts[#Parts + 1] = Part
        end
    end
    return #Parts > 0 and table.concat(Parts, "/") or "."
end

---@param AssetsRoot string
---@return string[]
function GodotDiscoverAssetMaps(AssetsRoot)
    assert(sdk.is_dir(AssetsRoot), "Assets directory not found: " .. AssetsRoot .. ". Run operation 17 (Copy GameFiles Assets to Godot) first.")
    local FullMap = join(AssetsRoot, "normalized_map.json")
    if sdk.is_file(FullMap) then
        return { FullMap }
    end
    local Maps = {}
    for _, Name in ipairs(sdk.list_dir(AssetsRoot)) do
        local Path = join(AssetsRoot, Name)
        if Name:match("^map_.*%.json$") and sdk.is_file(Path) then
            Maps[#Maps + 1] = Path
        end
    end
    table.sort(Maps)
    assert(#Maps > 0, "No normalized_map.json or map_*.json found in " .. AssetsRoot .. ". Copy the asset maps with the assets.")
    return Maps
end

--- Count top-level rows after JSON validation, retaining null slots that the SDK
--- decoder represents as nil. Quotes and escapes may contain commas or brackets.
---@param Content string
---@return integer
local function MapRowCount(Content)
    if Content:match("^%s*%[%s*%]%s*$") then
        return 0
    end
    local Count, Depth = 1, 0
    local InString, Escaped = false, false
    for Index = 1, #Content do
        local Character = Content:sub(Index, Index)
        if InString then
            if Escaped then
                Escaped = false
            elseif Character == "\\" then
                Escaped = true
            elseif Character == '"' then
                InString = false
            end
        elseif Character == '"' then
            InString = true
        elseif Character == "[" or Character == "{" then
            Depth = Depth + 1
        elseif Character == "]" or Character == "}" then
            Depth = Depth - 1
        elseif Character == "," and Depth == 1 then
            Count = Count + 1
        end
    end
    return Count
end

---@param MapPaths string[]
---@return table<string, GodotAssetMapping[]> ByUid
---@return integer Count
function GodotLoadAssetMaps(MapPaths)
    local PreviousActivity = GodotProgressPush("Load normalization maps", #MapPaths)
    ---@type table<string, GodotAssetMapping[]>
    local ByUid = {}
    local Seen, Count = {}, 0
    for _, MapPath in ipairs(MapPaths) do
        GodotProgressDetail(MapPath, true)
        local Content = sdk.read_file(MapPath)
        assert(Content, "Cannot read asset map: " .. MapPath)
        if Content:sub(1, #Utf8Bom) == Utf8Bom then
            Content = Content:sub(#Utf8Bom + 1)
        end
        -- The JSON decoder represents both arrays and objects as Lua tables.
        assert(Content:match("^%s*%["), MapPath .. ": expected an array of asset mappings")
        local Data = sdk.text.json.decode(Content)
        assert(type(Data) == "table", "Cannot decode asset map: " .. MapPath)
        local RowCount = MapRowCount(Content)
        GodotProgressDiscover(RowCount)
        for Index = 1, RowCount do
            local Row = Data[Index]
            local Context = MapPath .. ", entry " .. Index
            assert(type(Row) == "table" and type(Row.uid) == "string" and #Row.uid >= 6
                and Row.uid:match("^%x+$"), Context .. ": missing or invalid asset UID")
            ---@cast Row GodotAssetMapping
            ---@type GodotAssetMapping
            local Entry = {
                uid = Row.uid:lower(),
                original_path = GodotRelativeAssetPath(Row.original_path, Context),
                new_path = GodotRelativeAssetPath(Row.new_path, Context),
            }
            local Key = sdk.text.json.encode({ Entry.uid, Entry.original_path, Entry.new_path })
            if not Seen[Key] then
                Seen[Key] = true
                ByUid[Entry.uid] = ByUid[Entry.uid] or {}
                table.insert(ByUid[Entry.uid], Entry)
                Count = Count + 1
            end
            GodotProgressAdvance(Entry.uid)
        end
        GodotProgressAdvance(MapPath)
    end
    assert(Count > 0, "Asset maps contain no mappings; no scenes were changed.")
    GodotProgressPop(PreviousActivity)
    return ByUid, Count
end

---@param Path string
---@return string
local function Extension(Path)
    local Name = Path:gsub("\\", "/"):match("[^/]+$") or ""
    return (Name:match("(%.[^.]+)$") or ""):lower()
end

---@param Entry GodotAssetMapping
---@param Reference string
---@return string|nil
function GodotTargetAssetPath(Entry, Reference)
    local SourceExtension, RequestedExtension = Extension(Entry.new_path), Extension(Reference)
    if SourceExtension == RequestedExtension then
        return Entry.new_path
    end
    if ConvertedExtensions[SourceExtension] and ConvertedExtensions[SourceExtension][RequestedExtension] then
        return Entry.new_path:sub(1, #Entry.new_path - #SourceExtension) .. RequestedExtension
    end
    return nil
end

--- Read the normalization UID before the first extension (also .rws.PS3.glb).
---@param Reference string
---@return string|nil
function GodotExtractAssetUid(Reference)
    local Name = Reference:gsub("\\", "/"):match("[^/]+$") or ""
    local Stem = Name:match("^[^.]*") or ""
    local Uid = Stem:match("_(%x+)$")
    return Uid and #Uid >= 6 and Uid:lower() or nil
end

---@param Reference string
---@param ByUid table<string, GodotAssetMapping[]>
---@param AssetsRoot string
---@return string|nil Path
---@return string Reason
function GodotResolveAssetReference(Reference, ByUid, AssetsRoot)
    local Uid = GodotExtractAssetUid(Reference)
    if not Uid then
        return nil, "no_uid"
    end
    local Targets = {}
    for _, Entry in ipairs(ByUid[Uid:lower()] or {}) do
        local Target = GodotTargetAssetPath(Entry, Reference)
        if Target then
            Targets[Target] = true
        end
    end
    local Paths = GodotSortedKeys(Targets)
    if #Paths == 0 then
        return nil, "missing_uid_or_format"
    end
    local Target = Paths[1]
    if #Paths > 1 then
        Target = Reference:sub(#AssetPrefix + 1)
        if not Targets[Target] then
            return nil, "ambiguous_uid"
        end
    end
    -- sdk.realpath currently only makes a path absolute; it does not resolve
    -- directory links. Reject linked components to prevent escaping assets/.
    local AssetFile = AssetsRoot
    for Part in Target:gmatch("[^/]+") do
        AssetFile = join(AssetFile, Part)
        if sdk.is_symlink(AssetFile) then
            return nil, "missing_asset_file"
        end
    end
    if not sdk.is_file(AssetFile) then
        return nil, "missing_asset_file"
    end
    return AssetPrefix .. Target, "resolved"
end

---@param Directory string
---@param Scenes string[]
---@return nil
local function FindScenes(Directory, Scenes)
    local Names = sdk.list_dir(Directory)
    GodotProgressDiscover(#Names)
    for _, Name in ipairs(Names) do
        local Path = join(Directory, Name)
        if sdk.is_dir(Path) then
            if not ExcludedDirectories[Name] and not sdk.is_symlink(Path) then
                FindScenes(Path, Scenes)
            end
        elseif Name:lower():match("%.tscn$") and sdk.is_file(Path) then
            Scenes[#Scenes + 1] = Path
        end
        GodotProgressAdvance(Path)
    end
end

---@param Results GodotRefreshResults
---@param Key string
---@param Count integer|nil
---@return nil
local function Increment(Results, Key, Count)
    Results.Stats[Key] = (Results.Stats[Key] or 0) + (Count or 1)
end

---@param Options GodotRefreshOptions
---@param ByUid table<string, GodotAssetMapping[]>
---@param AssetsRoot string
---@return GodotRefreshResults
local function RefreshScenes(Options, ByUid, AssetsRoot)
    ---@type GodotRefreshResults
    local Results = { Stats = {}, Unresolved = {} }
    local Scenes = {}
    GodotProgressStage("Discover Godot scene files")
    FindScenes(Options.ProjectRoot, Scenes)
    table.sort(Scenes)
    if #Scenes == 0 then
        print("[WARNING] No .tscn files found in " .. Options.ProjectRoot)
    end
    GodotProgressStage(Options.DryRun and "Preview scene asset paths" or "Refresh scene asset paths")
    GodotProgressActivity("Process Godot scenes", #Scenes)
    for Index, Scene in ipairs(Scenes) do
        GodotProgressDetail(Scene, Index == 1)
        Increment(Results, "scanned_files")
        -- SDK text reads strip the BOM. Inspect its bytes separately and restore
        -- U+FEFF on write, retaining Unicode text and all original line endings.
        local Handle, Message = io.open(Scene, "rb")
        assert(Handle, Message or ("Cannot open scene: " .. Scene))
        ---@cast Handle FileHandle
        local HasBom = Handle:read(3) == BinaryUtf8Bom
        Handle:close()
        local Content = sdk.read_file(Scene)
        assert(Content, "Cannot read scene: " .. Scene)
        local Changes = 0
        ---@param Line string
        ---@return string
        local function ReplaceLine(Line)
            ---@param Reference string
            ---@return string
            local function ReplacePath(Reference)
                local NewPath, Reason = GodotResolveAssetReference(Reference, ByUid, AssetsRoot)
                if not NewPath then
                    Increment(Results, Reason)
                    Results.Unresolved[Reason] = Results.Unresolved[Reason] or {}
                    Results.Unresolved[Reason][Scene .. ": " .. Reference] = true
                elseif NewPath == Reference then
                    Increment(Results, "already_correct")
                else
                    Changes = Changes + 1
                    Increment(Results, "updated_references")
                end
                return '"' .. (NewPath or Reference) .. '"'
            end
            local Updated = Line:gsub('"(res://assets/[^"\r\n]+)"', ReplacePath)
            if Updated ~= Line and Line:match("^%s*%[ext_resource ") then
                local Removed
                Updated, Removed = Updated:gsub('%s+uid="uid://[^"\r\n]+"', "")
                if Removed > 0 then
                    Increment(Results, "cleared_godot_uid_hints", Removed)
                end
            end
            return Updated
        end
        local Updated = Content:gsub("[^\r\n]+", ReplaceLine)
        if Changes > 0 then
            Increment(Results, "modified_files")
            print(string.format("[%s] %s (%d references)", Options.DryRun and "PREVIEW" or "UPDATED", Scene, Changes))
            if not Options.DryRun then
                assert(sdk.write_file(Scene, (HasBom and Utf8Bom or "") .. Updated), "Cannot write scene: " .. Scene)
            end
        end
        GodotProgressAdvance(Scene, Changes == 0)
    end
    return Results
end

---@param Options GodotRefreshOptions
---@return nil
local function RunRefresh(Options)
    GodotProgressStage("Load the project's asset maps")
    assert(sdk.is_dir(Options.ProjectRoot), "Godot project directory not found: " .. Options.ProjectRoot)
    local AssetsRoot = join(Options.ProjectRoot, "assets")
    local Maps = GodotDiscoverAssetMaps(AssetsRoot)
    local ByUid, Count = GodotLoadAssetMaps(Maps)
    print(string.format("Loaded %d mappings from: %s", Count, table.concat(Maps, ", ")))
    local Results = RefreshScenes(Options, ByUid, AssetsRoot)
    GodotProgressStage("Report scene-path refresh results")
    for _, Reason in ipairs(GodotSortedKeys(Results.Unresolved)) do
        local References = GodotSortedKeys(Results.Unresolved[Reason])
        print(string.format("[WARNING] %s: %d unique unresolved references (left unchanged)", Reason, #References))
        for _, Reference in ipairs(References) do
            print("  " .. Reference)
        end
    end
    local Summary = {}
    for _, Key in ipairs(GodotSortedKeys(Results.Stats)) do
        Summary[#Summary + 1] = Key .. "=" .. Results.Stats[Key]
    end
    print("Summary: " .. table.concat(Summary, ", "))
    if Options.DryRun then
        print("Dry run: no scenes were modified.")
    end
    assert(next(Results.Unresolved) == nil, "Unresolved asset references remain; see warnings above.")
end

---@return nil
local function Main()
    local Options = ParseArguments(argv or {})
    if Options.Help then
        print("Refresh Godot scene asset paths from maps copied into the project's assets directory.\n"
            .. "Options: --project DIR, --dry-run, --help/-h\nDefault project: " .. Options.ProjectRoot)
        return
    end
    ---@return nil
    local function Work()
        RunRefresh(Options)
    end
    GodotProgressRun(4, "Refresh Godot Scene Asset Paths", Work)
end

if not _G.GodotRefreshImportOnly then
    local Success, Message = pcall(Main)
    if not Success then
        GodotReportError(Message)
        os.exit(1)
    end
end
