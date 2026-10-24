-- Operation orchestration and owned-output lifecycle. No root-level build work.
local OwnershipMarker = ".local_variant_owned.json"

---@return string|nil
function VariantDefaultSource()
    local ConfigPath = join(Game_Root, "config.toml")
    if not sdk.is_file(ConfigPath) then return nil end
    local Config = sdk.text.toml.read_file(ConfigPath)
    assert(type(Config) == "table", "Invalid config.toml")
    local Values = Config.placeholders
    if type(Values) ~= "table" then return nil end
    Values = Values[1] or Values
    local Parts = {}
    for _, Key in ipairs({ "Platform", "Region", "Type", "audio_state", "isRenamed" }) do
        assert(type(Values[Key]) == "string" and Values[Key] ~= "", "Missing config placeholder: " .. Key)
        Parts[#Parts + 1] = Values[Key]
    end
    return join(Game_Root, "GameFiles", table.concat(Parts, "-"))
end

---@param Arguments string[]
---@return VariantOptions
function VariantParseArguments(Arguments)
    local Project = join(Game_Root, "Godot", "GodotGame", "PreBuilt")
    ---@type VariantOptions
    local Options = { Project=Project, Assets=join(Project, "assets"),
        Output=join(dirname(Project), "LocalVariant"), Work=join(dirname(Project), ".local_variant_work"),
        Collision=true, DryRun=false, Clean=false, Help=false }
    local Fields = { ["--assets"]="Assets", ["--source"]="Source", ["--logos"]="Logos", ["--godot"]="Godot" }
    local Index = 1
    while Index <= #Arguments do
        local Argument = Arguments[Index]
        local Key, Inline = Argument:match("^(%-%-[^=]+)=(.*)$")
        Key = Key or Argument
        if Fields[Key] then
            if Inline == nil then Index = Index + 1 end
            local Value = Inline or Arguments[Index]
            assert(Value and Value:match("%S") and Value:sub(1, 1) ~= "-", Key .. " requires a path")
            Options[Fields[Key]] = VariantAbsolute(Value)
        elseif Inline == nil and Key == "--no-collision" then Options.Collision = false
        elseif Inline == nil and Key == "--dry-run" then Options.DryRun = true
        elseif Inline == nil and Key == "--clean" then Options.Clean = true
        elseif Inline == nil and (Key == "--help" or Key == "-h") then Options.Help = true
        else assert(false, "Unknown argument: " .. Argument) end
        Index = Index + 1
    end
    return Options
end

---@param Path string
---@param ExpectedParent string
---@return nil
function VariantCheckOwned(Path, ExpectedParent)
    Path, ExpectedParent = VariantAbsolute(Path), VariantAbsolute(ExpectedParent)
    assert(VariantWithin(Path, Game_Root) and VariantAbsolute(dirname(Path)) == ExpectedParent,
        "Refusing unsafe output: " .. Path)
    VariantNoLinks(Path)
    if sdk.lexists(Path) then
        assert(sdk.is_dir(Path), "Output is not a directory: " .. Path)
        local Marker = VariantReadJson(join(Path, OwnershipMarker))
        assert(Marker.tool == "local_variant", "Refusing unowned output: " .. Path)
    end
end

---@param Path string
---@param Root string
---@return nil
local function RemoveOwnedTree(Path, Root)
    assert(VariantWithin(Path, Root), "Cleanup leaves owned output: " .. Path)
    VariantNoLinks(Path)
    for _, Name in ipairs(sdk.list_dir(Path)) do
        local Child = VariantCheckedPath(Root, get_relative_path(Root, join(Path, Name)))
        if sdk.is_dir(Child) then RemoveOwnedTree(Child, Root)
        else
            assert(sdk.remove_file(Child), "Cannot remove generated file: " .. Child)
            GodotProgressAdvance(Child)
        end
    end
    assert(sdk.remove_dir(Path), "Cannot remove generated directory: " .. Path)
    GodotProgressAdvance(Path)
end

---@param Path string
---@param ExpectedParent string
---@return nil
function VariantOwnedRemove(Path, ExpectedParent)
    VariantCheckOwned(Path, ExpectedParent)
    if sdk.lexists(Path) then
        -- Preflight the complete tree before deleting anything. Never follow a
        -- link inserted into generated output, including a directory junction.
        local Files = {}
        local PreviousActivity = GodotProgressPush("Inspect generated files before cleanup", 0)
        VariantFindFiles(Path, "", Files, {}, false)
        local Total = GodotProgressTotal() + 1
        GodotProgressActivity("Remove owned generated files", Total)
        RemoveOwnedTree(Path, VariantAbsolute(Path))
        GodotProgressPop(PreviousActivity)
    end
end

---@param Work string
---@return table<string, string>
local function BuildEnvironment(Work)
    local Environment = {}
    for _, Name in ipairs({ "APPDATA", "LOCALAPPDATA", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME" }) do
        Environment[Name] = join(Work, Name:lower())
        assert(sdk.ensure_dir(Environment[Name]), "Cannot create isolated profile directory")
    end
    return Environment
end

---@param Explicit string|nil
---@param Work string
---@return string
function VariantFindGodot(Explicit, Work)
    local Executable = Explicit
    if not Executable then
        local Ok, Preferred = pcall(tool, "Godot", "4.6-stable")
        if Ok and type(Preferred) == "string" and sdk.is_file(Preferred) then Executable = Preferred
        else Executable = tool("Godot") end
    end
    assert(type(Executable) == "string" and sdk.is_file(Executable), "Godot not found; supply --godot with a registered Godot 4.6+ executable")
    Executable = VariantAbsolute(Executable)
    for _, Marker in ipairs({ "_sc_", "._sc_" }) do
        assert(not sdk.path_exists(join(dirname(Executable), Marker)),
            "Select a registered Godot without a portable " .. Marker .. " marker; its profile cannot be isolated through the Lua SDK")
    end
    local Result = sdk.run_process({ Executable, "--version" }, { env=BuildEnvironment(Work), timeout_ms=30000 })
    local Major, Minor = (Result.stdout or ""):match("(%d+)%.(%d+)")
    assert(Result.success and Major and (tonumber(Major) > 4 or tonumber(Major) == 4 and tonumber(Minor) >= 6), "Godot 4.6+ is required")
    return Executable
end

---@param Godot string
---@param Project string
---@param Arguments string[]
---@param Work string
---@return nil
function VariantRunGodot(Godot, Project, Arguments, Work)
    local Command = { Godot, "--headless", "--path", Project, "--log-file", join(Work, "godot.log") }
    for _, Argument in ipairs(Arguments) do Command[#Command + 1] = Argument end
    print("Godot: " .. table.concat(Arguments, " "))
    local ProcessLog = join(Work, "process.log")
    local Handle, Message = io.open(ProcessLog, "a")
    assert(Handle, Message or ("Cannot open " .. ProcessLog))
    ---@cast Handle FileHandle
    Handle:write("\nCOMMAND " .. table.concat(Arguments, " ") .. "\n")
    local Chunks = {}
    ---@param Text string
    ---@return nil
    local function AppendOutput(Text)
        Chunks[#Chunks + 1] = Text
        Handle:write(Text)
    end
    GodotProgressActivity("Godot " .. table.concat(Arguments, " "), 1)
    local Success, ExitCode = pcall(GodotProgressProcess, Command,
        { cwd=Work, capture_stdout=true, capture_stderr=true, env=BuildEnvironment(Work) }, 1200, AppendOutput)
    Handle:close()
    assert(Success, tostring(ExitCode) .. "; see " .. ProcessLog)
    local Output = table.concat(Chunks)
    assert(ExitCode == 0, "Godot exited " .. tostring(ExitCode) .. "; see " .. ProcessLog)
    for Line in Output:gmatch("[^\r\n]+") do
        assert(not (Line:find("ERROR:", 1, true) or Line:find("Parse Error:", 1, true))
            or Line:find("Failed to read the root certificate store", 1, true), "Godot reported " .. Line .. "; see " .. ProcessLog)
    end
end

---@param Options VariantOptions
---@return nil
local function CheckInputs(Options)
    for _, Path in ipairs({ Options.Project, Options.Assets, Options.Source or Options.Assets,
        Options.Logos or join(dirname(Options.Assets), "logos") }) do
        assert(not VariantWithin(Path, Options.Output) and not VariantWithin(Path, Options.Work),
            "Inputs must live outside disposable local output: " .. Path)
        VariantNoLinks(Path)
    end
    assert(sdk.is_dir(Options.Project), "Canonical Godot project not found: " .. Options.Project)
end

---@param Options VariantOptions
---@return nil
local function BuildLocked(Options)
    local Stage, Previous = join(Options.Work, "staging"), join(Options.Work, "previous")
    if Options.Clean then
        GodotProgressStage("Remove local variant output")
        if not Options.DryRun then
            VariantOwnedRemove(Options.Output, dirname(Options.Output))
        end
        GodotProgressStage("Remove pending staging project")
        if not Options.DryRun then
            VariantOwnedRemove(Stage, Options.Work)
        end
        GodotProgressStage("Remove previous local project")
        if not Options.DryRun then
            VariantOwnedRemove(Previous, Options.Work)
        end
        print(Options.DryRun and ("Would remove " .. Options.Output) or "Local variant removed.")
        return
    end
    GodotProgressStage("Load variant inputs and normalization maps")
    if not Options.Source and Options.Collision then Options.Source = VariantDefaultSource() end
    CheckInputs(Options)
    local Builder = VariantNewBuilder(Options)
    if Options.DryRun then
        GodotProgressStage("Preview local variant adaptation")
        VariantPreview(Builder)
        print("No project changed.")
        return
    end
    local Godot = VariantFindGodot(Options.Godot, Options.Work)
    VariantWrite(join(Options.Work, "process.log"), "")
    GodotProgressStage("Prepare isolated staging project")
    VariantOwnedRemove(Stage, Options.Work)
    VariantOwnedRemove(Previous, Options.Work)
    VariantCheckOwned(Options.Output, dirname(Options.Output))
    assert(sdk.ensure_dir(Stage), "Cannot create staging project")
    VariantWriteJson(join(Stage, OwnershipMarker), { tool="local_variant" })
    print("Preparing isolated project...")
    VariantPrepare(Builder, Stage)
    print(string.format("Copied %d referenced assets; %d original collision files.", #GodotSortedKeys(Builder.Materialized), #GodotSortedKeys(Builder.Jobs)))
    GodotProgressStage("Hash original collision inputs")
    VariantRunGodot(Godot, Stage, { "--script", "res://.variant_tools/hash_jobs.gd" }, Options.Work)
    GodotProgressStage("Bake original collision resources")
    VariantRunGodot(Godot, Stage, { "--script", "res://.variant_tools/bake.gd" }, Options.Work)
    GodotProgressStage("Attach collision and write adaptation report")
    local Results = VariantReadJson(join(Stage, "variant_bake_results.json"))
    ---@cast Results VariantBakeResults
    VariantAttach(Builder, Stage, Results)
    VariantWriteJson(join(Stage, "variant_report.json"), Builder.Report)
    GodotProgressStage("Import local project resources")
    VariantRunGodot(Godot, Stage, { "--editor", "--import" }, Options.Work)
    GodotProgressStage("Check the local variant editor plugin")
    VariantRunGodot(Godot, Stage, { "--script", "res://addons/local_variant/plugin.gd", "--check-only" }, Options.Work)
    GodotProgressStage("Validate scenes and collision physics")
    VariantRunGodot(Godot, Stage, { "--script", "res://.variant_tools/validate.gd" }, Options.Work)
    local Validation = VariantReadJson(join(Stage, "variant_validation.json"))
    ---@cast Validation VariantValidation
    assert(type(Validation.failures) == "table" and #Validation.failures == 0,
        "Scene validation failed: " .. table.concat(Validation.failures or { "Invalid validation report" }, "; "))
    GodotProgressStage("Smoke test the local project")
    VariantRunGodot(Godot, Stage, { "--quit-after", "5" }, Options.Work)
    -- The SDK's directory move can fall back to copy/delete on failure. Godot's
    -- rename_absolute gives us real rename-only publication and rollback instead.
    GodotProgressStage("Publish validated local project")
    VariantCheckOwned(Options.Output, dirname(Options.Output))
    VariantWrite(join(Options.Work, "project.godot"), 'config_version=5\n[application]\nconfig/name="Variant publication"\n')
    VariantCopy(join(Game_Root, "operations", "godot", "variant_runtime", "publish.gd"), join(Options.Work, "publish.gd"))
    VariantWriteJson(join(Options.Work, "publication.json"), { output=VariantAbsolute(Options.Output), stage=VariantAbsolute(Stage), previous=VariantAbsolute(Previous) })
    VariantRunGodot(Godot, Options.Work, { "--script", "res://publish.gd" }, Options.Work)
    VariantOwnedRemove(Previous, Options.Work)
    VariantWriteJson(join(Options.Work, "status.json"), { ok=true, output=Options.Output })
    print("Built " .. Options.Output .. "\nReport: " .. join(Options.Output, "variant_report.json"))
end

---@param Arguments string[]
---@return nil
function BuildLocalVariant(Arguments)
    local Options = VariantParseArguments(Arguments)
    if Options.Help then
        print("Build an isolated LocalVariant Godot project without rewriting canonical scenes or inputs.\n"
            .. "Options: --assets DIR, --source DIR, --logos DIR, --godot EXE, --no-collision, --dry-run, --clean, --help/-h")
        return
    end
    ---@return nil
    local function Work()
        VariantNoLinks(Options.Work)
        assert(sdk.ensure_dir(Options.Work), "Cannot create variant work directory")
        local Lock = join(Options.Work, "build.lock")
        -- Match the existing audio operation's exclusive file-rename lock pattern.
        assert(not sdk.lexists(Lock), "Another build is active; check stale lock " .. Lock)
        local Temporary = Lock .. "." .. tostring(os.time()) .. "." .. tostring(math.random(1, 1000000000))
        VariantNoLinks(Temporary)
        VariantWrite(Temporary, "local_variant\n")
        local Acquired = sdk.rename_file(Temporary, Lock, false)
        if not Acquired then sdk.remove_file(Temporary) end
        assert(Acquired, "Another build is active; check stale lock " .. Lock)
        local Success, Message = pcall(BuildLocked, Options)
        local Released = sdk.remove_file(Lock)
        if not Success then
            VariantWriteJson(join(Options.Work, "status.json"), { ok=false, error=tostring(Message) })
            assert(false, tostring(Message))
        end
        assert(Released, "Cannot release build lock: " .. Lock)
    end
    local Stages = Options.Clean and 3 or (Options.DryRun and 2 or 10)
    GodotProgressRun(Stages, "Build Isolated Local Godot Variant", Work)
end
