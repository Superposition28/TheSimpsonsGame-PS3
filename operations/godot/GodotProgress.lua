-- Shared progress for the Godot operations. Importing defines globals only.
-- ScriptProgress tracks stages; ConsoleProgress shows the current counted work.

---@class GodotActivityProgress
---@field Label string
---@field Current integer
---@field Total integer
---@field Skipped integer
---@field Detail string

---@class GodotOperationProgress
---@field Script ScriptProgress
---@field Panel ConsoleProgress
---@field Activity GodotActivityProgress|nil
---@field LastUpdate number
---@field LastMessage number

---@type GodotOperationProgress|nil
GodotCurrentProgress = _G.GodotCurrentProgress

---@param Force boolean|nil
---@return nil
local function Render(Force)
    local Ui = GodotCurrentProgress
    if not Ui or not Ui.Activity then return end
    local Activity, Now = Ui.Activity, os.clock()
    if not Force and Now - Ui.LastUpdate < 0.1 then return end
    Ui.Panel:SetTotal(math.max(Activity.Total, 1))
    Ui.Panel:SetStats(Activity.Current, Activity.Current - Activity.Skipped, Activity.Skipped, 0)
    Ui.Panel:SetLabel(Activity.Label .. (Activity.Detail ~= "" and (": " .. Activity.Detail) or ""))
    Ui.LastUpdate = Now
    local Time = os.time()
    if Time - Ui.LastMessage >= 2 then
        print(string.format("%s (%d/%d)%s", Activity.Label, Activity.Current, Activity.Total,
            Activity.Detail ~= "" and (": " .. Activity.Detail) or ""))
        Ui.LastMessage = Time
    end
end

---@param Label string
---@param Total integer
---@return GodotActivityProgress|nil Previous
function GodotProgressPush(Label, Total)
    local Ui = GodotCurrentProgress
    if not Ui then return nil end
    local Previous = Ui.Activity
    Ui.Activity = { Label=Label, Current=0, Total=Total, Skipped=0, Detail="" }
    Render(true)
    return Previous
end

---@param Previous GodotActivityProgress|nil
---@return nil
function GodotProgressPop(Previous)
    local Ui = GodotCurrentProgress
    if not Ui then return end
    Render(true)
    Ui.Activity = Previous
    if Previous then Render(true) end
end

---@param Label string
---@param Total integer|nil
---@return nil
function GodotProgressActivity(Label, Total)
    GodotProgressPush(Label, Total or 0)
end

---@param Label string
---@return nil
function GodotProgressStage(Label)
    local Ui = GodotCurrentProgress
    if not Ui then return end
    Ui.Script:Update(1, Label)
    print(Label)
    Ui.LastMessage = os.time()
    GodotProgressActivity(Label, 0)
end

---@param Count integer
---@return nil
function GodotProgressDiscover(Count)
    local Ui = GodotCurrentProgress
    if Ui and Ui.Activity then Ui.Activity.Total = Ui.Activity.Total + Count; Render(false) end
end

---@param Detail string
---@param Force boolean|nil
---@return nil
function GodotProgressDetail(Detail, Force)
    local Ui = GodotCurrentProgress
    if Ui and Ui.Activity then Ui.Activity.Detail = Detail; Render(Force) end
end

---@param Detail string|nil
---@param Skipped boolean|nil
---@return nil
function GodotProgressAdvance(Detail, Skipped)
    local Ui = GodotCurrentProgress
    if not Ui or not Ui.Activity then return end
    local Activity = Ui.Activity
    Activity.Current = Activity.Current + 1
    Activity.Total = math.max(Activity.Total, Activity.Current)
    if Skipped then Activity.Skipped = Activity.Skipped + 1 end
    if Detail then Activity.Detail = Detail end
    Render(Activity.Current == Activity.Total)
end

---@param Current integer
---@param Total integer
---@param Detail string|nil
---@return nil
function GodotProgressSet(Current, Total, Detail)
    local Ui = GodotCurrentProgress
    if not Ui or not Ui.Activity then return end
    Ui.Activity.Current, Ui.Activity.Total = Current, math.max(Current, Total)
    if Detail then Ui.Activity.Detail = Detail end
    Render(true)
end

---@return integer
function GodotProgressTotal()
    local Ui = GodotCurrentProgress
    return Ui and Ui.Activity and Ui.Activity.Total or 0
end

--- Put the useful error first in narrow terminals; retain source locations in logs.
---@param Failure any
---@return nil
function GodotReportError(Failure)
    local Message, Start = tostring(Failure), 1
    while true do
        local First, Last = Message:find(":%(%d+,[^)]*%):%s*", Start)
        if not First then break end
        Start = Last + 1
    end
    print("[ERROR] " .. Message:sub(Start))
    if Diagnostics and Diagnostics.Log then Diagnostics.Log("[Godot operation] " .. Message) end
end

--- Always release UI handles, including when the operation fails mid-activity.
---@param Total integer
---@param Label string
---@param Action fun(): nil
---@return nil
function GodotProgressRun(Total, Label, Action)
    local Previous = GodotCurrentProgress
    local Script = progress.script.start(Total, Label)
    local Panel = progress.console.new(1, nil, Label)
    GodotCurrentProgress = { Script=Script, Panel=Panel, LastUpdate=0, LastMessage=0 }
    print(Label)
    local Success, Failure = pcall(Action)
    if not Success then
        Panel:SetLabel("Failed: " .. Label)
        Panel:Update(0, 0, 0, 1)
        Script:Update(0, "Failed: " .. Label)
    end
    Panel:Complete()
    Script:Complete()
    GodotCurrentProgress = Previous
    assert(Success, tostring(Failure or ""))
end

--- Polling keeps stdout/stderr and the activity bar live while Godot is running.
--- Runtime helpers emit VARIANT_PROGRESS current total detail for counted jobs.
---@param Command string[]
---@param Options SpawnOptions
---@param TimeoutSeconds number
---@param OnOutput fun(Text: string): nil
---@return integer ExitCode
function GodotProgressProcess(Command, Options, TimeoutSeconds, OnOutput)
    local Ui = GodotCurrentProgress
    local Job = table.concat(Command, " ")
    if Ui then Ui.Panel:AddJob("Godot", Job) end
    ---@type integer|nil
    local Pid
    ---@return integer
    local function Run()
        local Spawned = sdk.spawn_process(Command, Options)
        Pid = Spawned.pid
        local Started, OutBuffer, ErrorBuffer = os.time(), "", ""
        local Counted = false
        ---@param Buffer string
        ---@param Delta string
        ---@param Flush boolean
        ---@return string
        local function Consume(Buffer, Delta, Flush)
            Buffer = Buffer .. Delta
            while true do
                local First, Last = Buffer:find("[\r\n]+")
                if not First then break end
                local Line = Buffer:sub(1, First - 1)
                if Line ~= "" then
                    print(Line)
                    local Current, Total, Detail = Line:match("VARIANT_PROGRESS%s+(%d+)%s+(%d+)%s*(.*)")
                    if Current then
                        Counted = true
                        GodotProgressSet(tonumber(Current), tonumber(Total), Detail)
                    else
                        local Percent = Line:match("(%d+)%%")
                        if Percent then
                            Counted = true
                            GodotProgressSet(tonumber(Percent), 100, Line)
                        end
                    end
                end
                Buffer = Buffer:sub(Last + 1)
            end
            if Flush and Buffer ~= "" then print(Buffer); Buffer = "" end
            return Buffer
        end
        while true do
            local Status = sdk.poll_process(Pid)
            local Out, Errors = Status.stdout_delta or "", Status.stderr_delta or ""
            if Out ~= "" or Errors ~= "" then OnOutput(Out .. Errors) end
            OutBuffer = Consume(OutBuffer, Out, not Status.running)
            ErrorBuffer = Consume(ErrorBuffer, Errors, not Status.running)
            if not Status.running then
                if Status.exit_code == 0 and not Counted then GodotProgressAdvance("Godot completed") end
                return Status.exit_code or -1
            end
            assert(os.time() - Started < TimeoutSeconds, "Godot timed out after " .. TimeoutSeconds .. " seconds")
            Render(false)
            sdk.sleep(0.1)
        end
    end
    local Success, Result = pcall(Run)
    if Pid then pcall(sdk.close_process, Pid) end
    if Ui then Ui.Panel:RemoveJob(Job) end
    assert(Success, tostring(Result or ""))
    ---@cast Result integer
    return Result
end
