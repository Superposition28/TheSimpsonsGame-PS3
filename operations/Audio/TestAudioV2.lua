-- Tiny adversarial/recovery fixtures. Only tools/audio/prepare_audio_fixtures.py
-- creates these disposable inputs. Original Source files are never written here.
---@class AudioV2FixtureInvocation
---@field root string
---@field map string
---@field plan string
---@field state string
---@field report string

---@class AudioV2Fixture: AudioV2FixtureInvocation
---@field source string
---@field destination string

---@class AudioV2FixtureContract
---@field asset AudioV2Asset
---@field filename string
---@field language string
---@field destination string

---@class AudioV2FixtureData
---@field cases table<string, AudioV2Fixture>
---@field contracts AudioV2FixtureContract[]

---@type AudioV2Runtime
local Runtime = import("AudioV2.lua")
local Data = sdk.text.json.decode(sdk.read_file(Game_Root .. "/GameFiles/testAudio-fixtures/cases.json"))
---@cast Data AudioV2FixtureData
local Count = 0

---@param Case AudioV2FixtureInvocation
---@param Execute boolean
---@param Extra string[]|nil
---@param Expected string|nil
---@return AudioV2Report|nil
local function Run(Case, Execute, Extra, Expected)
    local Arguments = {Execute and "--execute" or "--dry-run", "--root", Case.root,
        "--map", Case.map, "--plan", Case.plan, "--state", Case.state, "--report", Case.report}
    for _, Argument in ipairs(Extra or {}) do Arguments[#Arguments+1] = Argument end
    local Ok, Failure = pcall(Runtime.Run, Arguments)
    if Expected then
        assert(not Ok and tostring(Failure):find(Expected, 1, true), "expected rejection " .. Expected .. "; got " .. tostring(Failure))
    else assert(Ok, tostring(Failure)) end
    Count = Count + 1
    if not Expected then return sdk.text.json.decode(sdk.read_file(Case.report)) end
    return nil
end

local Recovery = Data.cases.recovery
local Source, Destination = Recovery.root .. "/" .. Recovery.source, Recovery.root .. "/" .. Recovery.destination
local Hash = sdk.sha1_file(Source)
local Dry = Run(Recovery, false)
assert(Dry.complete and Dry.moved == 0 and sdk.sha1_file(Source) == Hash and not sdk.lexists(Destination), "dry run changed audio")
Run(Recovery, true, {"--test-stop-after-copy", "1"}, "TEST interruption after verified copy")
assert(sdk.sha1_file(Source) == Hash and sdk.sha1_file(Destination) == Hash, "interrupted copy lost data")
local Resumed = Run(Recovery, true)
assert(Resumed.complete and Resumed.moved == 1 and Resumed.resumed == 1 and not sdk.lexists(Source), "resume failed")
local Repeat = Run(Recovery, true)
assert(Repeat.complete and Repeat.moved == 0 and Repeat.already_sorted == 1, "repeat moved files")

local Partial = Data.cases.partial
Run(Partial, true, {"--test-stop-after-copy", "1"}, "TEST interruption after verified copy")
assert(sdk.write_file(Partial.root .. "/" .. Partial.destination, "truncated"))
local Repaired = Run(Partial, true)
assert(Repaired.complete and Repaired.moved == 1 and Repaired.resumed == 1 and Repaired.partial_repaired == 1, "partial copy recovery failed")
assert(sdk.sha1_file(Partial.root .. "/" .. Partial.destination) == Hash, "partial copy was not restored")

local Collision = Data.cases.collision
assert(sdk.write_file(Collision.root .. "/" .. Collision.destination, "occupied destination"))
Run(Collision, true, nil, "destination exists without a matching journal intent")
assert(sdk.sha1_file(Collision.root .. "/" .. Collision.source) == Hash, "collision changed source")
assert(sdk.read_file(Collision.root .. "/" .. Collision.destination) == "occupied destination", "collision overwrote target")

local Changed = Data.cases.changed
assert(sdk.write_file(Changed.root .. "/" .. Changed.source, "corrupted audio"))
Run(Changed, true, nil, "file hash mismatch")
assert(not sdk.lexists(Changed.root .. "/" .. Changed.destination), "changed source was moved")

local Extra = Data.cases.extra
assert(sdk.write_file(Extra.root .. "/added.txt", "unexpected"))
Run(Extra, true, nil, "file was added since planning")

local ParentFile = Data.cases.parent
assert(sdk.write_file(ParentFile.root .. "/EN", "blocked directory"))
Run(ParentFile, true, nil, "file occupies destination parent")

local Traversal = Data.cases.traversal
local BadPlan = sdk.text.json.decode(sdk.read_file(Traversal.plan))
BadPlan.manifest.files[1].source = "../Source/file.exa.snu"
assert(sdk.write_file(Traversal.plan, sdk.text.json.encode(BadPlan)))
Run(Traversal, true, nil, "invalid path component")

local WrongMap = Data.cases.map
local WrongPlan = sdk.text.json.decode(sdk.read_file(WrongMap.plan))
WrongPlan.map_sha1 = string.rep("0", 40)
assert(sdk.write_file(WrongMap.plan, sdk.text.json.encode(WrongPlan)))
Run(WrongMap, true, nil, "map differs from the validated YAML")

local Locked = Data.cases.lock
assert(sdk.write_file(Locked.root .. ".v2-execute.lock", "fixture lock"))
Run(Locked, true, nil, "root is locked")
assert(sdk.remove_file(Locked.root .. ".v2-execute.lock"))

local ReadOnly = {root=Game_Root .. "/Source/PS3/EU/1/PS3_GAME/USRDIR/audiostreams",
    map=Recovery.map, plan=Recovery.plan, state=Recovery.state, report=Recovery.report}
Run(ReadOnly, true, nil, "restricted to GameFiles")

local Bound = sdk.text.json.decode(sdk.read_file(Recovery.plan))
Bound.test_new_plan = true
assert(sdk.write_file(Recovery.plan, sdk.text.json.encode(Bound)))
Run(Recovery, true, nil, "journal does not match plan")
assert(sdk.sha1_file(Destination) == Hash, "plan mismatch changed sorted output")

local Map = sdk.text.yaml.read_file(Recovery.map)
for _, Case in ipairs(Data.contracts) do
    assert(Runtime.Resolve(Map, Case.asset, Case.filename, Case.language) == Case.destination, "extra resolver contract mismatch")
    Count = Count + 1
end

-- Exercise the production entry contract without a prepared Python plan.
local Automatic = Game_Root .. "/GameFiles/testAudio-fixtures/automatic"
local AutoRoot = Automatic .. "/A1_Audio"
assert(sdk.ensure_dir(AutoRoot .. "/iv_xxx_0"))
assert(sdk.write_file(AutoRoot .. "/iv_xxx_0/d_dciv_xxx_123abcd.exa.snu", "synthetic audio"))
assert(sdk.write_file(AutoRoot .. "/test.mus", "unmanaged fixture"))

---@param Dataset string
---@return AudioV2Report
local function AutomaticReport(Dataset)
    local Root = sdk.absolute_path(Dataset .. "/A1_Audio"):gsub("\\", "/"):gsub("^//%?/", "")
    local Audit = Game_Root .. "/GameFiles/config/audio-v2/" .. sdk.md5(Root:lower())
    local Plan = sdk.text.json.decode(sdk.read_file(Audit .. "/plan.json"))
    assert(Plan.runtime_plan_version == 2 and #Plan.manifest.files == 2, "automatic plan is incomplete")
    return sdk.text.json.decode(sdk.read_file(Audit .. "/report.json"))
end

Runtime.Run({Automatic, "--dry-run"})
assert(AutomaticReport(Automatic).moved == 0 and sdk.is_file(AutoRoot .. "/iv_xxx_0/d_dciv_xxx_123abcd.exa.snu"), "automatic dry run moved input")
Count = Count + 1
local AutoOk, AutoError = pcall(Runtime.Run, {Automatic, "--execute", "--test-stop-after-copy", "1"})
assert(not AutoOk and tostring(AutoError):find("TEST interruption", 1, true), "automatic interruption failed")
Runtime.Run({Automatic, "--execute"})
local AutoRecovered = AutomaticReport(Automatic)
assert(AutoRecovered.complete and AutoRecovered.moved == 1 and AutoRecovered.resumed == 1, "automatic resume failed")
Count = Count + 1
Runtime.Run({Automatic, "--execute"})
assert(AutomaticReport(Automatic).already_sorted == 1 and AutomaticReport(Automatic).moved == 0, "automatic repeat moved input")
Count = Count + 1
assert(sdk.rename_file(Automatic, Automatic .. "-renamed", false), "fixture dataset rename failed")
Runtime.Run({Automatic .. "-renamed", "--execute"})
assert(AutomaticReport(Automatic .. "-renamed").already_sorted == 1, "dataset success rename broke V2 rerun")
Count = Count + 1

local Unmapped = Game_Root .. "/GameFiles/testAudio-fixtures/automatic-unmapped"
assert(sdk.ensure_dir(Unmapped))
assert(sdk.write_file(Unmapped .. "/unknown.exa.snu", "preserve this input"))
local UnmappedOk, UnmappedError = pcall(Runtime.Run, {Unmapped, "--execute"})
assert(not UnmappedOk and tostring(UnmappedError):find("unmapped audio", 1, true), "automatic planner accepted unmapped audio")
assert(sdk.read_file(Unmapped .. "/unknown.exa.snu") == "preserve this input", "unmapped input changed")
Count = Count + 1

assert(sdk.write_file(Game_Root .. "/GameFiles/testAudio-fixtures/results.json", sdk.text.json.encode({passed=Count})))
print(string.format("Audio V2 native fixtures: %d checks passed", Count))
