-- Live progress and console messages; no persistent diagnostics.
---@class AudioProgress
---@field Panel ConsoleProgress
---@field LastUpdate number
---@field LastMessage integer
---@field Sorting boolean
---@field Ok integer
---@field Skip integer
---@field Err integer

---@class AudioProgressModule
---@field New fun(): AudioProgress
---@field Update fun(Ui: AudioProgress, Phase: string, Current: integer, Total: integer, Force: boolean|nil): nil
---@field Warn fun(Path: string, Message: string): nil
---@field Finish fun(Ui: AudioProgress): nil

---@return AudioProgress
local function New()
    progress.script.start(5, "Organize audio V2")
    return {Panel=progress.console.new(1, "audio-v2", "Load V2 registry"), LastUpdate=0, LastMessage=0,
        Sorting=false, Ok=0, Skip=0, Err=0}
end

---@param Ui AudioProgress
---@param Phase string
---@param Current integer
---@param Total integer
---@param Force boolean|nil
---@return nil
local function UpdateProgress(Ui, Phase, Current, Total, Force)
    local Now = os.clock()
    if not Force and Current % 128 ~= 0 and Now - Ui.LastUpdate < 0.15 then return end
    Ui.Panel:SetTotal(math.max(Total, 1))
    Ui.Panel:SetLabel(Phase)
    if Ui.Sorting then Ui.Panel:SetStats(Current, Ui.Ok, Ui.Skip, Ui.Err)
    else Ui.Panel:SetStats(Current, Current, 0, 0) end
    Ui.LastUpdate = Now
    local Time = os.time()
    if Force or Time - Ui.LastMessage >= 2 then
        sdk.color_print("Cyan", string.format("Audio V2: %s (%d/%d)", Phase, Current, Total))
        Ui.LastMessage = Time
    end
end

---@param Path string
---@param Message string
---@return nil
local function Warn(Path, Message)
    sdk.color_print("Yellow", "Audio V2: " .. Path .. ": " .. Message)
end

---@param Ui AudioProgress
---@return nil
local function Finish(Ui)
    Ui.Panel:Complete()
    progress.script.finish()
end

return {New=New, Update=UpdateProgress, Warn=Warn, Finish=Finish}
