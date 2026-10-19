-- Organize generated audio using the maintained AudioMap V2 registry.
-- Operation 4 passes --execute; direct script calls default to a dry run.

-- AudioMap V2 runtime. Creates/reuses a hashed plan and preflights the complete
-- current inventory before moving files. Python tools provide independent checks.
-- Files are copied without overwrite, verified, then removed from the old path.

---@class Usage
---@field world_hub boolean|nil
---@field hubs string[]|nil
---@field levels string[]|nil
---@field unresolved string[]|nil

---@class Speaker
---@field display_name string
---@field speaker_type string
---@field groups string[]
---@field review_status string
---@field character_id string|nil
---@field variant string|nil

---@class Location
---@field folder string
---@field display_name string
---@field original_directory string|nil
---@field code string|nil
---@field aliases string[]|nil

---@class Source
---@field scope string
---@field original_directory string
---@field file_patterns string[]
---@field legacy_directories string[]|nil

---@class Asset
---@field id string
---@field audio_type string
---@field speaker_id string|nil
---@field source Source
---@field usage Usage
---@field category string|nil
---@field area string|nil
---@field notes string|nil
---@field nickname string|nil
---@field legacy table<string, any>|nil

---@class Map
---@field schema_version integer|nil
---@field speakers table<string, Speaker>
---@field locations table<string, table<string, Location>>
---@field assets Asset[]
---@field provenance table<string, any>|nil
---@field legacy table<string, any>|nil

---@class Record
---@field source string
---@field destination string|nil
---@field asset_id string|nil
---@field status string
---@field size integer
---@field sha1 string
---@field sha256 string|nil

---@class Plan
---@field runtime_plan_version integer
---@field map_path string
---@field map_sha1 string
---@field manifest Manifest
---@field route_cases RouteCase[]

---@class Manifest
---@field root string
---@field layout string
---@field hashed boolean
---@field files Record[]
---@field summary ManifestSummary

---@class ManifestSummary
---@field preflight_passed boolean
---@field all_audio_matched boolean
---@field files integer

---@class RouteCase
---@field asset_id string
---@field filename string
---@field language string
---@field destination string

---@class Event
---@field plan_sha1 string
---@field index integer
---@field phase string
---@field source string
---@field destination string
---@field sha1 string

---@class Options
---@field Root string
---@field Map string
---@field Plan string
---@field State string
---@field Report string
---@field Execute boolean
---@field StopAfterCopy integer|nil

---@class Job
---@field Record Record
---@field Index integer
---@field Mode string

---@class PatternNamespace
---@field Scope string
---@field Pattern string
---@field Route string
---@field Banks string[]

---@class Report
---@field mode string
---@field plan_sha1 string
---@field files integer
---@field planned integer
---@field moved integer
---@field already_sorted integer
---@field resumed integer
---@field unmanaged integer
---@field partial_repaired integer
---@field route_cases integer
---@field complete boolean
---@field error string|nil

---@class Attributes
---@field size integer|nil
---@field mode integer|nil

local Languages = {EN=true, ES=true, FR=true, IT=true}
local SpeakerFolders = {named_character="Characters", unnamed_character="UnnamedCharacters",
    unidentified_voice="UnidentifiedVoices", announcer="Announcers", narrator="Narrators",
    crowd="Crowds", unknown="UnknownSpeakers"}
local TypeFolders = {cutscene="Cutscenes", ambience="Ambience", sound_effect="SoundEffects",
    music="Music", unknown="Unmapped"}

---@param Condition any
---@param Message string
---@return nil
local function Require(Condition, Message)
    -- The engine replaces error() with a logging function. assert() still throws.
    assert(Condition, "Audio V2: " .. Message)
end

---@param Value string
---@return string
local function Component(Value)
    Require(type(Value) == "string" and Value ~= "" and Value ~= "." and Value ~= "..", "invalid path component")
    Require(not Value:find('[\\/:*?"<>|%c]') and not Value:find("[. ]$"), "unsafe component: " .. Value)
    local Stem = Value:upper():match("^[^.]+") or ""
    Require(not ({CON=true, PRN=true, AUX=true, NUL=true})[Stem]
        and not Stem:match("^COM[1-9]$") and not Stem:match("^LPT[1-9]$"), "reserved component: " .. Value)
    for _, Suffix in ipairs({"¹", "²", "³"}) do
        Require(Stem ~= "COM" .. Suffix and Stem ~= "LPT" .. Suffix, "reserved component: " .. Value)
    end
    return Value
end

---@param Value string
---@return string
local function Relative(Value)
    Require(type(Value) == "string" and Value ~= "" and not Value:find("\\", 1, true)
        and Value:sub(1,1) ~= "/" and Value:sub(-1) ~= "/" and not Value:find("//", 1, true), "invalid relative path")
    for Part in Value:gmatch("[^/]+") do Component(Part) end
    return Value
end

---@param Path string
---@return string
local function Absolute(Path)
    local Result = sdk.absolute_path(Path):gsub("\\", "/"):gsub("^//%?/", ""):gsub("/+$", "")
    return Result
end

---@param Path string
---@return nil
local function NoLinks(Path)
    Path = Absolute(Path)
    local Base = Absolute(Game_Root)
    Require(Path:lower() == Base:lower() or Path:lower():sub(1,#Base+1) == Base:lower() .. "/", "path leaves module root")
    while Path ~= "" do
        Require(not (sdk.lexists(Path) and sdk.is_symlink(Path)), "linked path is forbidden: " .. Path)
        if Path:lower() == Base:lower() then break end
        local Parent = Path:match("^(.*)/[^/]+$")
        if not Parent or Parent == Path then break end
        Path = Parent
    end
end

---@param Path string
---@return string
local function Managed(Path)
    Path = Absolute(Path)
    local Base = Absolute(Game_Root) .. "/GameFiles/"
    Require(Path:lower():sub(1, #Base) == Base:lower(), "runtime writes are restricted to GameFiles: " .. Path)
    NoLinks(Path)
    return Path
end

---@param Path string
---@return string
local function Parent(Path)
    return assert(Path:match("^(.*)/[^/]+$"))
end

---@param Path string
---@return string
local function Filename(Path)
    return assert(Path:match("([^/]+)$"))
end

---@param Path string
---@return table
local function ReadJson(Path)
    local Text = sdk.read_file(Path)
    Require(type(Text) == "string", "cannot read " .. Path)
    local Value = sdk.text.json.decode(Text)
    Require(type(Value) == "table", "invalid JSON: " .. Path)
    return Value
end

---@param Path string
---@param Value table
---@return nil
local function WriteJson(Path, Value)
    Managed(Path)
    Require(sdk.write_file(Path, sdk.text.json.encode(Value, {indent=true})), "cannot write " .. Path)
end

---@param Path string
---@param Record Record
---@param DeepLinks boolean|nil
---@return boolean
local function ContentsMatch(Path, Record, DeepLinks)
    if DeepLinks ~= false then NoLinks(Path)
    else Require(not sdk.is_symlink(Path), "linked file is forbidden: " .. Path) end
    local Attributes = sdk.attributes(Path)
    ---@cast Attributes Attributes
    return Attributes ~= nil and Attributes.mode == "file" and Attributes.size == Record.size and sdk.sha1_file(Path) == Record.sha1
end

---@param Path string
---@param Record Record
---@param DeepLinks boolean|nil
---@return nil
local function Verify(Path, Record, DeepLinks)
    Require(ContentsMatch(Path, Record, DeepLinks), "file hash mismatch or size/type changed: " .. Path)
end

---@param Map Map
---@param Asset Asset
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

---@param Map Map
---@param Asset Asset
---@param Name string
---@param Language string
---@return string
function Resolve(Map, Asset, Name, Language)
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

---@param Map Map
---@param Asset Asset
---@param Path string
---@param Layout string
---@return boolean
local function MatchesSource(Map, Asset, Path, Layout)
    local Name = Filename(Path)
    local Found = false
    for _, Pattern in ipairs(Asset.source.file_patterns) do
        if MatchesPattern(Pattern, Name) then Found = true end
    end
    if not Found then return false end
    local Top = Path:match("^[^/]+")
    local Language, Local = "EN", Path
    if Languages[Top:upper()] or Top:upper() == "GLOBAL" then
        if (Top:upper() == "GLOBAL") ~= (Asset.source.scope == "global") then return false end
        Language, Local = Top:upper(), Path:sub(#Top+2)
    end
    if (Layout == "auto" or Layout == "v2") and Path:lower() == Resolve(Map, Asset, Name, Language):lower() then return true end
    if Layout == "auto" or Layout == "raw" or Layout == "legacy_sorted" then
        local Bank = Component(Asset.source.original_directory):lower() .. "/"
        if Local:lower():sub(1,#Bank) == Bank then return true end
    end
    if Layout == "auto" or Layout == "legacy_sorted" then
        for _, Alias in ipairs(Asset.source.legacy_directories or {}) do
            Alias = Relative(Alias):lower() .. "/"
            if Local:lower():sub(1,#Alias) == Alias then return true end
        end
    end
    return false
end

---@param Root string
---@param Subpath string
---@param Files table<string, string>
---@param Folders table<string, boolean>
---@return nil
local function Walk(Root, Subpath, Files, Folders)
    local Current = Subpath == "" and Root or Root .. "/" .. Subpath
    NoLinks(Current)
    Require(sdk.is_dir(Current), "cannot list directory " .. Current)
    for _, Name in ipairs(sdk.list_dir(Current)) do
        Component(Name)
        local Rel = Subpath == "" and Name or Subpath .. "/" .. Name
        local Full = Root .. "/" .. Rel
        Require(not sdk.is_symlink(Full), "linked audio entry " .. Full)
        Require(not Files[Rel:lower()] and not Folders[Rel:lower()], "case collision " .. Rel)
        if sdk.is_dir(Full) then
            Folders[Rel:lower()] = true
            Walk(Root, Rel, Files, Folders)
        else
            Require(sdk.is_file(Full), "not a regular file " .. Full)
            Files[Rel:lower()] = Rel
        end
    end
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
---@return Map
local function ReadMap(Path)
    local Map = sdk.text.yaml.read_file(Path)
    ---@cast Map Map
    Fields(Map, {"schema_version", "locations", "speakers", "assets"}, {"provenance", "legacy"})
    Map.schema_version = tonumber(Map.schema_version)
    Require(Map.schema_version == 2, "V2 schema required")
    Fields(Map.locations, {"hubs", "levels"})
    local Folders, Assets = {}, {}
    ---@type PatternNamespace[]
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
        ---@cast Asset Asset
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

---@param Options Options
---@param Map Map
---@return Plan
local function PreparePlan(Options, Map)
    local Files, Folders, Names, Records, Targets, Index = {}, {}, {}, {}, {}, {}
    Walk(Options.Root, "", Files, Folders)
    -- Index literal prefixes once, avoiding a scan of all patterns for every file.
    for _, Asset in ipairs(Map.assets) do
        for _, Pattern in ipairs(Asset.source.file_patterns) do
            local Prefix = Pattern:lower():match("^[^#]+")
            local Length = #Prefix
            Index[Length] = Index[Length] or {}
            Index[Length][Prefix] = Index[Length][Prefix] or {}
            Index[Length][Prefix][Asset.id] = Asset
        end
    end
    for _, Name in pairs(Files) do Names[#Names+1] = Name end
    table.sort(Names)
    local AudioCount = 0
    for Number, Path in ipairs(Names) do
        local Full = Options.Root .. "/" .. Path
        local Attributes = sdk.attributes(Full)
        ---@cast Attributes Attributes
        Require(Attributes and Attributes.mode == "file", "inventory entry changed")
        local Record = {source=Path, size=Attributes.size, sha1=sdk.sha1_file(Full), status="unmanaged"}
        ---@cast Record Record
        Require(type(Record.sha1) == "string" and #Record.sha1 == 40, "cannot fingerprint " .. Path)
        local Name = Filename(Path)
        if Name:lower():sub(-8) == ".exa.snu" then
            local Found, Candidates = nil, {}
            ---@cast Candidates table<string, Asset>
            ---@cast Found Asset
            for Length, Prefixes in pairs(Index) do
                for Key, Asset in pairs(Prefixes[Name:lower():sub(1,Length)] or {}) do Candidates[Key] = Asset end
            end
            for _, Asset in pairs(Candidates) do
                if MatchesSource(Map, Asset, Path, "auto") then
                    Require(not Found, "ambiguous source mapping: " .. Path)
                    Found = Asset
                end
            end
            Require(Found, "unmapped audio: " .. Path)
            local Language = Path:match("^[^/]+"):upper()
            if not Languages[Language] then Language = "EN" end
            Record.asset_id = Found.id
            Record.destination = Resolve(Map, Found, Name, Language)
            local Key = Record.destination:lower()
            Require(not Targets[Key], "destination collision: " .. Record.destination)
            Require(not Folders[Key], "directory occupies destination filename")
            local Ancestor = Record.destination
            while Ancestor:find("/", 1, true) do
                Ancestor = Parent(Ancestor)
                Require(not Files[Ancestor:lower()], "file occupies destination parent")
            end
            Require(not Files[Key] or Key == Path:lower(), "destination already exists: " .. Record.destination)
            Targets[Key] = true
            Record.status = Key == Path:lower() and "already_sorted" or "planned"
            AudioCount = AudioCount + 1
        end
        Records[#Records+1] = Record
        if Number % 2000 == 0 then print(string.format("Audio V2 inventory: %d/%d files", Number, #Names)) end
    end
    Require(AudioCount > 0, "empty audio inventory")
    return {runtime_plan_version=2, map_path=Options.Map, map_sha1=sdk.sha1_file(Options.Map), route_cases={},
        manifest={root=Options.Root, layout="auto", hashed=true, files=Records,
            summary={preflight_passed=true, all_audio_matched=true, files=#Records}}}
end

---@param Options Options
---@param Index integer
---@param Phase string
---@return string
local function EventPath(Options, Index, Phase)
    return Options.State .. "/events/" .. string.format("%08d-%s.json", Index, Phase)
end

---@param Options Options
---@param Index integer
---@param Phase string
---@param PlanHash string
---@return boolean
local function HasEvent(Options, Index, Phase, PlanHash)
    local Path = EventPath(Options, Index, Phase)
    if not sdk.lexists(Path) then return false end
    -- The events directory is checked at entry. Reading existing records cannot
    -- mutate Source; all writes/removals still check their entire ancestor chain.
    Require(not sdk.is_symlink(Path), "linked journal record")
    local Event = ReadJson(Path)
    ---@cast Event Event
    Require(Event.plan_sha1 == PlanHash and Event.index == Index and Event.phase == Phase, "journal does not match plan: " .. Path)
    return true
end

---@param Options Options
---@param Job Job
---@param Phase string
---@param PlanHash string
---@return nil
local function SaveEvent(Options, Job, Phase, PlanHash)
    if HasEvent(Options, Job.Index, Phase, PlanHash) then return end
    local Path = EventPath(Options, Job.Index, Phase)
    local Temporary = Path .. ".tmp"
    -- A partial temporary record from an interrupted write is never a committed event.
    if sdk.lexists(Temporary) then
        Managed(Temporary)
        Require(sdk.remove_file(Temporary), "cannot remove partial journal record")
    end
    WriteJson(Temporary, {plan_sha1=PlanHash, index=Job.Index, phase=Phase,
        source=Job.Record.source, destination=Job.Record.destination, sha1=Job.Record.sha1})
    Require(sdk.rename_file(Temporary, Path, false), "cannot commit journal event")
    Require(HasEvent(Options, Job.Index, Phase, PlanHash), "journal verification failed")
end

---@param Options Options
---@param Plan Plan
---@param Map Map
---@param PlanHash string
---@return Job[]
local function Preflight(Options, Plan, Map, PlanHash)
    Require((Plan.runtime_plan_version == 1 or Plan.runtime_plan_version == 2) and Plan.manifest.hashed == true, "expected a hashed runtime plan")
    Require(Plan.manifest.summary.preflight_passed == true and Plan.manifest.summary.all_audio_matched == true, "plan preflight did not pass")
    Require(Absolute(Plan.manifest.root):lower() == Options.Root:lower(), "plan is for another audio root")
    Require(Absolute(Plan.map_path):lower() == Options.Map:lower() and sdk.sha1_file(Options.Map) == Plan.map_sha1, "map differs from the validated YAML")
    Require(Map.schema_version == 2, "V2 schema required")
    Require(Plan.manifest.layout == "auto" or Plan.manifest.layout == "raw"
        or Plan.manifest.layout == "legacy_sorted" or Plan.manifest.layout == "v2", "invalid input layout")
    local Assets = {}
    for _, Asset in ipairs(Map.assets) do
        ---@cast Asset Asset
        Require(not Assets[Asset.id], "duplicate asset ID")
        Assets[Asset.id] = Asset
    end
    for _, Case in ipairs(Plan.route_cases) do
        Require(Assets[Case.asset_id], "missing parity asset")
        local Actual = Resolve(Map, Assets[Case.asset_id], Case.filename, Case.language)
        Require(Actual == Case.destination, "Python/Lua destination disagreement: " .. Case.asset_id .. "; expected " .. Case.destination .. "; got " .. Actual)
    end
    local Files, Folders, Consumed, Targets, Sources, Jobs = {}, {}, {}, {}, {}, {}
    Walk(Options.Root, "", Files, Folders)
    for Index, Record in ipairs(Plan.manifest.files) do
        ---@cast Record Record
        Relative(Record.source)
        Require(not Sources[Record.source:lower()], "duplicate plan source")
        Sources[Record.source:lower()] = true
        Require(type(Record.size) == "number" and Record.size >= 0 and Record.size % 1 == 0
            and type(Record.sha1) == "string" and #Record.sha1 == 40 and Record.sha1:match("^[0-9a-f]+$")
            and (Plan.runtime_plan_version == 2 or (type(Record.sha256) == "string" and #Record.sha256 == 64)), "missing size/fingerprints")
        local SourceExists = Files[Record.source:lower()] ~= nil
        local Job = {Record=Record, Index=Index, Mode="unmanaged"}
        if Record.status == "unmanaged" then
            Require(Record.source:lower():sub(-8) ~= ".exa.snu" and SourceExists and not Record.destination, "invalid unmanaged file")
            Verify(Options.Root .. "/" .. Record.source, Record, false)
            Consumed[Record.source:lower()] = true
        else
            Require(Record.status == "planned" or Record.status == "already_sorted", "unroutable plan record")
            Relative(Record.destination)
            Require(Filename(Record.source) == Filename(Record.destination), "original filename must be preserved")
            local Asset = Assets[Record.asset_id]
            Require(Asset and MatchesSource(Map, Asset, Record.source, Plan.manifest.layout), "source bank/pattern mismatch: " .. Record.source)
            local Language = Record.source:match("^[^/]+"):upper()
            if not Languages[Language] then Language = "EN" end
            Require(Resolve(Map, Asset, Filename(Record.source), Language) == Record.destination, "route differs from execution plan")
            Require(not Targets[Record.destination:lower()], "destination collision")
            Targets[Record.destination:lower()] = true
            Require(not Folders[Record.destination:lower()], "directory occupies destination filename")
            local Ancestor = Record.destination
            while Ancestor:find("/", 1, true) do
                Ancestor = Parent(Ancestor)
                Require(not Files[Ancestor:lower()], "file occupies destination parent")
            end
            local TargetExists = Files[Record.destination:lower()] ~= nil
            local Same = Record.source:lower() == Record.destination:lower()
            local Intent = HasEvent(Options, Index, "intent", PlanHash)
            local Verified = HasEvent(Options, Index, "verified", PlanHash)
            Require(not Verified or TargetExists, "previously verified destination is missing")
            Require(not (Verified and SourceExists and not Same), "source reappeared after completed move")
            if Same then
                Require(SourceExists, "already-sorted file is missing")
                Job.Mode = "already_sorted"
            elseif TargetExists then
                Require(Intent, "destination exists without a matching journal intent: " .. Record.destination)
                Job.Mode = SourceExists and "copied" or (Verified and "already_sorted" or "resumed")
            else
                Require(SourceExists, "both source and destination are missing")
                Job.Mode = "planned"
            end
            if SourceExists then Verify(Options.Root .. "/" .. Record.source, Record, false); Consumed[Record.source:lower()] = true end
            if TargetExists and not Same then
                local ValidTarget = ContentsMatch(Options.Root .. "/" .. Record.destination, Record, false)
                if not ValidTarget then
                    Require(Intent and SourceExists and not Verified, "verified destination changed: " .. Record.destination)
                    Job.Mode = "partial_copy"
                end
                Consumed[Record.destination:lower()] = true
            end
        end
        Jobs[#Jobs+1] = Job
        if Index % 2000 == 0 then print(string.format("Audio V2 preflight: %d/%d files", Index, #Plan.manifest.files)) end
    end
    Require(#Jobs > 0 and #Jobs == Plan.manifest.summary.files, "incomplete plan inventory")
    for Key, Path in pairs(Files) do Require(Consumed[Key], "file was added since planning: " .. Path) end
    return Jobs
end

---@param Arguments string[]
---@return Options
local function Parse(Arguments)
    local Options = {Execute=false}
    local Fields = {["--root"]="Root", ["--map"]="Map", ["--plan"]="Plan", ["--state"]="State", ["--report"]="Report"}
    local Index, Mode = 1, nil
    while Index <= #Arguments do
        local Key = Arguments[Index]
        if Key == "--execute" or Key == "--dry-run" then
            Require(Mode == nil, "choose one execution mode")
            Mode, Options.Execute = Key, Key == "--execute"
        elseif Fields[Key] then
            Index = Index + 1
            Require(Arguments[Index] and not Options[Fields[Key]], "missing or repeated option " .. Key)
            Options[Fields[Key]] = Arguments[Index]
        elseif Key == "--test-stop-after-copy" then
            Index = Index + 1
            Options.StopAfterCopy = tonumber(Arguments[Index])
            Require(Options.StopAfterCopy and Options.StopAfterCopy > 0 and Options.StopAfterCopy % 1 == 0, "invalid interruption count")
        elseif Index == 1 and Key:sub(1,2) ~= "--" then Options.Root = Key
        else Require(false, "unknown argument " .. tostring(Key)) end
        Index = Index + 1
    end
    Require(Options.Root, "missing audio root")
    Options.Root = Managed(Options.Root)
    local Renamed, Original = Options.Root .. "/A1_Audio", Options.Root .. "/audiostreams"
    Require(not (sdk.lexists(Renamed) and sdk.lexists(Original)), "both A1_Audio and audiostreams exist; select the audio folder explicitly")
    if sdk.lexists(Renamed) then Options.Root = Managed(Renamed)
    elseif sdk.lexists(Original) then Options.Root = Managed(Original) end
    Require(sdk.is_dir(Options.Root), "audio root is not a directory")
    Options.Map = Options.Map or Game_Root .. "/reversing/docs/PS3_GAME/USRDIR/A1_Audio/AudioMap.yaml"
    local Audit = Absolute(Game_Root) .. "/GameFiles/config/audio-v2/" .. sdk.md5(Options.Root:lower())
    Options.Plan = Options.Plan or Audit .. "/plan.json"
    Options.State = Options.State or Audit .. "/journal"
    Options.Report = Options.Report or Audit .. "/report.json"
    Options.Root, Options.State, Options.Report = Managed(Options.Root), Managed(Options.State), Managed(Options.Report)
    Options.Map, Options.Plan = Absolute(Options.Map), Managed(Options.Plan)
    NoLinks(Options.Map)
    for _, Path in ipairs({Options.State, Options.Report, Options.Plan}) do
        Require(Path:lower():sub(1,#Options.Root+1) ~= Options.Root:lower() .. "/" and Path:lower() ~= Options.Root:lower(), "audit paths must be outside the audio tree")
    end
    Require(Options.Plan:lower() ~= Options.Report:lower() and Options.Map:lower() ~= Options.Report:lower(), "report may not overwrite input")
    Require(Options.Report:lower():sub(1,#Options.State+1) ~= Options.State:lower() .. "/"
        and Options.Report:lower() ~= Options.State:lower(), "report may not overwrite journal state")
    Require(not Options.StopAfterCopy or Options.Execute, "interruption injection requires --execute")
    return Options
end

---@param Options Options
---@param Jobs Job[]
---@param Report Report
---@return nil
local function Execute(Options, Jobs, Report)
    local Copies = 0
    for _, Job in ipairs(Jobs) do
        ---@cast Job Job
        local Record = Job.Record
        local Source, Destination = Options.Root .. "/" .. Record.source, Options.Root .. "/" .. (Record.destination or Record.source)
        if Job.Mode == "planned" or Job.Mode == "copied" or Job.Mode == "partial_copy" then
            local Recovered = Job.Mode ~= "planned"
            Verify(Source, Record, false)
            if Job.Mode == "partial_copy" then
                -- The matching intent reserved an absent destination before its
                -- interrupted copy. Never discard it without a verified original.
                Verify(Source, Record)
                NoLinks(Destination)
                SaveEvent(Options, Job, "retry", Report.plan_sha1)
                Require(sdk.remove_file(Destination), "cannot discard owned partial copy")
                Require(not sdk.lexists(Destination), "partial copy removal failed")
                Job.Mode = "planned"
                Report.partial_repaired = Report.partial_repaired + 1
            end
            if Job.Mode == "planned" then
                NoLinks(Destination)
                Require(not sdk.lexists(Destination), "destination appeared after preflight")
                SaveEvent(Options, Job, "intent", Report.plan_sha1)
                Require(sdk.ensure_dir(Parent(Destination)), "cannot create destination parent")
                NoLinks(Destination)
                Require(sdk.copy_file(Source, Destination, false), "copy failed; source preserved")
                Verify(Destination, Record)
                Copies = Copies + 1
                if Options.StopAfterCopy and Copies == Options.StopAfterCopy then Require(false, "TEST interruption after verified copy") end
            else Verify(Destination, Record) end
            -- The destination was just verified. Recheck the source, including
            -- every ancestor, immediately before deleting the original copy.
            Verify(Source, Record)
            Require(sdk.remove_file(Source), "cannot remove verified source copy")
            Require(not sdk.lexists(Source), "source removal did not complete")
            SaveEvent(Options, Job, "verified", Report.plan_sha1)
            Report.moved = Report.moved + 1
            if Recovered then Report.resumed = Report.resumed + 1 end
        elseif Job.Mode == "resumed" then
            Verify(Destination, Record)
            SaveEvent(Options, Job, "verified", Report.plan_sha1)
        end
        if Job.Index % 1000 == 0 then print(string.format("Audio V2 execute: %d/%d files", Job.Index, #Jobs)) end
    end
    -- All expected files, hashes and extras are checked again after execution.
    local Expected, Actual, Folders = {}, {}, {}
    Walk(Options.Root, "", Actual, Folders)
    for _, Job in ipairs(Jobs) do
        local Record = Job.Record
        local Rel = Record.destination or Record.source
        Expected[Rel:lower()] = true
        Verify(Options.Root .. "/" .. Rel, Record, false)
    end
    for Key, Path in pairs(Actual) do Require(Expected[Key], "unexpected remaining file: " .. Path) end
end


---@param Arguments string[]
---@return nil
function Run(Arguments)
    local Options = Parse(Arguments)
    local MapHash = sdk.sha1_file(Options.Map)
    local Map = ReadMap(Options.Map)
    -- One lock per audio root, even if callers choose different audit directories.
    local Lock = Managed(Options.Root .. ".v2-execute.lock")
    Require(Options.Report:lower() ~= Lock:lower() and Options.Plan:lower() ~= Lock:lower(), "audit input/output conflicts with lock")
    local Temporary = Lock .. "." .. tostring(os.time()) .. "." .. tostring(math.random(1,1000000000))
    WriteJson(Temporary, {root=Options.Root, map_sha1=MapHash})
    if not sdk.rename_file(Temporary, Lock, false) then
        sdk.remove_file(Temporary)
        Require(false, "root is locked; confirm the previous process stopped before removing " .. Lock)
    end
    local Report = {mode=Options.Execute and "execute" or "dry_run", plan_sha1="",
        files=0, planned=0, moved=0, already_sorted=0, resumed=0, unmanaged=0, partial_repaired=0,
        route_cases=0, complete=false}
    ---@cast Report Report
    ---@return nil
    local function Work()
        Require(sdk.ensure_dir(Options.State), "cannot create audit state directory")
        NoLinks(Options.State)
        NoLinks(Options.State .. "/events")
        if not sdk.lexists(Options.Plan) then
            print("Audio V2: preparing " .. Options.Plan)
            local NewPlan = PreparePlan(Options, Map)
            Require(sdk.sha1_file(Options.Map) == MapHash, "YAML changed during inventory")
            local Pending = Options.Plan .. ".tmp"
            if sdk.lexists(Pending) then Managed(Pending); Require(sdk.remove_file(Pending), "cannot discard incomplete plan") end
            WriteJson(Pending, NewPlan)
            Require(sdk.rename_file(Pending, Options.Plan, false), "cannot commit execution plan")
        end
        local Plan = ReadJson(Options.Plan)
        ---@cast Plan Plan
        Require(type(Plan.route_cases) == "table" and type(Plan.manifest) == "table"
            and type(Plan.manifest.files) == "table" and type(Plan.manifest.summary) == "table", "invalid runtime plan")
        local PlanHash = sdk.sha1_file(Options.Plan)
        Require(type(PlanHash) == "string", "cannot hash plan")
        Require(MapHash == Plan.map_sha1, "map differs from the validated YAML")
        Report.plan_sha1, Report.route_cases = PlanHash, #Plan.route_cases
        local Jobs = Preflight(Options, Plan, Map, PlanHash)
        for _, Job in ipairs(Jobs) do
            Report.files = Report.files + 1
            if Job.Mode == "unmanaged" then Report.unmanaged = Report.unmanaged + 1
            elseif Job.Mode == "already_sorted" then Report.already_sorted = Report.already_sorted + 1
            elseif Job.Mode == "resumed" then Report.resumed = Report.resumed + 1
            else Report.planned = Report.planned + 1 end
        end
        WriteJson(Options.Report, Report)
        Require(sdk.sha1_file(Options.Plan) == PlanHash and sdk.sha1_file(Options.Map) == Plan.map_sha1, "plan or YAML changed during preflight")
        if Options.Execute then Execute(Options, Jobs, Report) end
        Report.complete = true
        WriteJson(Options.Report, Report)
    end
    local Ok, Failure = pcall(Work)
    if not Ok then Report.error = tostring(Failure) end
    -- Release the lock on handled failures; an abrupt process termination leaves it
    -- for explicit operator recovery, never guessed stale while another run is active.
    Require(sdk.remove_file(Lock), "cannot release execution lock")
    WriteJson(Options.Report, Report)
    Require(Ok, tostring(Failure))
    print(string.format("Audio V2 %s complete: %d files, %d moved, %d already sorted, %d recovered, %d unmanaged; %d parity cases.",
        Report.mode, Report.files, Report.moved, Report.already_sorted, Report.resumed, Report.unmanaged, Report.route_cases))
    print("Audio V2 audit: " .. Options.Report)
end

Run(argv or {})
