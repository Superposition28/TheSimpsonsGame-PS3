-- Godot text-resource parsing and adaptation. All exported functions are globals.
---@type table<string, boolean>
local HeaderKinds = { gd_scene=true, gd_resource=true, resource=true, ext_resource=true,
    sub_resource=true, node=true, connection=true, editable=true }

---@param Block VariantBlock
---@return string
function VariantBlockKind(Block)
    return Block.Header:match("^%[([%w_]+)") or ""
end

---@param Block VariantBlock
---@return table<string, string>
function VariantAttributes(Block)
    local Attributes, Start = {}, 1
    while true do
        local First, Last, Name = Block.Header:find('([%w_]+)="', Start)
        if not First then break end
        local Cursor, Escaped = Last + 1, false
        while Cursor <= #Block.Header do
            local Character = Block.Header:sub(Cursor, Cursor)
            if Escaped then Escaped = false
            elseif Character == "\\" then Escaped = true
            elseif Character == '"' then break end
            Cursor = Cursor + 1
        end
        assert(Cursor <= #Block.Header, "Unclosed attribute in " .. Block.Header)
        Attributes[Name] = Block.Header:sub(Last + 1, Cursor - 1)
        Start = Cursor + 1
    end
    return Attributes
end

---@param Text string
---@return VariantBlock[]
function VariantParseBlocks(Text)
    local Blocks = {}
    for Line in (Text .. "\n"):gmatch("([^\n]*)\n") do
        local Kind = Line:match("^%[([%w_]+)")
        if Kind and HeaderKinds[Kind] and Line:match("%]%s*$") then
            Blocks[#Blocks + 1] = { Header = Line:gsub("%s+$", ""), Body = "" }
        elseif #Blocks > 0 then
            Blocks[#Blocks].Body = Blocks[#Blocks].Body .. Line .. "\n"
        end
    end
    return Blocks
end

---@param Blocks VariantBlock[]
---@return string
function VariantBlocksText(Blocks)
    local Parts = {}
    for _, Block in ipairs(Blocks) do
        Parts[#Parts + 1] = Block.Header:gsub("%s+$", "") .. "\n"
            .. Block.Body:gsub("^\n+", ""):gsub("\n+$", "") .. "\n\n"
    end
    return table.concat(Parts)
end

---@param Block VariantBlock
---@return string
function VariantNodePath(Block)
    local Attributes = VariantAttributes(Block)
    if not Attributes.parent then return "." end
    assert(Attributes.name, "Node has no name: " .. Block.Header)
    return Attributes.parent == "." and Attributes.name or Attributes.parent .. "/" .. Attributes.name
end

---@param Path string
---@param Roots table<string, boolean>
---@return boolean
function VariantDescends(Path, Roots)
    for Root in pairs(Roots) do
        if Root == "." or Path == Root or Path:sub(1, #Root + 1) == Root .. "/" then return true end
    end
    return false
end

---@param Text string
---@return VariantReference[]
local function ResourceReferences(Text)
    local References = {}
    -- Unanchored %a+ patterns backtrack through long identifiers/embedded text
    -- and exceed MoonSharp's pattern limit on real scenes. Search literals.
    for _, Kind in ipairs({ "ExtResource", "SubResource" }) do
        local Prefix, Start = Kind .. '("', 1
        while true do
            local First, Last = Text:find(Prefix, Start, true)
            if not First then break end
            local End = Text:find('")', Last + 1, true)
            if End and End > Last + 1 and not Text:sub(First - 1, First - 1):match("[%w_]") then
                local Id = Text:sub(Last + 1, End - 1)
                if not Id:find('"', 1, true) and not Id:find("\n", 1, true) then
                    References[#References + 1] = { Kind=Kind, Id=Id }
                end
            end
            Start = Last + 1
        end
    end
    return References
end

---@param Blocks VariantBlock[]
---@return VariantBlock[]
function VariantPruneResources(Blocks)
    local Resources, Pending, Required = {}, {}, {}
    for _, Block in ipairs(Blocks) do
        local Kind = VariantBlockKind(Block)
        if Kind == "ext_resource" or Kind == "sub_resource" then
            local Id = VariantAttributes(Block).id
            assert(Id, "Resource has no id: " .. Block.Header)
            Resources[(Kind == "ext_resource" and "ExtResource" or "SubResource") .. ":" .. Id] = Block
        else
            for _, Ref in ipairs(ResourceReferences(Block.Header .. "\n" .. Block.Body)) do Pending[#Pending + 1] = Ref end
        end
    end
    while #Pending > 0 do
        local Ref = table.remove(Pending)
        ---@cast Ref VariantReference
        local Key = Ref.Kind .. ":" .. Ref.Id
        if not Required[Key] then
            Required[Key] = true
            local Resource = Resources[Key]
            if Resource then
                for _, Child in ipairs(ResourceReferences(Resource.Header .. "\n" .. Resource.Body)) do Pending[#Pending + 1] = Child end
            end
        end
    end
    local Result = {}
    for _, Block in ipairs(Blocks) do
        local Kind = VariantBlockKind(Block)
        if Kind ~= "ext_resource" and Kind ~= "sub_resource"
            or Required[(Kind == "ext_resource" and "ExtResource" or "SubResource") .. ":" .. VariantAttributes(Block).id] then
            Result[#Result + 1] = Block
        end
    end
    return Result
end

---@param Builder VariantBuilder
---@param Text string
---@param Relative string
---@param Stage string
---@return string
function VariantAdaptScene(Builder, Text, Relative, Stage)
    local Blocks = VariantPruneResources(VariantParseBlocks(Text))
    for _, Block in ipairs(Blocks) do
        if VariantBlockKind(Block) == "sub_resource" and VariantAttributes(Block).type == "CompressedTexture2D" then
            local Cached = Block.Body:match('load_path%s*=%s*"res://%.godot/imported/([^"\n]+)"')
            local SourceName, ImportHash
            if Cached then SourceName, ImportHash = Cached:match("^(.*)%-(%x+)%.ctex$") end
            if SourceName and #ImportHash == 32 then
                local Id = VariantAttributes(Block).id
                local Resolved, Reason = VariantResolve(Builder, "res://assets/" .. SourceName)
                for _, Other in ipairs(Blocks) do
                    Other.Body = VariantReplace(Other.Body, 'SubResource("' .. Id .. '")',
                        Resolved and 'ExtResource("Recovered_' .. Id .. '")' or "null")
                end
                if Resolved then
                    Block.Header = '[ext_resource type="Texture2D" path=' .. sdk.text.json.encode(Resolved) .. ' id="Recovered_' .. Id .. '"]'
                    Block.Body = ""
                else
                    table.insert(Builder.Report.disabled, { scene=Relative, resource='load_path = "res://.godot/imported/' .. Cached .. '"', reason=Reason })
                end
            end
        end
    end
    Blocks = VariantPruneResources(Blocks)
    ---@type table<string, VariantResource>
    local Resources = {}
    for _, Block in ipairs(Blocks) do
        if VariantBlockKind(Block) == "ext_resource" then
            local Attributes = VariantAttributes(Block)
            Block.Header = Block.Header:gsub('%s+uid="[^"]+"', "")
            local Path = Attributes.path or ""
            if Path:sub(1, 12) == "res://logos/" then VariantAuxiliary(Builder, Path, Stage) end
            if Path:sub(1, 13) == "res://assets/" then
                local Resolved, Reason = VariantResolve(Builder, Path)
                Resources[Attributes.id] = { Resolved=Resolved, Reason=Reason, Original=Path }
                if Resolved then
                    VariantMaterialize(Builder, Resolved, Stage)
                    Block.Header = VariantReplace(Block.Header, 'path="' .. Path .. '"', 'path="' .. Resolved .. '"')
                end
            elseif Path:sub(1, 6) == "res://" and not sdk.is_file(VariantCheckedPath(Stage, Path:sub(7))) then
                assert(Attributes.type ~= "Script" and Attributes.type ~= "Shader" and Attributes.type ~= "PackedScene",
                    "Missing required resource in " .. Relative .. ": " .. Path)
                Resources[Attributes.id] = { Reason="missing_optional_resource", Original=Path }
            end
        end
    end
    ---@type table<string, VariantResource>
    local Missing = {}
    local GlbRoots, RemovedRoots = {}, {}
    for _, Block in ipairs(Blocks) do
        if VariantBlockKind(Block) == "node" then
            local Instance = Block.Header:match('instance=ExtResource%("([^"]+)"%)')
            local Resource = Instance and Resources[Instance]
            if Resource then
                local Path = VariantNodePath(Block)
                if not Resource.Resolved then Missing[Path] = Resource
                elseif VariantExtension(Resource.Original) == ".glb" or VariantExtension(Resource.Original) == ".gltf" then
                    GlbRoots[Path] = true
                    table.insert(Builder.SceneInstances, { scene=Relative, node=Path, asset=Resource.Resolved })
                    local Key, Status
                    if Builder.Collision then Key, Status = VariantCollisionJob(Builder, Resource.Resolved)
                    else Status = "collision_disabled" end
                    table.insert(Builder.Report.collisions, { scene=Relative, node=Path, asset=Resource.Resolved, uid=Key, status=Status })
                    if Key then table.insert(Builder.Attachments, { scene=Relative, node=Path, uid=Key }) end
                end
            end
        end
    end
    for _, Block in ipairs(Blocks) do
        if VariantBlockKind(Block) == "node" and VariantAttributes(Block).type == "StaticBody3D"
            and VariantDescends(VariantNodePath(Block), GlbRoots) then RemovedRoots[VariantNodePath(Block)] = true end
    end
    local DisabledRoots = {}
    for Path in pairs(RemovedRoots) do DisabledRoots[Path] = true end
    for Path in pairs(Missing) do DisabledRoots[Path] = true end
    local Output = {}
    for _, Block in ipairs(Blocks) do
        local Kind, Attributes, Keep = VariantBlockKind(Block), VariantAttributes(Block), true
        if Kind == "node" then
            local Path = VariantNodePath(Block)
            Keep = not VariantDescends(Path, RemovedRoots)
            for Root in pairs(Missing) do
                if Path ~= Root and VariantDescends(Path, { [Root]=true }) then Keep = false end
            end
            if Keep and Missing[Path] then
                local Resource = Missing[Path]
                local Header = '[node name=' .. sdk.text.json.encode(Attributes.name) .. ' type="Node3D"'
                if Attributes.parent then Header = Header .. " parent=" .. sdk.text.json.encode(Attributes.parent) end
                local Unique = Block.Header:match("%f[%w]unique_id=%d+")
                Block.Header = Header .. (Unique and " " .. Unique or "") .. "]"
                local Lines = {}
                for Line in Block.Body:gmatch("[^\n]+") do
                    local Property = Line:match("^(%w+)%s*=")
                    if Property == "transform" or Property == "position" or Property == "rotation" or Property == "scale" then Lines[#Lines + 1] = Line end
                end
                Block.Body = table.concat(Lines, "\n") .. '\nvisible = false\nprocess_mode = 4\nmetadata/variant_disabled = true\n'
                    .. "metadata/canonical_uid = " .. sdk.text.json.encode(GodotExtractAssetUid(Resource.Original) or "")
                    .. "\nmetadata/canonical_path = " .. sdk.text.json.encode(Resource.Original)
                    .. "\nmetadata/disabled_reason = " .. sdk.text.json.encode(Resource.Reason) .. "\n"
                table.insert(Builder.Report.disabled, { scene=Relative, node=Path, canonical_path=Resource.Original, reason=Resource.Reason })
            end
        elseif Kind == "editable" then Keep = not VariantDescends(Attributes.path, DisabledRoots)
        elseif Kind == "connection" then
            Keep = not VariantDescends(Attributes.from or "", DisabledRoots) and not VariantDescends(Attributes.to or "", DisabledRoots)
        elseif Kind == "ext_resource" and Resources[Attributes.id] and not Resources[Attributes.id].Resolved then Keep = false end
        if Keep then
            for _, Id in ipairs(GodotSortedKeys(Resources)) do
                local Resource = Resources[Id]
                local Reference = 'ExtResource("' .. Id .. '")'
                if not Resource.Resolved and Block.Body:find(Reference, 1, true) then
                    Block.Body = VariantReplace(Block.Body, Reference, "null")
                    table.insert(Builder.Report.disabled, { scene=Relative, resource=Resource.Original, reason=Resource.Reason })
                end
            end
            Output[#Output + 1] = Block
        end
    end
    Output = VariantPruneResources(Output)
    if Output[1] then Output[1].Header = Output[1].Header:gsub("%s+load_steps=%d+", "") end
    return VariantBlocksText(Output)
end

---@param Builder VariantBuilder
---@param Text string
---@param Relative string
---@param Stage string
---@return string
function VariantAdaptText(Builder, Text, Relative, Stage)
    local IsScript = Relative:match("%.gd$") ~= nil
    if IsScript then
        ---@param Function string
        ---@param Reference string
        ---@return string
        local function OptionalLoad(Function, Reference)
            if Function ~= "preload" and Function ~= "load" then return Function .. '(' .. sdk.text.json.encode(Reference) .. ')' end
            local Resolved, Reason = VariantResolve(Builder, Reference)
            if Resolved then VariantMaterialize(Builder, Resolved, Stage); return Function .. '(' .. sdk.text.json.encode(Resolved) .. ')' end
            table.insert(Builder.Report.disabled, { file=Relative, canonical_path=Reference, reason=Reason })
            return "null"
        end
        Text = Text:gsub('%f[%w_]([%w_]+)%(%s*"(res://assets/[^"\r\n]+)"%s*%)', OptionalLoad)
    end
    ---@param Path string
    ---@return string
    local function ReplaceReference(Path)
        if Path:sub(1, 12) == "res://logos/" then
            return VariantAuxiliary(Builder, Path, Stage) and ('"' .. Path .. '"') or (IsScript and '""' or "null")
        end
        if Path:sub(1, 13) ~= "res://assets/" or Path:sub(-1) == "/" or Path == "res://assets/normalized_map.json" then return '"' .. Path .. '"' end
        local Resolved, Reason = VariantResolve(Builder, Path)
        if Resolved then VariantMaterialize(Builder, Resolved, Stage); return sdk.text.json.encode(Resolved) end
        table.insert(Builder.Report.disabled, { file=Relative, canonical_path=Path, reason=Reason })
        return IsScript and '""' or "null"
    end
    return (Text:gsub('"(res://[^"\r\n]+)"', ReplaceReference))
end
