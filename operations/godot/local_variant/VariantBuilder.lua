-- Dataset resolution, dependency copying, nested overrides, and collision jobs.
-- Import through BuildLocalVariant.lua, which loads the typed global helpers.

local Excluded = { [".godot"]=true, [".git"]=true, [".history"]=true, [".backup"]=true,
    __pycache__=true, ["./assets"]=true, ["./logos"]=true }
local TextTypes = { [".tscn"]=true, [".tres"]=true, [".gd"]=true, [".godot"]=true,
    [".gdshader"]=true, [".gdshaderinc"]=true, [".cfg"]=true, [".fnt"]=true }

---@param Options VariantOptions
---@return VariantBuilder
function VariantNewBuilder(Options)
    local Assets = VariantAbsolute(Options.Assets)
    local ByUid = GodotLoadAssetMaps(GodotDiscoverAssetMaps(Assets))
    local Logos = VariantAbsolute(Options.Logos or join(dirname(Assets), "logos"))
    ---@type VariantBuilder
    local Builder = {
        Project=VariantAbsolute(Options.Project), Assets=Assets,
        Source=Options.Source and VariantAbsolute(Options.Source) or nil,
        Logos=Logos, Collision=Options.Collision, ByUid=ByUid, CollisionByDirectory={},
        Materialized={}, Jobs={}, Attachments={}, SceneInstances={}, Preview=false,
        Report={schema_version=1, canonical_project=VariantAbsolute(Options.Project), assets=Assets,
            source=Options.Source or "None", logos=Logos, collision_enabled=Options.Collision,
            disabled={}, collisions={}, warnings={}},
    }
    local Entries = VariantOrderedEntries(ByUid)
    local PreviousActivity = GodotProgressPush("Index asset and collision mappings", #Entries)
    for _, Entry in ipairs(Entries) do
        if Entry.new_path:lower():match("%.hk[ot]%.[^.]+$") then
            local Directory = dirname(Entry.original_path):gsub("\\", "/")
            Builder.CollisionByDirectory[Directory] = Builder.CollisionByDirectory[Directory] or {}
            table.insert(Builder.CollisionByDirectory[Directory], Entry)
        end
        GodotProgressAdvance(Entry.uid)
    end
    GodotProgressPop(PreviousActivity)
    return Builder
end

---@param Builder VariantBuilder
---@param Reference string
---@param Stage string
---@return boolean
function VariantAuxiliary(Builder, Reference, Stage)
    if Reference:sub(1, 12) ~= "res://logos/" then return false end
    local Original = VariantCheckedPath(Builder.Logos, Reference:sub(13))
    if not sdk.is_file(Original) then return false end
    if not Builder.Preview then
        local Target = VariantCheckedPath(Stage, Reference:sub(7))
        if not sdk.path_exists(Target) then VariantCopy(Original, Target) end
    end
    return true
end

---@param Builder VariantBuilder
---@param Reference string
---@return string|nil Resolved
---@return string Reason
function VariantResolve(Builder, Reference)
    local Uid = GodotExtractAssetUid(Reference)
    if not Uid then return nil, "no_normalization_uid" end
    local Targets = {}
    for _, Entry in ipairs(Builder.ByUid[Uid] or {}) do
        local Target = GodotTargetAssetPath(Entry, Reference)
        if Target then Targets[Target] = true end
    end
    local Paths = GodotSortedKeys(Targets)
    if #Paths ~= 1 then return nil, #Paths > 0 and "ambiguous_uid" or "missing_uid_or_format" end
    if not sdk.is_file(VariantCheckedPath(Builder.Assets, Paths[1])) then return nil, "missing_asset_file" end
    return "res://assets/" .. Paths[1], "resolved"
end

---@param Builder VariantBuilder
---@param Reference string
---@param Stage string
---@return nil
local function Materialize(Builder, Reference, Stage)
    if Builder.Materialized[Reference] then return end
    GodotProgressDiscover(1)
    Builder.Materialized[Reference] = true
    local Relative = Reference:sub(14)
    local Original = VariantCheckedPath(Builder.Assets, Relative)
    if not Builder.Preview then VariantCopy(Original, VariantCheckedPath(Stage, "assets/" .. Relative)) end
    local Dependencies = {}
    if VariantExtension(Original) == ".fnt" then
        for Dependency in VariantRead(Original):gmatch('%f[%w]file="([^"]+)"') do Dependencies[#Dependencies + 1] = Dependency end
    elseif VariantExtension(Original) == ".gltf" then
        local Data = VariantReadJson(Original)
        for _, Group in ipairs({ "buffers", "images" }) do
            for _, Item in ipairs(Data[Group] or {}) do
                if type(Item.uri) == "string" and Item.uri:sub(1, 5) ~= "data:" then Dependencies[#Dependencies + 1] = Item.uri end
            end
        end
    end
    for _, Dependency in ipairs(Dependencies) do
        local Path = VariantCheckedPath(Builder.Assets, dirname(Relative) .. "/" .. Dependency)
        assert(sdk.is_file(Path), "Missing asset dependency: " .. Original .. ": " .. Dependency)
        local AssetRelative = get_relative_path(Builder.Assets, Path):gsub("\\", "/")
        Materialize(Builder, "res://assets/" .. AssetRelative, Stage)
    end
    GodotProgressAdvance(Relative)
end

---@param Builder VariantBuilder
---@param Reference string
---@param Stage string
---@return nil
function VariantMaterialize(Builder, Reference, Stage)
    if Builder.Materialized[Reference] then return end
    local PreviousActivity = GodotProgressPush("Copy referenced assets and dependencies", 0)
    Materialize(Builder, Reference, Stage)
    GodotProgressPop(PreviousActivity)
end

---@param Left GodotAssetMapping
---@param Right GodotAssetMapping
---@return boolean
local function SameMapping(Left, Right)
    return Left.uid == Right.uid and Left.original_path == Right.original_path and Left.new_path == Right.new_path
end

---@param Builder VariantBuilder
---@param Reference string
---@return string|nil Uid
---@return string Status
function VariantCollisionJob(Builder, Reference)
    local Models = {}
    for _, Entry in ipairs(Builder.ByUid[GodotExtractAssetUid(Reference) or ""] or {}) do
        if GodotTargetAssetPath(Entry, Reference) == Reference:sub(14) then Models[#Models + 1] = Entry end
    end
    if #Models ~= 1 then return nil, "ambiguous_model_mapping" end
    local Model = Models[1]
    if Model.original_path:lower():sub(1, 14) == "a2_characters/" then return nil, "character_collision_excluded" end
    local Directory = dirname(Model.original_path):gsub("\\", "/")
    if basename(Directory):lower() == "terrain" then Directory = dirname(Directory):gsub("\\", "/") end
    local Candidates = {}
    for _, Location in ipairs({ Directory .. "/collision", Directory }) do
        for _, Entry in ipairs(Builder.CollisionByDirectory[Location] or {}) do Candidates[#Candidates + 1] = Entry end
    end
    if #Candidates ~= 1 then return nil, #Candidates > 0 and "ambiguous_collision" or "no_original_collision_match" end
    if not Builder.Source then return nil, "no_collision_source_selected" end
    if not Builder.SourceEntries then Builder.SourceEntries = GodotLoadAssetMaps(GodotDiscoverAssetMaps(Builder.Source)) end
    local Entry = Candidates[1]
    for _, Expected in ipairs({ Model, Entry }) do
        local Matches = Builder.SourceEntries[Expected.uid] or {}
        assert(#Matches == 1 and SameMapping(Matches[1], Expected), "Selected source maps disagree with asset dataset for UID " .. Expected.uid)
    end
    local Exported = VariantCheckedPath(Builder.Source, Reference:sub(14))
    assert(not sdk.is_file(Exported) or VariantSameFile(Exported, VariantCheckedPath(Builder.Assets, Reference:sub(14))),
        "Selected source GLB differs from asset dataset for UID " .. Model.uid)
    local Raw = VariantCheckedPath(Builder.Source, Entry.new_path)
    if not sdk.is_file(Raw) then return nil, "missing_collision_file" end
    -- Godot's native FileAccess.get_sha256 fills this in a single batch before
    -- bake.gd runs. Lua's SDK exposes SHA-1 only; persisted hashes stay SHA-256.
    Builder.Jobs[Entry.uid] = { uid=Entry.uid, source=Raw, source_hash="", canonical_path=Entry.original_path,
        output="res://generated_collision/" .. Entry.uid .. ".tscn" }
    return Entry.uid, "pending"
end

---@param Builder VariantBuilder
---@return nil
function VariantPreview(Builder)
    Builder.Preview = true
    local Files = {}
    local PreviousActivity = GodotProgressPush("Discover scenes for variant preview", 0)
    VariantFindFiles(Builder.Project, "", Files, Excluded, false)
    table.sort(Files)
    GodotProgressActivity("Preview canonical scenes", #Files)
    for _, Relative in ipairs(Files) do
        local Extension = VariantExtension(Relative)
        if Extension == ".tscn" or Extension == ".tres" then
            VariantAdaptScene(Builder, VariantRead(join(Builder.Project, Relative)), Relative, Builder.Project)
        end
        GodotProgressAdvance(Relative, Extension ~= ".tscn" and Extension ~= ".tres")
    end
    GodotProgressPop(PreviousActivity)
    print(string.format("Would copy %d referenced assets, bake %d collision files, and disable %d missing references.",
        #GodotSortedKeys(Builder.Materialized), #GodotSortedKeys(Builder.Jobs), #Builder.Report.disabled))
    local Counts = {}
    for _, Row in ipairs(Builder.Report.collisions) do Counts[Row.status] = (Counts[Row.status] or 0) + 1 end
    print("Collision coverage: " .. sdk.text.json.encode(Counts))
end

---@param Builder VariantBuilder
---@param Stage string
---@return nil
function VariantSuppressNestedOverrides(Builder, Stage)
    ---@type table<string, VariantBlock[]>
    local Scenes = {}
    local Files = {}
    local PreviousActivity = GodotProgressPush("Discover nested scene overrides", 0)
    VariantFindFiles(Stage, "", Files, Excluded, false)
    table.sort(Files)
    GodotProgressActivity("Read staged scene overrides", #Files)
    for _, Relative in ipairs(Files) do
        if VariantExtension(Relative) == ".tscn" then Scenes[Relative] = VariantParseBlocks(VariantRead(join(Stage, Relative))) end
        GodotProgressAdvance(Relative, VariantExtension(Relative) ~= ".tscn")
    end
    ---@type table<string, table<string, boolean>>
    local Cache = {}
    ---@param Relative string
    ---@param Visiting table<string, boolean>
    ---@return table<string, boolean>
    local function DisabledIn(Relative, Visiting)
        if Cache[Relative] then return Cache[Relative] end
        assert(not Visiting[Relative], "Cyclic scene dependencies: " .. Relative)
        Visiting[Relative] = true
        local Blocks, Result, Refs = Scenes[Relative] or {}, {}, {}
        for _, Block in ipairs(Blocks) do
            local Kind = VariantBlockKind(Block)
            if Kind == "node" and Block.Body:find("metadata/variant_disabled = true", 1, true) then Result[VariantNodePath(Block)] = true end
            if Kind == "ext_resource" then local Attr = VariantAttributes(Block); Refs[Attr.id] = Attr.path or "" end
        end
        for _, Block in ipairs(Blocks) do
            local Instance = VariantBlockKind(Block) == "node" and Block.Header:match('instance=ExtResource%("([^"]+)"%)')
            if Instance then
                local Child = (Refs[Instance] or ""):gsub("^res://", "")
                for Path in pairs(DisabledIn(Child, Visiting)) do
                    local Prefix = VariantNodePath(Block)
                    Result[Path == "." and Prefix or (Prefix == "." and Path or Prefix .. "/" .. Path)] = true
                end
            end
        end
        Visiting[Relative], Cache[Relative] = nil, Result
        return Result
    end
    local ScenePaths = GodotSortedKeys(Scenes)
    GodotProgressActivity("Suppress unavailable nested overrides", #ScenePaths)
    for _, Relative in ipairs(ScenePaths) do
        local Disabled, Output = DisabledIn(Relative, {}), {}
        for _, Block in ipairs(Scenes[Relative]) do
            local Kind, Attr, Keep = VariantBlockKind(Block), VariantAttributes(Block), true
            if Kind == "node" then
                local Path = VariantNodePath(Block)
                if not Disabled[Path] and VariantDescends(Path, Disabled) then
                    table.insert(Builder.Report.disabled, { scene=Relative, node=Path, reason="override_below_unavailable_instance" })
                    Keep = false
                end
            elseif Kind == "editable" then Keep = not VariantDescends(Attr.path, Disabled)
            elseif Kind == "connection" then Keep = not VariantDescends(Attr.from or "", Disabled) and not VariantDescends(Attr.to or "", Disabled) end
            if Keep then Output[#Output + 1] = Block end
        end
        VariantWrite(join(Stage, Relative), VariantBlocksText(VariantPruneResources(Output)))
        GodotProgressAdvance(Relative)
    end
    GodotProgressPop(PreviousActivity)
end

---@param Builder VariantBuilder
---@param Stage string
---@return nil
function VariantPrepare(Builder, Stage)
    local Files = {}
    GodotProgressActivity("Discover canonical project files", 0)
    VariantFindFiles(Builder.Project, "", Files, Excluded, true)
    table.sort(Files)
    GodotProgressActivity("Copy canonical project files", #Files)
    for _, Relative in ipairs(Files) do
        VariantCopy(join(Builder.Project, Relative), join(Stage, Relative))
        GodotProgressAdvance(Relative)
    end
    local ConfigPath = join(Stage, "project.godot")
    local Text = VariantRead(ConfigPath):gsub(',?%s*"res://addons/local_variant/plugin%.cfg"', "")
    local Paths = {}
    for Path in Text:gmatch('"(res://[^"\r\n]+)"') do Paths[#Paths + 1] = Path end
    for _, Path in ipairs(Paths) do
        VariantAuxiliary(Builder, Path, Stage)
        if Path:sub(1, 13) ~= "res://assets/" and not sdk.path_exists(VariantCheckedPath(Stage, Path:sub(7))) then
            local Extension = VariantExtension(Path)
            assert(Extension ~= ".gd" and Extension ~= ".tscn", "Missing core project resource: " .. Path)
            Text = VariantReplace(Text, sdk.text.json.encode(Path),
                (Path:find("/shader", 1, true) or Extension == ".tres") and "null" or '""')
            table.insert(Builder.Report.warnings, "Missing optional project resource: " .. Path)
        end
    end
    VariantWrite(ConfigPath, Text)
    -- Only the original copied file list is adapted, so a just-materialized font
    -- or glTF dependency is never mistaken for authored project text.
    GodotProgressActivity("Adapt staged project resources", #Files)
    for _, Relative in ipairs(Files) do
        local Extension = VariantExtension(Relative)
        if TextTypes[Extension] then
            local Path = join(Stage, Relative)
            local Original = VariantRead(Path)
            local Adapted
            if Extension == ".tscn" or Extension == ".tres" then Adapted = VariantAdaptScene(Builder, Original, Relative, Stage)
            else Adapted = VariantAdaptText(Builder, Original, Relative, Stage) end
            if Adapted ~= Original then VariantWrite(Path, Adapted) end
        end
        GodotProgressAdvance(Relative, not TextTypes[Extension])
    end
    local Maps = GodotDiscoverAssetMaps(Builder.Assets)
    GodotProgressActivity("Copy matching normalization maps", #Maps)
    for _, Mapping in ipairs(Maps) do
        VariantCopy(Mapping, join(Stage, "assets", basename(Mapping)))
        GodotProgressAdvance(Mapping)
    end
    VariantSuppressNestedOverrides(Builder, Stage)
    local RuntimeRoot, RuntimeFiles = join(Game_Root, "operations", "godot", "variant_runtime"), {}
    GodotProgressActivity("Discover variant runtime helpers", 0)
    VariantFindFiles(RuntimeRoot, "", RuntimeFiles, { [".history"]=true, [".backup"]=true }, false)
    GodotProgressActivity("Copy variant runtime helpers", #RuntimeFiles + 1)
    for _, Relative in ipairs(RuntimeFiles) do
        VariantCopy(join(RuntimeRoot, Relative), join(Stage, ".variant_tools", Relative))
        GodotProgressAdvance(Relative)
    end
    VariantCopy(VariantHavokReaderPath(), join(Stage, ".variant_tools", "tsg_havok_reader.gd"))
    GodotProgressAdvance("tsg_havok_reader.gd")
    local Jobs = {}
    for _, Uid in ipairs(GodotSortedKeys(Builder.Jobs)) do Jobs[#Jobs + 1] = Builder.Jobs[Uid] end
    VariantWriteJson(join(Stage, "variant_jobs.json"), { jobs=Jobs, instances=Builder.SceneInstances })
end

---@param Builder VariantBuilder
---@param Stage string
---@param Results VariantBakeResults
---@return nil
function VariantAttach(Builder, Stage, Results)
    assert(type(Results.jobs) == "table", "Invalid collision bake results")
    local Successful, Statuses = {}, {}
    for _, Row in ipairs(Results.jobs) do
        assert(type(Row.uid) == "string" and Row.uid:match("^%x+$"), "Invalid baked collision UID")
        Statuses[Row.uid] = Row
        if Row.ok then Successful[Row.uid] = true end
    end
    local SuccessfulUids = GodotSortedKeys(Successful)
    GodotProgressActivity("Normalize baked collision scenes", #SuccessfulUids)
    for _, Uid in ipairs(SuccessfulUids) do
        local Path = VariantCheckedPath(Stage, "generated_collision/" .. Uid .. ".tscn")
        local Text = VariantRead(Path):gsub("%s+unique_id=%d+", "")
        local Ids = {}
        for _, Block in ipairs(VariantParseBlocks(Text)) do
            if VariantBlockKind(Block) == "sub_resource" then Ids[#Ids + 1] = VariantAttributes(Block).id end
        end
        for Index, Old in ipairs(Ids) do
            local New = string.format("VariantShape_%06d", Index - 1)
            Text = VariantReplace(VariantReplace(Text, 'id="' .. Old .. '"', 'id="' .. New .. '"'), 'SubResource("' .. Old .. '")', 'SubResource("' .. New .. '")')
        end
        VariantWrite(Path, Text)
        GodotProgressAdvance(Uid)
    end
    ---@type table<string, VariantAttachment[]>
    local ByScene = {}
    for _, Attachment in ipairs(Builder.Attachments) do
        if Successful[Attachment.uid] then
            ByScene[Attachment.scene] = ByScene[Attachment.scene] or {}
            table.insert(ByScene[Attachment.scene], Attachment)
        end
    end
    local ScenePaths = GodotSortedKeys(ByScene)
    GodotProgressActivity("Attach original collision to scenes", #ScenePaths)
    for _, Relative in ipairs(ScenePaths) do
        local Blocks = VariantParseBlocks(VariantRead(join(Stage, Relative)))
        local Insert = #Blocks + 1
        for Index, Block in ipairs(Blocks) do if VariantBlockKind(Block) == "node" then Insert = Index; break end end
        local Uids = {}
        for _, Item in ipairs(ByScene[Relative]) do Uids[Item.uid] = true end
        for _, Uid in ipairs(GodotSortedKeys(Uids)) do
            table.insert(Blocks, Insert, { Header='[ext_resource type="PackedScene" path="res://generated_collision/' .. Uid .. '.tscn" id="VariantCollision_' .. Uid .. '"]', Body="" })
            Insert = Insert + 1
        end
        for _, Item in ipairs(ByScene[Relative]) do
            Blocks[#Blocks + 1] = { Header='[node name="OriginalGameCollision" parent=' .. sdk.text.json.encode(Item.node)
                .. ' instance=ExtResource("VariantCollision_' .. Item.uid .. '")]', Body="" }
        end
        VariantWrite(join(Stage, Relative), VariantBlocksText(Blocks))
        GodotProgressAdvance(Relative)
    end
    Builder.Report.bake_results = Results
    Builder.Report.asset_files_copied = #GodotSortedKeys(Builder.Materialized)
    for _, Row in ipairs(Builder.Report.collisions) do
        local Result = Row.uid and Statuses[Row.uid]
        if Result then Row.status = Result.ok and "baked" or (Result.error or "unsupported_or_malformed") end
    end
end
