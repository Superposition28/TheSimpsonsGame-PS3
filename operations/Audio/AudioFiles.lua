-- Stage banks, scan once, move streams without overwriting, and clean empty folders.
---@class AudioInventory
---@field Files string[]
---@field Directories table<string, boolean>
---@field CheckedDirectories table<string, boolean>
---@field Scanned integer
---@field Discovered integer

---@class AudioCounts
---@field Planned integer
---@field Moved integer
---@field AlreadySorted integer
---@field RemovedDirectories integer

---@class AudioFiles
---@field NewInventory fun(): AudioInventory
---@field Stage fun(Options: AudioOptions, Lookup: AudioLookup, Inventory: AudioInventory, Ui: AudioProgress): nil
---@field Scan fun(Root: string, Subpath: string, Inventory: AudioInventory, Ui: AudioProgress): nil
---@field Sort fun(Options: AudioOptions, Lookup: AudioLookup, Inventory: AudioInventory, Counts: AudioCounts, Ui: AudioProgress): nil
---@field Cleanup fun(Options: AudioOptions, Inventory: AudioInventory, Counts: AudioCounts, Ui: AudioProgress): nil

---@type AudioPaths
local Paths = import("AudioPaths.lua")
local Require, Component = Paths.Require, Paths.Component
local Parent, NoLinks, Languages = Paths.Parent, Paths.NoLinks, Paths.Languages
---@type AudioRouting
local Routing = import("AudioRouting.lua")
local Destination = Routing.Destination
---@type AudioProgressModule
local Progress = import("AudioProgress.lua")
local UpdateProgress = Progress.Update

---@return AudioInventory
local function NewInventory()
    return {Files={}, Directories={}, CheckedDirectories={}, Scanned=0, Discovered=0}
end

---@param Inventory AudioInventory
---@param Path string
---@return nil
local function EnsureDirectory(Inventory, Path)
    if Inventory.CheckedDirectories[Path:lower()] then return end
    NoLinks(Path)
    Require(not sdk.lexists(Path) or sdk.is_dir(Path), "file blocks destination directory: " .. Path)
    Require(sdk.ensure_dir(Path), "cannot create directory: " .. Path)
    Inventory.CheckedDirectories[Path:lower()] = true
    Inventory.Directories[Path] = true
end

---@param SourcePath string
---@param TargetPath string
---@param Inventory AudioInventory
---@return boolean
local function MergeBank(SourcePath, TargetPath, Inventory)
    if sdk.is_symlink(SourcePath) or (sdk.lexists(TargetPath) and sdk.is_symlink(TargetPath)) then
        Progress.Warn(SourcePath, "linked bank left in place")
        return false
    end
    EnsureDirectory(Inventory, Parent(TargetPath))
    if not sdk.lexists(TargetPath) then
        Require(sdk.rename_file(SourcePath, TargetPath, false), "cannot stage bank: " .. SourcePath)
        return true
    end
    if not sdk.is_dir(TargetPath) then
        Progress.Warn(SourcePath, "file blocks staged bank: " .. TargetPath)
        return false
    end
    EnsureDirectory(Inventory, TargetPath)
    for _, Name in ipairs(sdk.list_dir(SourcePath)) do
        Component(Name)
        local From, To = SourcePath .. "/" .. Name, TargetPath .. "/" .. Name
        if sdk.is_symlink(From) or (sdk.lexists(To) and sdk.is_symlink(To)) then Progress.Warn(From, "linked entry left in place")
        elseif sdk.is_dir(From) then MergeBank(From, To, Inventory)
        elseif sdk.lexists(To) then Progress.Warn(From, "staging destination exists: " .. To)
        elseif not sdk.rename_file(From, To, false) then Progress.Warn(From, "cannot stage file") end
    end
    -- sdk.remove_dir is recursive: call it only after an explicit empty check.
    NoLinks(SourcePath)
    if #sdk.list_dir(SourcePath) == 0 then Require(sdk.remove_dir(SourcePath), "cannot remove empty bank") end
    return not sdk.lexists(SourcePath)
end

---@param Options AudioOptions
---@param Lookup AudioLookup
---@param Inventory AudioInventory
---@param Ui AudioProgress
---@return nil
local function Stage(Options, Lookup, Inventory, Ui)
    local Names = sdk.list_dir(Options.Root)
    for Index, Name in ipairs(Names) do
        Component(Name)
        local Full, Upper = Options.Root .. "/" .. Name, Name:upper()
        if not Languages[Upper] and Upper ~= "GLOBAL" and Upper ~= "MUSIC" then
            if sdk.is_symlink(Full) then Progress.Warn(Name, "linked root entry left in place")
            elseif sdk.is_dir(Full) then
                local Scope = Lookup.Scopes[Name:lower()] == "global" and "global" or "localized"
                Lookup.Scopes[Name:lower()] = Scope
                local Prefix = Scope == "global" and "Global" or "EN"
                if Options.Execute then
                    ---@return boolean
                    local function MoveBank()
                        return MergeBank(Full, Options.Root .. "/" .. Prefix .. "/" .. Name, Inventory)
                    end
                    local Ok, Failure = pcall(MoveBank)
                    if not Ok then Progress.Warn(Name, tostring(Failure)) end
                end
            end
        end
        UpdateProgress(Ui, "Stage English and global banks", Index, #Names)
    end
    UpdateProgress(Ui, "Stage English and global banks", #Names, #Names, true)
end

---@param Root string
---@param Subpath string
---@param Inventory AudioInventory
---@param Ui AudioProgress
---@return nil
local function Scan(Root, Subpath, Inventory, Ui)
    local Current = Subpath == "" and Root or Root .. "/" .. Subpath
    Inventory.Directories[Current] = true
    Inventory.CheckedDirectories[Current:lower()] = true
    local Names = sdk.list_dir(Current)
    Inventory.Discovered = Inventory.Discovered + #Names
    for _, Name in ipairs(Names) do
        Component(Name)
        Inventory.Scanned = Inventory.Scanned + 1
        local Rel = Subpath == "" and Name or Subpath .. "/" .. Name
        local Full = Root .. "/" .. Rel
        if sdk.is_symlink(Full) then Progress.Warn(Rel, "linked entry left in place")
        else
            local Attributes = sdk.attributes(Full)
            if Attributes and Attributes.mode == "directory" then Scan(Root, Rel, Inventory, Ui)
            elseif Attributes and Attributes.mode == "file" then
                Inventory.Files[#Inventory.Files+1] = Rel
            else Progress.Warn(Rel, "cannot inspect audio entry") end
        end
        UpdateProgress(Ui, "Find files: " .. #Inventory.Files .. " found", Inventory.Scanned, Inventory.Discovered)
    end
end

---@param Options AudioOptions
---@param Lookup AudioLookup
---@param Inventory AudioInventory
---@param Counts AudioCounts
---@param Ui AudioProgress
---@return nil
local function Sort(Options, Lookup, Inventory, Counts, Ui)
    local Reservations = {}
    Ui.Sorting, Ui.Ok, Ui.Skip, Ui.Err = true, 0, 0, 0
    for Index, Rel in ipairs(Inventory.Files) do
        if Rel:lower():sub(-8) ~= ".exa.snu" then
            Ui.Skip = Ui.Skip + 1
        else
            local Target, Reason = Destination(Lookup, Rel)
            if not Target then
                Progress.Warn(Rel, tostring(Reason) .. ": no unique V2 mapping; file retained")
                Ui.Skip = Ui.Skip + 1
            elseif Target:lower() == Rel:lower() then
                Counts.AlreadySorted = Counts.AlreadySorted + 1
                Ui.Ok = Ui.Ok + 1
            elseif Reservations[Target:lower()] or sdk.lexists(Options.Root .. "/" .. Target) then
                Progress.Warn(Rel, "destination exists; file retained: " .. Target)
                Ui.Skip = Ui.Skip + 1
            else
                Reservations[Target:lower()] = true
                Counts.Planned = Counts.Planned + 1
                if Options.Execute then
                    ---@return nil
                    local function MoveFile()
                        local From, To = Options.Root .. "/" .. Rel, Options.Root .. "/" .. Target
                        EnsureDirectory(Inventory, Parent(To))
                        Require(not sdk.is_symlink(From), "linked source file")
                        -- Both paths stay on the same, non-linked audio tree.
                        -- Renaming retains the original bytes and is resumable by
                        -- matching the new location on the next invocation.
                        Require(sdk.rename_file(From, To, false), "move failed; input retained")
                        Counts.Moved = Counts.Moved + 1
                    end
                    local Ok, Failure = pcall(MoveFile)
                    if not Ok then
                        Progress.Warn(Rel, tostring(Failure))
                        Ui.Err = Ui.Err + 1
                    else Ui.Ok = Ui.Ok + 1 end
                else Ui.Ok = Ui.Ok + 1 end
            end
        end
        UpdateProgress(Ui, "Sort streams: " .. Rel, Index, #Inventory.Files)
    end
    UpdateProgress(Ui, "Sort streams", #Inventory.Files, #Inventory.Files, true)
    Ui.Sorting = false
end

---@param Options AudioOptions
---@param Inventory AudioInventory
---@param Counts AudioCounts
---@param Ui AudioProgress
---@return nil
local function Cleanup(Options, Inventory, Counts, Ui)
    local Paths = {}
    for Path in pairs(Inventory.Directories) do Paths[#Paths+1] = Path end
    ---@param Left string
    ---@param Right string
    ---@return boolean
    local function DeepestFirst(Left, Right) return #Left > #Right end
    table.sort(Paths, DeepestFirst)
    for Index, Path in ipairs(Paths) do
        local Rel = Path:sub(#Options.Root+2)
        if Rel ~= "" and not Languages[Rel:upper()] and Rel:upper() ~= "GLOBAL" and Rel:upper() ~= "MUSIC" then
            Require(Path:lower():sub(1,#Options.Root+1) == Options.Root:lower() .. "/", "cleanup leaves audio root")
            NoLinks(Path)
            if sdk.is_dir(Path) and #sdk.list_dir(Path) == 0 then
                if sdk.remove_dir(Path) then Counts.RemovedDirectories = Counts.RemovedDirectories + 1
                else Progress.Warn(Rel, "cannot remove empty directory") end
            end
        end
        UpdateProgress(Ui, "Remove empty folders", Index, #Paths)
    end
    UpdateProgress(Ui, "Remove empty folders", #Paths, #Paths, true)
end

return {NewInventory=NewInventory, Stage=Stage, Scan=Scan, Sort=Sort, Cleanup=Cleanup}
