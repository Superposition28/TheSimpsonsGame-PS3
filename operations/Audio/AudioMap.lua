-- Read and validate the maintained V2 registry before reorganizing files.
---@class AudioPatternNamespace
---@field Scope string
---@field Pattern string
---@field Route string
---@field Banks string[]

---@class AudioMapReader
---@field Read fun(Path: string): AudioMap

---@type AudioPaths
local Paths = import("AudioPaths.lua")
local Require, Component, Relative = Paths.Require, Paths.Component, Paths.Relative
local Parent = Paths.Parent
---@type AudioRouting
local Routing = import("AudioRouting.lua")
local Resolve, SpeakerFolders, TypeFolders = Routing.Resolve, Routing.SpeakerFolders, Routing.TypeFolders

---@param Pattern string
---@param Name string
---@return boolean
local function MatchesPattern(Pattern, Name)
    Component(Pattern)
    Require(Pattern:lower():sub(-8) == ".exa.snu" and not Pattern:find("[%[%]{}]"), "invalid filename pattern")
    Require(not Pattern:gsub("#######", ""):find("#", 1, true)
        and not Pattern:find("##############", 1, true), "invalid hex placeholder")
    local Escaped = Pattern:lower():gsub("([%^%$%(%)%%%.%[%]%*%+%-%?])", "%%%1")
    Escaped = Escaped:gsub("#######", "[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]")
    return Name:lower():match("^" .. Escaped .. "$") ~= nil
end

---@param Value any
---@param Required string[]
---@param Optional string[]|nil
---@return nil
local function Fields(Value, Required, Optional)
    Require(type(Value) == "table", "expected a mapping")
    local Allowed = {}
    for _, Key in ipairs(Required) do
        Require(Value[Key] ~= nil, "missing map field " .. Key)
        Allowed[Key] = true
    end
    for _, Key in ipairs(Optional or {}) do Allowed[Key] = true end
    for Key in pairs(Value) do Require(Allowed[Key], "unexpected map field " .. tostring(Key)) end
end

---@param Value any
---@return string
local function Identifier(Value)
    Component(Value)
    Require(Value:match("^[a-z0-9_]+$") and not Value:find("__", 1, true)
        and Value:sub(1,1) ~= "_" and Value:sub(-1) ~= "_", "invalid stable ID: " .. Value)
    return Value
end

---@param Value any
---@return nil
local function Text(Value)
    Require(type(Value) == "string" and Value ~= "", "expected nonempty text")
end

---@param Values any
---@param Ids boolean
---@return nil
local function UniqueStrings(Values, Ids)
    Require(type(Values) == "table", "expected an array")
    local Seen, Count = {}, 0
    for Key, Value in pairs(Values) do
        Require(type(Key) == "number" and Key >= 1 and Key % 1 == 0, "expected an array index")
        if Ids then Identifier(Value) else Text(Value) end
        Require(not Seen[Value], "duplicate array value " .. Value)
        Seen[Value], Count = true, Count + 1
    end
    Require(Count == #Values, "sparse array")
end

---@param Left string
---@param Right string
---@return boolean
local function PatternsOverlap(Left, Right)
    Left, Right = Left:lower(), Right:lower()
    if #Left ~= #Right then return false end
    for Index = 1, #Left do
        local A, B = Left:sub(Index,Index), Right:sub(Index,Index)
        if A ~= B and not (A == "#" and B:match("[0-9a-f]"))
            and not (B == "#" and A:match("[0-9a-f]")) then return false end
    end
    return true
end

---@param Path string
---@return AudioMap
local function ReadMap(Path)
    local Map = sdk.text.yaml.read_file(Path)
    ---@cast Map AudioMap
    Fields(Map, {"schema_version", "locations", "speakers", "assets"}, {"provenance", "legacy"})
    Map.schema_version = tonumber(Map.schema_version)
    Require(Map.schema_version == 2, "V2 schema required")
    Fields(Map.locations, {"hubs", "levels"})
    local Folders, Assets = {}, {}
    ---@type AudioPatternNamespace[]
    local Patterns = {}
    for _, Kind in ipairs({"hubs", "levels"}) do
        Require(type(Map.locations[Kind]) == "table", "missing location registry")
        for Key, Location in pairs(Map.locations[Kind]) do
            Identifier(Key)
            Fields(Location, {"folder", "display_name"}, {"original_directory", "code", "aliases"})
            Component(Location.folder)
            Text(Location.display_name)
            Require(not Folders[Location.folder:lower()], "duplicate location folder")
            Folders[Location.folder:lower()] = true
            if Location.aliases then UniqueStrings(Location.aliases, false) end
        end
    end
    Require(type(Map.speakers) == "table", "missing speakers")
    for Key, Speaker in pairs(Map.speakers) do
        Identifier(Key)
        Fields(Speaker, {"display_name", "speaker_type", "groups", "review_status"}, {"character_id", "variant"})
        Text(Speaker.display_name)
        Require(SpeakerFolders[Speaker.speaker_type], "unknown speaker type")
        Require(Speaker.review_status == "inherited" or Speaker.review_status == "provisional"
            or Speaker.review_status == "verified", "unknown speaker review status")
        UniqueStrings(Speaker.groups, true)
        if Speaker.character_id then Identifier(Speaker.character_id) end
        if Speaker.variant then Identifier(Speaker.variant); Identifier(Speaker.character_id) end
    end
    Require(type(Map.assets) == "table" and #Map.assets > 0, "empty assets")
    for Index, Asset in pairs(Map.assets) do
        ---@cast Asset AudioAsset
        Require(type(Index) == "number" and Index >= 1 and Index <= #Map.assets and Index % 1 == 0, "assets must be an array")
        Fields(Asset, {"id", "audio_type", "source", "usage"}, {"speaker_id", "category", "area", "notes", "nickname", "legacy"})
        Identifier(Asset.id)
        Require(not Assets[Asset.id], "duplicate asset ID")
        Assets[Asset.id] = true
        Require(TypeFolders[Asset.audio_type] or Asset.audio_type == "dialogue", "unknown audio type")
        if Asset.audio_type == "dialogue" then
            Require(Map.speakers[Asset.speaker_id], "invalid speaker reference")
        else Require(Asset.speaker_id == nil, "only dialogue can reference a speaker") end
        for _, Key in ipairs({"category", "area"}) do if Asset[Key] then Identifier(Asset[Key]) end end
        Fields(Asset.source, {"scope", "original_directory", "file_patterns"}, {"legacy_directories"})
        Require(Asset.source.scope == "localized" or Asset.source.scope == "global", "unknown source scope")
        Component(Asset.source.original_directory)
        UniqueStrings(Asset.source.file_patterns, false)
        Require(#Asset.source.file_patterns > 0, "empty filename patterns")
        local Banks = {Asset.source.original_directory:lower()}
        if Asset.source.legacy_directories then
            UniqueStrings(Asset.source.legacy_directories, false)
            for _, Alias in ipairs(Asset.source.legacy_directories) do Banks[#Banks+1] = Relative(Alias):lower() end
        end
        -- YamlDotNet preserves scalar lexemes; normalize only the typed fields.
        Fields(Asset.usage, {}, {"world_hub", "hubs", "levels", "unresolved"})
        if Asset.usage.world_hub == "true" then Asset.usage.world_hub = true
        elseif Asset.usage.world_hub == "false" then Asset.usage.world_hub = false end
        Require(Asset.usage.world_hub == nil or type(Asset.usage.world_hub) == "boolean", "invalid world_hub")
        for _, Kind in ipairs({"hubs", "levels"}) do
            if Asset.usage[Kind] then
                UniqueStrings(Asset.usage[Kind], true)
                for _, Key in ipairs(Asset.usage[Kind]) do Require(Map.locations[Kind][Key], "unknown location " .. Key) end
            end
        end
        Require(#(Asset.usage.hubs or {}) == 0 or Asset.usage.world_hub == true, "named hubs require world_hub: true")
        if Asset.usage.unresolved then UniqueStrings(Asset.usage.unresolved, false) end
        for _, Pattern in ipairs(Asset.source.file_patterns) do
            MatchesPattern(Pattern, "validation.exa.snu")
            local Sample = Pattern:gsub("#######", "0000000")
            local Route = Parent(Resolve(Map, Asset, Sample, "EN")):lower()
            for _, Previous in ipairs(Patterns) do
                if Asset.source.scope == Previous.Scope and PatternsOverlap(Pattern, Previous.Pattern) then
                    local SharedBank = false
                    for _, A in ipairs(Banks) do
                        for _, B in ipairs(Previous.Banks) do
                            if A == B or A:sub(1,#B+1) == B .. "/" or B:sub(1,#A+1) == A .. "/" then SharedBank = true end
                        end
                    end
                    Require(not SharedBank and Route ~= Previous.Route, "overlapping filename patterns: " .. Asset.id)
                end
            end
            Patterns[#Patterns+1] = {Scope=Asset.source.scope, Pattern=Pattern, Route=Route, Banks=Banks}
        end
    end
    return Map
end

return {Read=ReadMap}
