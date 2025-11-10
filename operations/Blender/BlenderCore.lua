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
        - opts.main_db: string (path to main asset DB; passed to Blender script)
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

-- host OS path separator (first character of package.config)
local path_sep = package.config:sub(1, 1)
-- Colour names used by sdk.colour_print when available
local Colours = {
    DEFAULT = "default",
    WHITE = "white",
    RED = "red",
    GREEN = "green",
    YELLOW = "yellow",
    BLUE = "blue",
    MAGENTA = "magenta",
    CYAN = "cyan",
    GRAY = "gray",
    GREY = "gray",
    DARK_GREEN = "darkgreen",
    DARKGRAY = "darkgray",
    DARKGREY = "darkgray",
    DARKCYAN = "darkcyan",
    DARKYELLOW = "darkyellow",
    DARKRED = "darkred"
}

local PREFIX = "BlenderCore"
local VERBOSE = false

--- Log a message with a module prefix and an optional colour.
-- @param colour string|nil
-- @param message string
local function log(colour, message)
    sdk.colour_print({ colour = colour or Colours.DEFAULT, message = string.format("[%s] %s", PREFIX, message or "") })
end

--- Normalize path separators to match the host OS.
-- @param path string|nil
-- @return string|nil
local function normalize_separators(path)
    if not path then
        return path
    end
    if path_sep == "\\" then
        path = path:gsub("/", "\\")
    else
        path = path:gsub("\\", "/")
    end
    return path
end

--- Join path segments and trim redundant separators.
-- @vararg string
-- @return string
local function join(...)
    local parts = { ... }
    local buffer = {}
    for index = 1, #parts do
        local part = parts[index]
        if part and part ~= "" then
            part = normalize_separators(part)
            if index > 1 then
                part = part:gsub("^" .. path_sep .. "+", "")
            end
            if index < #parts then
                part = part:gsub(path_sep .. "+$", "")
            end
            table.insert(buffer, part)
        end
    end
    return table.concat(buffer, path_sep)
end

--- Return true when path exists.
local function path_exists(path)
    return sdk.path_exists(path)
end

--- Return true when path is a file.
local function is_file(path)
    return sdk.is_file(path)
end

--- Create and return a temporary directory path for per-run addon files.
-- Uses os.tmpname as a base; attempts to remove the temp file first.
-- @param prefix string|nil
-- @return string temp directory path
local function make_temp_dir(prefix)
    prefix = prefix or "blender_addon_"
    -- Use a workspace-local temp root to avoid relying on os.tmpname (not available in sandbox)
    local temp_root = join("TMP", "blender_temp")
    sdk.ensure_dir(temp_root)
    local dir = join(temp_root, prefix .. tostring(os.time()) .. "_" .. tostring(math.random(100000, 999999)))
    sdk.ensure_dir(dir)
    return dir
end

-- Seed RNG once (used only for temp dir suffixes)
math.randomseed(os.time())

--TODO make run script pass these paths
-- Repository-relative locations used by this pipeline
local script_root = join("EngineApps", "Games", "TheSimpsonsGame-PS3", "operations")
local blender_dir = join(script_root, "Blender")
local python_script_path = join(blender_dir, "MainPreinstancedConvert.py")
local python_extension_file = join(blender_dir, "PreinstancedImportExtension.py")
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
-- Expected columns: identifier, filename, preinstanced_symlink,
--                   blend_symlink, glb_symlink
-- @param db_path string
-- @return table array of asset tables
local function load_assets(db_path)
    local db = sqlite.open(db_path)
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

    local blend_file = join(asset.blend_symlink, asset.filename .. ".blend")
    if not is_file(blend_file) then
        return false, false, string.format("Blend file not found: %s", blend_file)
    end

    local run_needed = false
    if export_set.glb then
        if not asset.glb_symlink then
            return false, false, "GLB symlink path missing"
        end
        local glb_file = join(asset.glb_symlink, asset.filename .. ".glb")
        if not is_file(glb_file) then
            run_needed = true
        end
    end

    if export_set.fbx then
        if not asset.glb_symlink then
            return false, false, "FBX symlink path missing"
        end
        local fbx_file = join(asset.glb_symlink, asset.filename .. ".fbx")
        if not is_file(fbx_file) then
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
local function run_blender_for_asset(asset, export_set, ordered_formats, verbose, debug_sleep, main_db_path, blender_exe_path, game_root_path)
    local ok, run_needed, reason = should_process_asset(asset, export_set)
    if not ok then
        return { asset_id = asset.identifier, success = false, skipped = false, message = reason }
    end

    if not run_needed then
        return { asset_id = asset.identifier, success = true, skipped = true, message = string.format("Skipped: requested exports already exist for %s", asset.filename) }
    end

    -- Informational log for the upcoming Blender run
    log(Colours.DARKCYAN, string.format("running blender for asset %s", tostring(asset.identifier)))

    local blend_file = join(asset.blend_symlink, asset.filename .. ".blend")
    local glb_dir = asset.glb_symlink or ""
    local glb_file = join(glb_dir, asset.filename .. ".glb")
    local fbx_file = join(glb_dir, asset.filename .. ".fbx")
    local preinstanced_file = join(asset.preinstanced_symlink, asset.filename .. ".preinstanced")

    if not is_file(preinstanced_file) then
        return { asset_id = asset.identifier, success = false, skipped = false, message = string.format("Preinstanced symlink missing: %s", preinstanced_file) }
    end

    -- Create a per-run temp addon directory; will be removed after execution
    local temp_addon_dir = make_temp_dir("blender_addon_")
    -- Blender CLI layout: `--` separates Blender's args from script args
    local command = {
        blender_exe_path,
        "-b", blend_file,
        "--python", python_script_path,
        "--",
        blend_file,
        preinstanced_file,
        glb_file,
        python_extension_file,
        verbose and "true" or "false",
        debug_sleep and "true" or "false",
        blender_dir,
        fbx_file,
        asset.identifier,
        temp_addon_dir,
        main_db_path,
        game_root_path,
        table.concat(ordered_formats, ",")
    }

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
    log(Colours.DARKGRAY, string.format("\n--- Output for Asset ID: %s ---", asset.identifier))
    if result.stdout and #result.stdout > 0 then
        log(Colours.GRAY, result.stdout)
    end
    if result.stderr and #result.stderr > 0 then
        log(Colours.YELLOW, result.stderr)
    end
    log(Colours.DARKGRAY, string.format("--- End of Output for Asset ID: %s ---\n", asset.identifier))

    if sdk.remove_dir then
        sdk.remove_dir(temp_addon_dir)
    end

    if result.exit_code ~= 0 then
        local message = result.stderr and #result.stderr > 0 and result.stderr:match("[^\n]*") or result.stdout or "Blender process reported failure"
        return { asset_id = asset.identifier, success = false, skipped = false, message = message }
    end

    return { asset_id = asset.identifier, success = true, skipped = false, message = string.format("Processed asset %s", asset.identifier) }
end

--- Remove a file path if it exists (safe no-op when helpers missing).
local function remove_file_if_exists(path)
    if path_exists(path) and sdk.remove_file then
        sdk.remove_file(path)
    end
end

local BlenderCore = {}

local function tableToString(t)
    if next(t) == nil then
        return "none"
    end
    local result = {}
    for k, v in pairs(t) do
        if type(v) == "table" then
            table.insert(result, tostring(k) .. "=" .. tableToString(v))
        else
            table.insert(result, tostring(k) .. "=" .. tostring(v))
        end
    end
    return "{" .. table.concat(result, ", ") .. "}"
end

--- Entry point for batch processing.
-- Validates resources, loads assets, processes sequentially, and summarizes.
-- Throws an error if any asset failed to process.
-- @param opts table (see module header for fields)
function BlenderCore.main(opts)
    opts = opts or {}
    VERBOSE = not not opts.verbose
    local debug_sleep = not not opts.debug_sleep
    local export_set, ordered_formats = normalize_export_formats(opts.export_formats)

    local db_path = opts.db_file_path and normalize_separators(opts.db_file_path)
    db_path = normalize_separators(db_path)
    if not db_path or db_path == "" then
        error("DB file path must be specified in opts.db_file_path")
        os.exit(1)
    end

    local main_db_path = opts.main_db and normalize_separators(opts.main_db) or ""
    local blender_exe_path = opts.blender_exe_path and normalize_separators(opts.blender_exe_path) or ""
    local game_root_path = opts.game_root and normalize_separators(opts.game_root)

    log(Colours.CYAN, "all input opts: " .. tableToString(opts))

    log(Colours.CYAN, string.format("Export formats: %s", (#ordered_formats > 0) and table.concat(ordered_formats, ", ") or "None"))
    log(Colours.CYAN, string.format("Using DB: %s", db_path))
    log(Colours.CYAN, string.format("Using main DB: %s", main_db_path))
    log(Colours.CYAN, string.format("Using Blender executable: %s", blender_exe_path))
    if not game_root_path then
        error("Game root path must be specified in opts.game_root_path")
        os.exit(1)
    end
    log(Colours.CYAN, string.format("Using game root path: %s", game_root_path))

    if not path_exists(blender_exe_path) then
        error(string.format("Blender executable not found: %s", blender_exe_path))
    end
    if not path_exists(python_script_path) then
        error(string.format("Python driver not found: %s", python_script_path))
    end
    if not path_exists(python_extension_file) then
        error(string.format("Python extension not found: %s", python_extension_file))
    end
    if not path_exists(db_path) then
        error(string.format("DB not found: %s", db_path))
    end

    local assets = load_assets(db_path)
    log(Colours.CYAN, string.format("Loaded %d assets from DB", #assets))

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

    local has_spawn = (sdk.spawn_process ~= nil)
    -- Default workers: user-specified opts.workers -> sdk.cpu_count -> 1
    local default_workers = 1
    if sdk and sdk.cpu_count then
        default_workers = tonumber(sdk.cpu_count) or default_workers
    end
    local max_workers = tonumber(opts.workers) or default_workers
    if max_workers < 1 then max_workers = 1 end

    if not has_spawn then
        -- Fallback: run sequentially using existing run_blender_for_asset implementation
        log(Colours.YELLOW, "spawn_process unavailable; running sequentially using sdk.run_process")
        for _, asset in ipairs(work_queue) do
            local rec = run_blender_for_asset(asset, export_set, ordered_formats, VERBOSE, debug_sleep, main_db_path, blender_exe_path, game_root_path)
            if rec.success then
                table.insert(successes, rec)
            else
                table.insert(failures, rec)
            end
        end
    else
        -- Concurrent execution using spawn/poll
        log(Colours.GREEN, string.format("Spawning up to %d workers using sdk.spawn_process", max_workers))

        local active = {} -- pid -> { asset=..., temp_dir=... }

        local function active_count()
            local c = 0
            for _ in pairs(active) do c = c + 1 end
            return c
        end

        local function start_next()
            if #work_queue == 0 then return end
            if active_count() >= max_workers then return end
            local asset = table.remove(work_queue, 1)

            -- build paths and basic checks (similar to run_blender_for_asset)
            local blend_file = join(asset.blend_symlink, asset.filename .. ".blend")
            if not is_file(blend_file) then
                table.insert(failures, { asset_id = asset.identifier, success = false, skipped = false, message = string.format("Blend file not found: %s", blend_file) })
                return
            end
            local glb_dir = asset.glb_symlink or ""
            local glb_file = join(glb_dir, asset.filename .. ".glb")
            local fbx_file = join(glb_dir, asset.filename .. ".fbx")
            local preinstanced_file = join(asset.preinstanced_symlink, asset.filename .. ".preinstanced")
            if not is_file(preinstanced_file) then
                table.insert(failures, { asset_id = asset.identifier, success = false, skipped = false, message = string.format("Preinstanced symlink missing: %s", preinstanced_file) })
                return
            end

            local temp_addon_dir = make_temp_dir("blender_addon_")

            local cmd = {
                blender_exe_path,
                "-b", blend_file,
                "--python", python_script_path,
                "--",
                blend_file,
                preinstanced_file,
                glb_file,
                python_extension_file,
                VERBOSE and "true" or "false",
                debug_sleep and "true" or "false",
                blender_dir,
                fbx_file,
                asset.identifier,
                temp_addon_dir,
                main_db_path,
                game_root_path,
                table.concat(ordered_formats, ",")
            }

            --log(Colours.DARKCYAN, string.format("Spawning process for asset %s with command: %s", tostring(asset.identifier), table.concat(cmd, " ")))

            local ok, res = pcall(function()
                return sdk.spawn_process(cmd, { capture_stdout = true, capture_stderr = true, cwd = nil })
            end)

            if not ok or not res or not res.pid then
                if sdk.remove_dir then pcall(sdk.remove_dir, temp_addon_dir) end
                local msg = "spawn failed"
                if not ok then msg = tostring(res) end
                table.insert(failures, { asset_id = asset.identifier, success = false, skipped = false, message = msg })
                return
            end

            local pid = res.pid
            active[pid] = { asset = asset, temp_dir = temp_addon_dir }
            log(Colours.DARKCYAN, string.format("Launched PID %s for asset %s", tostring(pid), tostring(asset.identifier)))
        end

        -- seed initial workers
        for i = 1, max_workers do start_next() end

        -- poll loop
        while next(active) ~= nil or #work_queue > 0 do
            -- start more if capacity
            while active_count() < max_workers and #work_queue > 0 do
                start_next()
            end

            -- poll active pids
            for pid, info in pairs(active) do
                local ok, pol = pcall(function() return sdk.poll_process(pid) end)
                if not ok then
                    -- treat as failure and cleanup
                    if sdk.remove_dir then pcall(sdk.remove_dir, info.temp_dir) end
                    table.insert(failures, { asset_id = info.asset.identifier, success = false, skipped = false, message = "poll failed: " .. tostring(pol) })
                    active[pid] = nil
                else
                    if not pol.running then
                        -- finished
                        if sdk.remove_dir then pcall(sdk.remove_dir, info.temp_dir) end

                        -- log captured output grouped by asset
                        if (pol.stderr and #pol.stderr > 0) or (pol.stdout and #pol.stdout > 0) then
                            log(Colours.DARKGRAY, string.format("\n--- Output for Asset ID: %s (PID %s) ---", info.asset.identifier, tostring(pid)))
                            if pol.stdout and #pol.stdout > 0 then log(Colours.GRAY, pol.stdout) end
                            if pol.stderr and #pol.stderr > 0 then log(Colours.YELLOW, pol.stderr) end
                            log(Colours.DARKGRAY, string.format("--- End of Output for Asset ID: %s ---\n", info.asset.identifier))
                        else
                            log(Colours.DARKGRAY, string.format("No output for Asset ID: %s (PID %s)", info.asset.identifier, tostring(pid)))
                        end

                        local exit_code = pol.exit_code or 1
                        if exit_code ~= 0 then
                            local message = (pol.stderr and #pol.stderr > 0 and pol.stderr:match("^[^\n]*")) or pol.stdout or "Blender process reported failure"
                            table.insert(failures, { asset_id = info.asset.identifier, success = false, skipped = false, message = message })
                        else
                            -- verify expected files
                            local ok_files = true
                            if export_set.glb and not is_file(join(info.asset.glb_symlink or "", info.asset.filename .. ".glb")) then
                                ok_files = false
                                table.insert(failures, { asset_id = info.asset.identifier, success = false, skipped = false, message = "GLB not produced" })
                            end
                            if export_set.fbx and not is_file(join(info.asset.glb_symlink or "", info.asset.filename .. ".fbx")) then
                                ok_files = false
                                table.insert(failures, { asset_id = info.asset.identifier, success = false, skipped = false, message = "FBX not produced" })
                            end
                            if ok_files then
                                table.insert(successes, { asset_id = info.asset.identifier, success = true, skipped = false, message = string.format("Processed asset %s", info.asset.identifier) })
                            end
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

    -- Summarize and error on failures (same behaviour as before)
    log(Colours.CYAN, string.format("Successes: %d, Failures: %d, Skipped: %d", #successes, #failures, #skipped))
    if #failures > 0 then
        log(Colours.RED, "Some assets failed to process. See messages for details.")
        for _, f in ipairs(failures) do
            log(Colours.RED, string.format("Asset %s: %s", tostring(f.asset_id), tostring(f.message)))
        end
        error(string.format("%d asset(s) failed to process", #failures))
    end

    log(Colours.GREEN, "\nProcessing complete.")
end

return BlenderCore
