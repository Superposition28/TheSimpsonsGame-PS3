-- Organize generated audio using AudioMap V2. Direct calls default to a dry run.
---@class AudioOptions
---@field Root string
---@field Map string
---@field Execute boolean

---@type AudioPaths
local Paths = import("AudioPaths.lua")
local Require, Managed, Absolute, NoLinks = Paths.Require, Paths.Managed, Paths.Absolute, Paths.NoLinks
---@type AudioMapReader
local MapReader = import("AudioMap.lua")
---@type AudioRouting
local Routing = import("AudioRouting.lua")
---@type AudioFiles
local Files = import("AudioFiles.lua")
---@type AudioProgressModule
local Progress = import("AudioProgress.lua")

---@param Arguments string[]
---@return AudioOptions
local function Parse(Arguments)
    local Options = {Execute=false}
    ---@cast Options AudioOptions
    local Fields = {["--root"]="Root", ["--map"]="Map"}
    local Index, Mode = 1, nil
    while Index <= #Arguments do
        local Key = Arguments[Index]
        if Key == "--execute" or Key == "--dry-run" then
            Require(not Mode, "choose one execution mode")
            Mode, Options.Execute = Key, Key == "--execute"
        elseif Fields[Key] then
            Index = Index + 1
            Require(Arguments[Index] and not Options[Fields[Key]], "missing or repeated " .. Key)
            Options[Fields[Key]] = Arguments[Index]
        elseif Index == 1 and Key:sub(1,2) ~= "--" then Options.Root = Key
        else Require(false, "unknown option: " .. Key) end
        Index = Index + 1
    end
    Require(Options.Root, "missing generated audio root")
    Options.Root = Managed(Options.Root)
    local Renamed, Original = Options.Root .. "/A1_Audio", Options.Root .. "/audiostreams"
    Require(not (sdk.lexists(Renamed) and sdk.lexists(Original)), "select A1_Audio or audiostreams explicitly when both exist")
    if sdk.lexists(Renamed) then Options.Root = Managed(Renamed)
    elseif sdk.lexists(Original) then Options.Root = Managed(Original) end
    Require(sdk.is_dir(Options.Root), "audio root is not a directory")
    Options.Map = Absolute(Options.Map or Game_Root .. "/reversing/docs/PS3_GAME/USRDIR/A1_Audio/AudioMap.yaml")
    NoLinks(Options.Map)
    return Options
end

---@param Arguments string[]
---@return nil
local function Run(Arguments)
    local Options = Parse(Arguments)
    local Lock = Managed(Options.Root .. ".v2-execute.lock")
    Require(not sdk.lexists(Lock), "root is locked; confirm the previous process stopped before removing " .. Lock)
    local Temporary = Lock .. "." .. tostring(os.time()) .. "." .. tostring(math.random(1,1000000000))
    Require(sdk.write_file(Temporary, Options.Root .. "\n"), "cannot create lock")
    if not sdk.rename_file(Temporary, Lock, false) then sdk.remove_file(Temporary); Require(false, "root is locked") end
    local Ui = Progress.New()
    ---@type AudioCounts
    local Counts = {Planned=0, Moved=0, AlreadySorted=0, RemovedDirectories=0}
    ---@return nil
    local function Work()
        Progress.Update(Ui, "Load V2 registry", 0, 1, true)
        local Map = MapReader.Read(Options.Map)
        local Lookup = Routing.Compile(Map)
        local Inventory = Files.NewInventory()
        progress.script.step("Stage English and global banks")
        Progress.Update(Ui, "Stage English and global banks", 0, 1, true)
        Files.Stage(Options, Lookup, Inventory, Ui)
        progress.script.step("Find files")
        Progress.Update(Ui, "Find files", 0, 1, true)
        Files.Scan(Options.Root, "", Inventory, Ui)
        Progress.Update(Ui, "Find files: " .. #Inventory.Files .. " found", Inventory.Scanned, Inventory.Discovered, true)
        progress.script.step("Sort streams")
        Progress.Update(Ui, "Sort streams", 0, #Inventory.Files, true)
        Files.Sort(Options, Lookup, Inventory, Counts, Ui)
        progress.script.step("Remove empty folders")
        if Options.Execute then Files.Cleanup(Options, Inventory, Counts, Ui) end
        progress.script.step("Finished")
    end
    local Ok, Failure = pcall(Work)
    Progress.Finish(Ui)
    Require(sdk.remove_file(Lock), "cannot release execution lock")
    if not Ok then Require(false, tostring(Failure)) end
    if Options.Execute then
        sdk.color_print("Green", string.format("Audio V2: %d moved, %d already sorted, %d skipped, %d failed; %d empty folders removed.",
            Counts.Moved, Counts.AlreadySorted, Ui.Skip, Ui.Err, Counts.RemovedDirectories))
    else
        sdk.color_print("Green", string.format("Audio V2 dry run: %d files would move, %d already sorted, %d skipped, %d failed.",
            Counts.Planned, Counts.AlreadySorted, Ui.Skip, Ui.Err))
    end
end

return Run(argv or {})
