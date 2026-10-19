-- Resolve V2 asset routes and compile filename lookups once per run.
---@class AudioUsage
---@field world_hub boolean|nil
---@field hubs string[]|nil
---@field levels string[]|nil
---@field unresolved string[]|nil

---@class AudioSpeaker
---@field display_name string
---@field speaker_type string
---@field groups string[]
---@field review_status string
---@field character_id string|nil
---@field variant string|nil

---@class AudioLocation
---@field folder string
---@field display_name string
---@field original_directory string|nil
---@field code string|nil
---@field aliases string[]|nil

---@class AudioSource
---@field scope string
---@field original_directory string
---@field file_patterns string[]
---@field legacy_directories string[]|nil

---@class AudioAsset
---@field id string
---@field audio_type string
---@field speaker_id string|nil
---@field source AudioSource
---@field usage AudioUsage
---@field category string|nil
---@field area string|nil
---@field notes string|nil
---@field nickname string|nil
---@field legacy table<string, any>|nil

---@class AudioMap
---@field schema_version integer|nil
---@field speakers table<string, AudioSpeaker>
---@field locations table<string, table<string, AudioLocation>>
---@field assets AudioAsset[]
---@field provenance table<string, any>|nil
---@field legacy table<string, any>|nil

---@class AudioRule
---@field Asset AudioAsset
---@field Pattern string
---@field Prefix string
---@field Banks string[]
---@field Outputs table<string, string>

---@class AudioLookup
---@field Prefixes table<integer, table<string, AudioRule[]>>
---@field Scopes table<string, string>

---@class AudioRouting
---@field Resolve fun(AudioMap: AudioMap, AudioAsset: AudioAsset, Name: string, Language: string): string
---@field Compile fun(AudioMap: AudioMap): AudioLookup
---@field Destination fun(Lookup: AudioLookup, Path: string): (string|nil, string|nil)
---@field SpeakerFolders table<string, string>
---@field TypeFolders table<string, string>

---@type AudioPaths
local Paths = import("AudioPaths.lua")
local Require, Component, Relative = Paths.Require, Paths.Component, Paths.Relative
local Parent, Filename, Languages = Paths.Parent, Paths.Filename, Paths.Languages
local SpeakerFolders = {named_character="Characters", unnamed_character="UnnamedCharacters",
    unidentified_voice="UnidentifiedVoices", announcer="Announcers", narrator="Narrators",
    crowd="Crowds", unknown="UnknownSpeakers"}
local TypeFolders = {cutscene="Cutscenes", ambience="Ambience", sound_effect="SoundEffects",
    music="Music", unknown="Unmapped"}

---@param Map AudioMap
---@param Asset AudioAsset
---@return string
local function LocationFolder(Map, Asset)
    local Count, Folder = 0, nil
    for _, Kind in ipairs({"hubs", "levels"}) do
        for _, Key in ipairs(Asset.usage[Kind] or {}) do
            local Location = Map.locations[Kind][Key]
            Require(Location, "unknown location " .. Key)
            Count, Folder = Count + 1, Component(Location.folder)
        end
    end
    if Count == 1 and #(Asset.usage.unresolved or {}) == 0
        and not (Asset.usage.world_hub == true and #(Asset.usage.hubs or {}) == 0) then
        return assert(Folder)
    end
    return Count > 1 and "MultipleLocations" or "UnresolvedLocation"
end

---@param Map AudioMap
---@param Asset AudioAsset
---@param Name string
---@param Language string
---@return string
local function Resolve(Map, Asset, Name, Language)
    Component(Name)
    local Prefix = "Global"
    if Asset.source.scope == "localized" then
        Require(Languages[Language], "unknown language " .. tostring(Language))
        Prefix = Language
    else
        Require(Asset.source.scope == "global", "unknown source scope")
    end
    local Parts = {Prefix}
    if Asset.audio_type == "dialogue" then
        local Speaker = Map.speakers[Asset.speaker_id]
        Require(Speaker and SpeakerFolders[Speaker.speaker_type], "invalid speaker reference")
        Parts[#Parts+1] = "Dialogue"
        Parts[#Parts+1] = SpeakerFolders[Speaker.speaker_type]
        if Speaker.variant ~= nil then
            Parts[#Parts+1] = Component(Speaker.character_id)
            Parts[#Parts+1] = Component(Speaker.variant)
        else Parts[#Parts+1] = Component(Asset.speaker_id) end
    else
        Require(TypeFolders[Asset.audio_type], "unknown audio type")
        Parts[#Parts+1] = TypeFolders[Asset.audio_type]
        if Asset.audio_type == "unknown" then Parts[#Parts+1] = Component(Asset.id)
        else
            local Location = LocationFolder(Map, Asset)
            Parts[#Parts+1] = Location
            if Location == "UnresolvedLocation" or Location == "MultipleLocations" then Parts[#Parts+1] = Component(Asset.id) end
            if Asset.category then Parts[#Parts+1] = Component(Asset.category) end
            if Asset.area then Parts[#Parts+1] = Component(Asset.area) end
        end
    end
    Parts[#Parts+1] = Name
    return Relative(table.concat(Parts, "/"))
end

---@param Map AudioMap
---@return AudioLookup
local function Compile(Map)
    local Lookup = {Prefixes={}, Scopes={}}
    ---@cast Lookup AudioLookup
    for _, Asset in ipairs(Map.assets) do
        local Banks = {Asset.source.original_directory:lower()}
        for _, Alias in ipairs(Asset.source.legacy_directories or {}) do Banks[#Banks+1] = Alias:lower() end
        for _, Bank in ipairs(Banks) do
            local Top = Bank:match("^[^/]+")
            local Previous = Lookup.Scopes[Top]
            Lookup.Scopes[Top] = Previous and Previous ~= Asset.source.scope and "mixed" or Asset.source.scope
        end
        for _, Pattern in ipairs(Asset.source.file_patterns) do
            local Prefix = Pattern:lower():match("^[^#]+") or ""
            local Escaped = Pattern:lower():gsub("([%^%$%(%)%%%.%[%]%*%+%-%?])", "%%%1")
            Escaped = Escaped:gsub("#######", "[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]")
            local Outputs = {}
            local Sample = Pattern:gsub("#######", "0000000")
            for Language in pairs(Languages) do Outputs[Language] = Parent(Resolve(Map, Asset, Sample, Language)) end
            local Rule = {Asset=Asset, Pattern="^" .. Escaped .. "$", Prefix=Prefix, Banks=Banks, Outputs=Outputs}
            ---@cast Rule AudioRule
            local Length = #Prefix
            Lookup.Prefixes[Length] = Lookup.Prefixes[Length] or {}
            Lookup.Prefixes[Length][Prefix] = Lookup.Prefixes[Length][Prefix] or {}
            local Bucket = Lookup.Prefixes[Length][Prefix]
            Bucket[#Bucket+1] = Rule
        end
    end
    return Lookup
end

---@param Lookup AudioLookup
---@param Path string
---@return string|nil destination, string|nil reason
local function Destination(Lookup, Path)
    local Top, Name = Path:match("^[^/]+"), Filename(Path)
    local Language, Scope, Local = "EN", Lookup.Scopes[Top:lower()], Path:lower()
    if Languages[Top:upper()] or Top:upper() == "GLOBAL" then
        Language = Languages[Top:upper()] and Top:upper() or "EN"
        Scope = Top:upper() == "GLOBAL" and "global" or "localized"
        Local = Path:sub(#Top+2):lower()
    end
    local Found, Best, Ambiguous = nil, -1, false
    ---@cast Found string|nil
    for Length, Prefixes in pairs(Lookup.Prefixes) do
        for _, Rule in ipairs(Prefixes[Name:lower():sub(1,Length)] or {}) do
            if (not Scope or Scope == Rule.Asset.source.scope) and Name:lower():match(Rule.Pattern) then
                local Result = Rule.Outputs[Language] .. "/" .. Name
                local Score = Path:lower() == Result:lower() and 3 or 0
                for _, Bank in ipairs(Rule.Banks) do
                    if Local:sub(1,#Bank+1) == Bank .. "/" then Score = math.max(Score, 2) end
                end
                -- Bank/canonical matches win; a unique exact filename pattern
                -- also recovers files kept in an unrecorded, older folder name.
                if Score > Best then Found, Best, Ambiguous = Result, Score, false
                elseif Score == Best and Result ~= Found then Ambiguous = true end
            end
        end
    end
    if Ambiguous then return nil, "ambiguous" end
    if Found then return Found, nil end
    return nil, "unmatched"
end

return {Resolve=Resolve, Compile=Compile, Destination=Destination,
    SpeakerFolders=SpeakerFolders, TypeFolders=TypeFolders}
