--[[
BlenderCore.lua – Batch Blender export driver for TSG PS3 assets
================================================================

Overview
    Drives headless Blender to generate exports (GLB/FBX) from prepared
    .blend files using a Python driver and extension. Asset metadata and
    symlink locations are read from an SQLite database (asset_map table).

Environment contracts
    - Global `sdk` table is expected to provide utilities:
        sdk.run_process(cmd, opts)           -- REQUIRED
        sdk.colour_print({colour, message})  -- optional
        sdk.sleep(seconds)                   -- optional
        sdk.ensure_dir(path)                 -- optional
        sdk.path_exists(path)                -- optional
        sdk.is_file(path)                    -- optional
        sdk.remove_file(path), sdk.remove_dir(path) -- optional
    - Global `sqlite` module is expected with:
        sqlite.open(path) -> db
        db.query(sql) -> array of rows
        db.close()

Public entry point
    BlenderCore.main(opts)
        - opts.verbose: boolean
        - opts.debug_sleep: boolean
        - opts.export: boolean
        - opts.export_formats: list of strings (e.g. {"glb", "fbx"})
        - opts.db_file_path: string
        - opts.blender_exe_path: string (path to Blender executable)

Behavior
    1) Validates required files (Blender exe, Python scripts, SQLite DB)
    2) Loads assets from DB
    3) For each asset: checks if requested exports already exist; runs Blender
    4) Summarizes results; throws if any asset failed

Notes
    - Paths are normalized to the host OS separator
    - Missing optional helpers degrade gracefully
    - Subprocess output is always logged; consider gating by verbose in future
]]


if not sqlite then
    error("sqlite module is not available; ensure LuaScriptAction exposes sqlite helpers")
end
-- run_process is always available in engine runtime
if not sdk.run_process then
    error("sdk.run_process helper is required for BlenderCore.lua")
end

local Utils = _G.import(script_dir .. "/init/BlenderUtils.lua")
if not Utils then
    error("BlenderUtils not found")
end

local function log(colour, message)
    Utils.log(colour, message, "BlenderCore")
end

--- Create and return a temporary directory path for per-run addon files.
-- Uses os.tmpname as a base; attempts to remove the temp file first.
-- @param prefix string|nil
-- @return string temp directory path
local function make_temp_dir(prefix)
    prefix = prefix or "blender_addon_"
    -- Use a workspace-local temp root to avoid relying on os.tmpname (not available in sandbox)
    local temp_root = Utils.join("TMP", "blender_temp")
    sdk.ensure_dir(temp_root)
    local dir = Utils.join(temp_root, prefix .. tostring(os.time()) .. "_" .. tostring(math.random(100000, 999999)))
    sdk.ensure_dir(dir)
    return dir
end

-- Seed RNG once (used only for temp dir suffixes)
math.randomseed(os.time())

--TODO make run script pass these paths
-- Repository-relative locations used by this pipeline
local script_root = Utils.join("EngineApps", "Games", "TheSimpsonsGame-PS3", "operations")
local blender_dir = Utils.join(script_root, "Blender")
local python_script_path = Utils.join(blender_dir, "MainPreinstancedConvert.py")
local python_extension_path = Utils.join(blender_dir, "blender_addon")
--- Convert a list of export format hints to a set and an ordered list.
-- Recognized tokens: "glb", "fbx" (case-insensitive). Duplicates removed.
-- @param list table|nil
-- @return table set, table ordered
local function normalize_export_formats(list)
    local set = {}
    local ordered = {}
    if list then
        for _, value in ipairs(list) do
            local lowered = tostring(value):lower()
            for token in lowered:gmatch("[^%s]+") do
                if token == "glb" or token == "fbx" then
                    if not set[token] then
                        set[token] = true
                        table.insert(ordered, token)
                    end
                end
            end
        end
    end
    return set, ordered
end


--- Load all assets from the SQLite `asset_map` table.
-- Expected columns: identifier, filename, preinstanced_symlink, blend_symlink, glb_symlink
-- @param db_path string
-- @return table array of asset tables
local function load_assets(db_path)
    local db = sqlite.open(Utils.to_long_path(db_path))
    local rows = db.query("SELECT identifier, filename, preinstanced_symlink, blend_symlink, glb_symlink FROM asset_map")
    local assets = {}
    for index, row in ipairs(rows) do
        assets[index] = {
            identifier = row.identifier,
            filename = row.filename,
            preinstanced_symlink = row.preinstanced_symlink,
            blend_symlink = row.blend_symlink,
            glb_symlink = row.glb_symlink
        }
    end
    db.close()
    return assets
end

--- Check whether an asset has enough information and whether work is needed.
-- @param asset table
-- @param export_set table set-like { glb=true?, fbx=true? }
-- @return boolean ok, boolean run_needed, string|nil reason
local function should_process_asset(asset, export_set)
    if not asset.blend_symlink or not asset.preinstanced_symlink then
        return false, false, "Missing required symlink paths"
    end

    local blend_file = Utils.get_path(asset.blend_symlink, asset.filename, ".blend")
    if not sdk.is_file(blend_file) then
        return false, false, string.format("Blend file not found: %s", blend_file)
    end

    local run_needed = false
    if export_set.glb then
        if not asset.glb_symlink then
            return false, false, "GLB symlink path missing"
        end
        local glb_file = Utils.get_path(asset.glb_symlink, asset.filename, ".glb")
        if not sdk.is_file(glb_file) then
            run_needed = true
        end
    end

    if export_set.fbx then
        if not asset.glb_symlink then
            return false, false, "FBX symlink path missing"
        end
        local fbx_file = Utils.get_path(asset.glb_symlink, asset.filename, ".fbx")
        if not sdk.is_file(fbx_file) then
            run_needed = true
        end
    end

    return true, run_needed, nil
end

--- Run Blender headless for a single asset if required.
-- Builds the command line for Blender, invokes it, and maps results to
-- a structured record.
-- @param asset table
-- @param export_set table set-like { glb=true?, fbx=true? }
-- @param ordered_formats table e.g. {"glb", "fbx"}
-- @param verbose boolean
-- @param debug_sleep boolean
-- @return table { asset_id, success, skipped, message }
local function run_blender_for_asset(asset, export_set, ordered_formats, verbose, debug_sleep, blender_exe_path, game_root_path, json_db_path, preinstanced_dir)
    local ok, run_needed, reason = should_process_asset(asset, export_set)
    if not ok then
        return { asset_id = asset.identifier, success = false, skipped = false, message = reason }
    end

    if not run_needed then
        return { asset_id = asset.identifier, success = true, skipped = true, message = string.format("Skipped: requested exports already exist for %s", asset.filename) }
    end

    -- Informational log for the upcoming Blender run
    log(Utils.Colours.DARKCYAN, string.format("running blender for asset %s", tostring(asset.identifier)))

    local blend_file = Utils.get_path(asset.blend_symlink, asset.filename, ".blend")
    local glb_file = Utils.get_path(asset.glb_symlink, asset.filename, ".glb")
    local fbx_file = Utils.get_path(asset.glb_symlink, asset.filename, ".fbx")
    local preinstanced_file = Utils.get_path(asset.preinstanced_symlink, asset.filename, ".preinstanced")

    if not sdk.is_file(preinstanced_file) then
        return { asset_id = asset.identifier, success = false, skipped = false, message = string.format("Preinstanced symlink missing: %s", preinstanced_file) }
    end

    -- Create a per-run temp addon directory; will be removed after execution
    local temp_addon_dir = make_temp_dir("blender_addon_")
    
    local batch_file = Utils.join(temp_addon_dir, "batch.json")
    local batch_data = {
        {
            asset_id = asset.identifier,
            blend_file = blend_file,
            preinstanced_file = preinstanced_file,
            glb_file = glb_file,
            fbx_file = fbx_file
        }
    }
    local fh = io.open(batch_file, "w")
    if fh then
        fh:write(sdk.text.json.encode(batch_data))
        fh:close()
    else
        log(Utils.Colours.RED, "Failed to write batch file: " .. batch_file)
        return { asset_id = asset.identifier, success = false, skipped = false, message = "Failed to write batch file" }
    end

    -- Blender CLI layout: `--` separates Blender's args from script args
    local command = {
        blender_exe_path,
        "-b",
        "--python", python_script_path,
        "--",
        "--batch_file", batch_file,
        "--python_extension_path", python_extension_path,
        "--current_dir", blender_dir,
        "--temp_addon_dir", temp_addon_dir,
        "--game_root_path", game_root_path,
        "--export_formats", table.concat(ordered_formats, ",")
    }

    if verbose then table.insert(command, "--verbose") end
    if debug_sleep then table.insert(command, "--debug_sleep") end
    if json_db_path then
        table.insert(command, "--db_path")
        table.insert(command, json_db_path)
    end
    if preinstanced_dir then
        table.insert(command, "--preinstanced_dir")
        table.insert(command, preinstanced_dir)
    end

    local result
    local status, err = pcall(function()
        -- Capture stdout/stderr for diagnostics and summary reporting
        result = sdk.run_process(command, { capture_stdout = true, capture_stderr = true })
    end)

    if not status then
        if sdk.remove_dir then
            sdk.remove_dir(temp_addon_dir)
        end
        return { asset_id = asset.identifier, success = false, skipped = false, message = string.format("Process launch failed: %s", err) }
    end

    -- Subprocess output is echoed to help debug Blender/Python failures
    log(Utils.Colours.DARKGRAY, string.format("\n--- Output for Asset ID: %s ---", asset.identifier))
    if result.stdout and #result.stdout > 0 then
        log(Utils.Colours.GRAY, result.stdout)
    end
    if result.stderr and #result.stderr > 0 then
        log(Utils.Colours.YELLOW, result.stderr)
    end
    log(Utils.Colours.DARKGRAY, string.format("--- End of Output for Asset ID: %s ---\n", asset.identifier))

    if sdk.remove_dir then
        sdk.remove_dir(temp_addon_dir)
    end

    if result.exit_code ~= 0 then
        local message = result.stderr and #result.stderr > 0 and result.stderr:match("[^\n]*") or result.stdout or "Blender process reported failure"
        return { asset_id = asset.identifier, success = false, skipped = false, message = message }
    end

    return { asset_id = asset.identifier, success = true, skipped = false, message = string.format("Processed asset %s", asset.identifier) }
end

local BlenderCore = {}

--- Entry point for batch processing.
-- Validates resources, loads assets, processes sequentially, and summarizes.
-- Throws an error if any asset failed to process.
-- @param opts table (see module header for fields)
function BlenderCore.main(opts)
    opts = opts or {}
    VERBOSE = not not opts.verbose
    local debug_sleep = not not opts.debug_sleep
    local export_set, ordered_formats = normalize_export_formats(opts.export_formats)

    local db_path = opts.db_file_path and Utils.normalize_separators(opts.db_file_path)
    db_path = Utils.to_long_path(Utils.normalize_separators(db_path))
    if not db_path or db_path == "" then
        error("DB file path must be specified in opts.db_file_path")
        os.exit(1)
    end

    local json_db_path = opts.preinstanced_dir and Utils.join(opts.preinstanced_dir, "normalized_map.json")
    if json_db_path then
        json_db_path = Utils.to_long_path(Utils.normalize_separators(json_db_path))
    end

    local blender_exe_path = opts.blender_exe_path and Utils.to_long_path(Utils.normalize_separators(opts.blender_exe_path)) or ""
    local game_root_path = opts.game_root and Utils.to_long_path(Utils.normalize_separators(opts.game_root))

    log(Utils.Colours.CYAN, "all input opts: " .. sdk.text.json.encode(opts))

    log(Utils.Colours.CYAN, string.format("Export formats: %s", (#ordered_formats > 0) and table.concat(ordered_formats, ", ") or "None"))
    log(Utils.Colours.CYAN, string.format("Using DB: %s", db_path))
    log(Utils.Colours.CYAN, string.format("Using Blender executable: %s", blender_exe_path))
    if not game_root_path then
        error("Game root path must be specified in opts.game_root_path")
        os.exit(1)
    end
    log(Utils.Colours.CYAN, string.format("Using game root path: %s", game_root_path))

    if not sdk.path_exists(blender_exe_path) then
        error(string.format("Blender executable not found: %s", blender_exe_path))
    end
    if not sdk.path_exists(python_script_path) then
        error(string.format("Python driver not found: %s", python_script_path))
    end
    if not sdk.path_exists(python_extension_path) then
        error(string.format("Python extension not found: %s", python_extension_path))
    end
    if not sdk.path_exists(db_path) then
        error(string.format("DB not found: %s", db_path))
    end

    local assets = load_assets(db_path)
    log(Utils.Colours.CYAN, string.format("Loaded %d assets from DB", #assets))

    local successes = {}
    local failures = {}
    local skipped = {}

    -- Prepare list of assets that actually require processing
    local work_queue = {}
    for _, asset in ipairs(assets) do
        local ok, need, reason = should_process_asset(asset, export_set)
        if not ok then
            table.insert(failures, { asset_id = asset.identifier, success = false, skipped = false, message = reason })
        elseif not need then
            table.insert(skipped, { asset_id = asset.identifier, success = true, skipped = true, message = string.format("Skipped: requested exports already exist for %s", asset.filename) })
        else
            table.insert(work_queue, asset)
        end
    end

    local p = progress.new(#work_queue, "blender-batch", "Exporting Assets with Blender...")

    local has_spawn = (sdk.spawn_process ~= nil)
    -- Default workers: user-specified opts.workers -> global cpu_count -> sdk.cpu_count -> 1
    local default_workers = 1
    if _G.cpu_count then
        default_workers = tonumber(_G.cpu_count) or default_workers
    elseif sdk and sdk.cpu_count then
        default_workers = tonumber(sdk.cpu_count) or default_workers
    end
    local max_workers = tonumber(opts.workers) or default_workers
    if max_workers < 1 then max_workers = 1 end

    if not has_spawn then
        -- Fallback: run sequentially using existing run_blender_for_asset implementation
        log(Utils.Colours.YELLOW, "spawn_process unavailable; running sequentially using sdk.run_process")
        for _, asset in ipairs(work_queue) do
            local rec = run_blender_for_asset(asset, export_set, ordered_formats, VERBOSE, debug_sleep, blender_exe_path, game_root_path, json_db_path, opts.preinstanced_dir)
            if rec.success then
                table.insert(successes, rec)
            else
                table.insert(failures, rec)
            end
            p:Update(1)
        end
    else
        -- Concurrent execution using spawn/poll with JSON batching
        log(Utils.Colours.GREEN, string.format("Spawning up to %d workers using sdk.spawn_process", max_workers))

        local active = {} -- pid -> { batch_file=..., temp_dir=..., assets=... }
        local batches = {}

        -- Partition work_queue into discrete batches for parallel processing
        local batch_size = tonumber(opts.batch_size) or 50
        for i = 1, #work_queue, batch_size do
            local batch = {}
            for j = i, math.min(i + batch_size - 1, #work_queue) do
                table.insert(batch, work_queue[j])
            end
            table.insert(batches, batch)
        end

        local function active_count()
            local c = 0
            for _ in pairs(active) do c = c + 1 end
            return c
        end

        local function start_next()
            if #batches == 0 then return end
            if active_count() >= max_workers then return end

            local batch_assets = table.remove(batches, 1)
            if #batch_assets == 0 then return end

            local temp_addon_dir = make_temp_dir("blender_addon_")
            local batch_file = Utils.join(temp_addon_dir, "batch.json")

            local batch_data = {}
            for _, asset in ipairs(batch_assets) do
                local blend_file = Utils.get_path(asset.blend_symlink, asset.filename, ".blend")
                local glb_file = Utils.get_path(asset.glb_symlink, asset.filename, ".glb")
                local fbx_file = Utils.get_path(asset.glb_symlink, asset.filename, ".fbx")
                local preinstanced_file = Utils.get_path(asset.preinstanced_symlink, asset.filename, ".preinstanced")

                table.insert(batch_data, {
                    asset_id = asset.identifier,
                    blend_file = blend_file,
                    preinstanced_file = preinstanced_file,
                    glb_file = glb_file,
                    fbx_file = fbx_file
                })
            end

            local fh = io.open(batch_file, "w")
            if fh then
                fh:write(sdk.text.json.encode(batch_data))
                fh:close()
            else
                log(Utils.Colours.RED, "Failed to write batch file: " .. batch_file)
                return
            end

            local cmd = {
                blender_exe_path,
                "-b",
                "--python", python_script_path,
                "--",
                "--batch_file", batch_file,
                "--python_extension_path", python_extension_path,
                "--current_dir", blender_dir,
                "--temp_addon_dir", temp_addon_dir,
                "--game_root_path", game_root_path,
                "--export_formats", table.concat(ordered_formats, ",")
            }

            if VERBOSE then table.insert(cmd, "--verbose") end
            if debug_sleep then table.insert(cmd, "--debug_sleep") end
            if json_db_path then
                table.insert(cmd, "--db_path")
                table.insert(cmd, json_db_path)
            end
            if opts.preinstanced_dir then
                table.insert(cmd, "--preinstanced_dir")
                table.insert(cmd, opts.preinstanced_dir)
            end

            local ok, res = pcall(function()
                return sdk.spawn_process(cmd, { capture_stdout = true, capture_stderr = true, cwd = nil })
            end)

            if not ok or not res or not res.pid then
                if sdk.remove_dir then pcall(sdk.remove_dir, temp_addon_dir) end
                local msg = "spawn failed"
                if not ok then msg = tostring(res) end
                for _, asset in ipairs(batch_assets) do
                    table.insert(failures, { asset_id = asset.identifier, success = false, skipped = false, message = msg })
                    p:Update(1)
                end
                return
            end

            local pid = res.pid
            active[pid] = { batch_file = batch_file, temp_dir = temp_addon_dir, assets = batch_assets }
            log(Utils.Colours.DARKCYAN, string.format("Launched PID %s for batch of %d assets", tostring(pid), #batch_assets))
        end

        -- seed initial workers
        for i = 1, max_workers do start_next() end

        -- poll loop
        while next(active) ~= nil or #batches > 0 do
            -- start more if capacity
            while active_count() < max_workers and #batches > 0 do
                start_next()
            end

            -- poll active pids
            for pid, info in pairs(active) do
                local ok, pol = pcall(function() return sdk.poll_process(pid) end)
                if not ok then
                    -- treat as failure and cleanup
                    if sdk.remove_dir then pcall(sdk.remove_dir, info.temp_dir) end
                    for _, asset in ipairs(info.assets) do
                        table.insert(failures, { asset_id = asset.identifier, success = false, skipped = false, message = "poll failed: " .. tostring(pol) })
                        p:Update(1)
                    end
                    active[pid] = nil
                else
                    -- Process stdout delta for progress markers
                    if pol.stdout_delta and #pol.stdout_delta > 0 then
                        for line in pol.stdout_delta:gmatch("[^\r\n]+") do
                            local asset_id, status, msg = line:match("__REMAKE_ASSET_DONE__:([^:]+):([^:]+):?(.*)")
                            if asset_id and status then
                                if status == "SUCCESS" then
                                    table.insert(successes, { asset_id = asset_id, success = true, skipped = false, message = "Processed asset " .. asset_id })
                                else
                                    table.insert(failures, { asset_id = asset_id, success = false, skipped = false, message = (msg and msg ~= "") and msg or "Failed" })
                                end
                                p:Update(1)
                            else
                                log(Utils.Colours.GRAY, string.format("[PID %s] %s", tostring(pid), line))
                            end
                        end
                    end

                    if pol.stderr_delta and #pol.stderr_delta > 0 then
                        for line in pol.stderr_delta:gmatch("[^\r\n]+") do
                            log(Utils.Colours.YELLOW, string.format("[PID %s] %s", tostring(pid), line))
                        end
                    end

                    if not pol.running then
                        -- finished
                        if sdk.remove_dir then pcall(sdk.remove_dir, info.temp_dir) end

                        local exit_code = pol.exit_code or 1
                        if exit_code ~= 0 then
                            local message = (pol.stderr and #pol.stderr > 0 and pol.stderr:match("^[^\n]*")) or pol.stdout or "Blender process reported failure"
                            log(Utils.Colours.RED, string.format("Batch PID %s failed: %s", tostring(pid), message))
                        else
                            log(Utils.Colours.DARKGRAY, string.format("Batch PID %s finished successfully", tostring(pid)))
                        end

                        active[pid] = nil
                    end
                end
            end

            if sdk.sleep then
                pcall(sdk.sleep, 0.05)
            else
                local t0 = os.clock()
                while os.clock() - t0 < 0.05 do end
            end
        end
    end

    p:Complete()

    -- Summarize and error on failures (same behaviour as before)
    log(Utils.Colours.CYAN, string.format("Successes: %d, Failures: %d, Skipped: %d", #successes, #failures, #skipped))
    if #failures > 0 then
        log(Utils.Colours.RED, "Some assets failed to process. See messages for details.")
        for _, f in ipairs(failures) do
            log(Utils.Colours.RED, string.format("Asset %s: %s", tostring(f.asset_id), tostring(f.message)))
        end
        error(string.format("%d asset(s) failed to process", #failures))
    end

    log(Utils.Colours.GREEN, "\nProcessing complete.")
end

return BlenderCore
