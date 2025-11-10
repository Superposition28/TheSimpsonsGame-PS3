--[[
Folder-batched Godot import with per-language sub-batches for audio.
- No temp projects
- No staging mirror
- No batch_* folders
- Preserves final res://assets/<TopFolder>/... paths so scene JSON stays valid

Lua port of init.py with equivalent behavior.
Runtime: Lua 5.1+ under RemakeEngine LuaScriptAction (MoonSharp)
Dependencies provided by engine (no fallbacks used):
 - lfs (shim)
 - dkjson (shim)
 - global `sdk` (EngineSdk bridge)
 - global `tool(name)` resolver
 - global `argv` args
 - global `progress(total, id?, label?)` -> Panel progress handle (Update/Complete)
 - global `script_progress(total, id?, label?)` -> Stage progress indicator

Expected folder structure (relative to this module root):
 - GameFiles/STROUT/<TopFolder>/... assets to import
   - Special case: GameFiles/STROUT/audiostreams/<Lang>/...
 - Game/GodotGame/<ProjectName>/ project output
 - Game/addons, Game/Scripts, Game/rootfiles copied into project before import
]]

local lfs = require("lfs")
local path_sep = package.config:sub(1,1)

-- Console colour names
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

-- Print via SDK colour_print (guaranteed by engine runtime)
local function colour_print(opts)
    sdk.colour_print(opts)
end

-- Inline logging to both console (SDK) and persistent file (godot-init.log)
local log_handle = nil
local function open_log(path)
    -- Ensure directory then open file via safe io shim
    ensure_dir(dirname(path))
    log_handle = io.open(path, "w")
end

local function close_log()
    if log_handle then
        pcall(function() log_handle:flush() end)
        pcall(function() log_handle:close() end)
    end
    log_handle = nil
end

local function write_log(level, msg)
    local ts = os.date("%Y-%m-%d %H:%M:%S")
    local line = string.format("[%s] %-5s %s\n", ts, level, msg)
    if log_handle then
        pcall(function()
            log_handle:write(line)
            log_handle:flush()
        end)
    end
end

local function log_info(msg)
    colour_print{ colour = Colours.CYAN, message = msg }
    write_log("INFO", msg)
end

local function log_warn(msg)
    colour_print{ colour = Colours.YELLOW, message = msg }
    write_log("WARN", msg)
end

local function log_error(msg)
    -- Engine error event (UI/log panels)
    error(msg) -- mapped by engine to EngineSdk.Error
    colour_print{ colour = Colours.RED, message = msg }
    write_log("ERROR", msg)
end

-- Fatal helper: also raises a Lua error via assert to stop execution
local function fatal(msg)
    log_error(msg)
    assert(false, msg)
end

-- Small utils
local function join(a,b)
    if a:sub(-1) == path_sep then return a .. b end
    return a .. path_sep .. b
end

local function normalize(p)
    if not p then return p end
    if path_sep == "\\" then
        p = p:gsub("/", "\\")
    else
        p = p:gsub("\\", "/")
    end
    p = p:gsub("[/\\]+", path_sep)
    return p
end

local function dirname(p)
    if not p or p == "" then return "." end
    local d = p:match("(.+)[/\\][^/\\]+$") or p:match("(.+)[/\\]$") or ""
    if d == "" then return "." end
    return d
end

local function basename(p)
    return (p and p:match("([^/\\]+)$")) or p
end

local function ensure_dir(p)
    return sdk.ensure_dir(normalize(p))
end

local function file_exists(p)
    return sdk.path_exists(p)
end

local function is_dir(p)
    return sdk.is_dir(p)
end

local function is_file(p)
    return sdk.is_file(p)
end

local function get_file_size(p)
    local a = lfs.attributes(p)
    if a and a.mode == "file" then return a.size end
    return nil
end

-- May return false on missing; true if size equal and (if available) mtime comparable
local function nearly_same_file(src, dst)
    local sa = lfs.attributes(src)
    local da = lfs.attributes(dst)
    if not sa or not da then return false end
    if (sa.size or -1) ~= (da.size or -2) then return false end
    -- lfs shim exposes numeric 'modification'; accept equality if available
    if sa.modification and da.modification then
        return sa.modification == da.modification
    end
    return true
end

-- Compute SHA1; returns lowercase hex string or nil on failure
local function sha1(path)
    return sdk.sha1_file(normalize(path))
end

-- Compare two files for exact equality.
-- Strategy: quick size check -> SHA1 if available -> buffered byte-by-byte compare.
local function files_equal(src, dst)
    local ss = get_file_size(src)
    local ds = get_file_size(dst)
    if not ss or not ds or ss ~= ds then return false end
    -- Prefer hash comparison using SDK
    local h1, h2 = sha1(src), sha1(dst)
    if h1 and h2 then return h1 == h2 end
    -- If hashing unavailable, assume equal when sizes match (SDK guarantees stable copy)
    return true
end

local function countdown(sec)
    sec = tonumber(sec) or 0
    while sec > 0 do
        colour_print{ colour = Colours.CYAN, message = string.format("Waiting... %d seconds remaining.", sec) }
        sdk.sleep(1)
        sec = sec - 1
    end
end

-- Build a safely quoted command line for the current platform
local function build_cmdline(args)
    local parts = {}
    for i = 1, #args do
        local a = tostring(args[i])
        if path_sep == "\\" then
            -- Windows CMD quoting: wrap in double quotes and double any embedded quotes
            if a:find('%s') or a:find('["&|<>^]') then
                a = '"' .. a:gsub('"', '""') .. '"'
            end
        else
            -- POSIX: single-quote, escape single quotes by closing/opening
            if a:find('%s') or a:find('["\'$]') then
                a = "'" .. a:gsub("'", "'\\''") .. "'"
            end
        end
        parts[#parts + 1] = a
    end
    return table.concat(parts, " ")
end

-- Command runner backed by engine SDK (C#). Streams output and returns true on exit code 0.
-- Options:
--   opts.new_terminal: open in a new terminal window (best-effort per OS)
--   opts.keep_open: keep new terminal open after completion
--   opts.cwd: working directory
--   opts.env: table of env vars
local function run_cmd(args, opts)
    opts = opts or {}
    local cmdline = build_cmdline(args)
    colour_print{ colour = Colours.CYAN, message = "Exec: " .. cmdline }
    local res = sdk.exec(args, {
        cwd = opts.cwd,
        env = opts.env,
        new_terminal = opts.new_terminal == true,
        keep_open = opts.keep_open == true,
        wait = opts.wait ~= false,
    })
    return res and res.success == true
end

-- Godot helper
local function run_godot(command, label)
    log_info(string.format("\n--- %s ---", label))
    log_info("Command: " .. build_cmdline(command))
    local ok = run_cmd(command)
    if not ok then
        log_error(string.format("Godot command failed during '%s'", label))
    end
    log_info(string.format("--- %s finished ---", label))
end

-- File ops
local function copy_file(src, dst)
    ensure_dir(dirname(dst))
    -- Use SDK copy_file (guaranteed by engine runtime). Validate afterward.
    local ok = sdk.copy_file(src, dst, true)
    if not ok then
        fatal(string.format("SDK copy failed: '%s' -> '%s'", src, dst))
    end
    if not files_equal(src, dst) then
        fatal(string.format("Copy validation failed: '%s' -> '%s'", src, dst))
    end
end

local function remove_file(path)
    sdk.remove_file(path)
end

local function try_hardlink(src, dst)
    -- returns true on success, false otherwise
    remove_file(dst)
    ensure_dir(dirname(dst))
    return sdk.create_hardlink(src, dst) == true
end

-- Walk a directory tree (breadth-first) and call cb(absPath, relPath, filename) for each file
local function walk_files(root, cb)
    root = normalize(root)
    local function walk_dir(dir, rel)
        local iter = lfs.dir(dir)
        if not iter then return end
        for name in iter do
            if name ~= "." and name ~= ".." then
                local ap = join(dir, name)
                local rp = rel and join(rel, name) or name
                local a = lfs.attributes(ap)
                if a and a.mode == "directory" then
                    walk_dir(ap, rp)
                elseif a and a.mode == "file" then
                    cb(ap, rp, name)
                end
            end
        end
    end
    walk_dir(root, nil)
end

-- Copy/hardlink files from src_root -> dst_root, preserving structure.
-- Only copy when changed. Returns a stats table.
-- Cross-platform and case-aware: optionally detects case-collisions on case-insensitive filesystems.
--
-- Parameters (opts table):
--   use_hardlinks (bool, default true)
--   verify_hash_for_large (bool, default true)
--   large_bytes_threshold (number, default 50 MiB)
--   exts (array of extensions like {".png", ".glb"})
--   dry_run (bool) -> logs actions without writing
--   progress_handle (userdata from progress()) -> updated per processed file
--   case_insensitive (bool) -> treat destination as case-insensitive and detect collisions
--   log_sample_actions (integer) -> print first N planned actions to console; full list goes to log
local function copy_tree_incremental(src_root, dst_root, opts)
    opts = opts or {}
    local use_hardlinks = (opts.use_hardlinks ~= false)
    local verify_hash_for_large = (opts.verify_hash_for_large ~= false)
    local large_bytes_threshold = opts.large_bytes_threshold or (50 * 1024 * 1024)
    local dry_run = (opts.dry_run == true)
    local progress_handle = opts.progress_handle
    local case_insensitive = (opts.case_insensitive == true)
    local log_sample_actions = tonumber(opts.log_sample_actions or 50) or 50

    local extset = nil
    if opts.exts and #opts.exts > 0 then
        extset = {}
        for _,e in ipairs(opts.exts) do extset[e:lower()] = true end
    end

    -- Scan first to build a list and compute total bytes for ETA
    local files = {}
    local lower_map = {}
    local total_bytes = 0
    walk_files(src_root, function(src, rel, fn)
        if extset then
            local low = fn:lower()
            local match = false
            for e,_ in pairs(extset) do
                if low:sub(-#e) == e then match = true break end
            end
            if not match then return end
        end
        local a = lfs.attributes(src)
        local sz = (a and a.size) or 0
        table.insert(files, { src = src, rel = rel, size = sz })
        total_bytes = total_bytes + sz
        if case_insensitive then
            local low = rel:lower()
            if lower_map[low] then
                log_error(string.format("Case collision detected on destination: '%s' vs '%s'", lower_map[low], rel))
            else
                lower_map[low] = rel
            end
        end
    end)

    -- Stats
    local stats = {
        total_seen = #files,
        total_bytes = total_bytes,
        copied = 0,
        hardlinked = 0,
        skipped_identical = 0,
        bytes_copied = 0,
        bytes_skipped = 0,
        errors = 0,
        actions = {}, -- for dry-run preview
    }

    if progress_handle then progress_handle:Update(0) end

    -- Ensure destination root (skip for dry-run to avoid writes)
    if not dry_run then ensure_dir(dst_root) end

    -- Throttled ETA display
    local start_clock = os.clock()
    local last_eta_print = start_clock
    local processed_bytes = 0

    local function maybe_print_eta(processed_count)
        local now = os.clock()
        if now - last_eta_print < 1.0 then return end
        last_eta_print = now
        local elapsed = now - start_clock
        if elapsed <= 0.0 then return end
        local rate = processed_bytes / elapsed -- bytes/sec
        if rate <= 1 then return end
        local remain = math.max(0, total_bytes - processed_bytes)
        local eta = remain / rate
        local mm = math.floor(eta / 60)
        local ss = math.floor(eta % 60)
        colour_print{ colour = Colours.GRAY, message = string.format("Progress: %d/%d, ETA ~ %02d:%02d", processed_count, stats.total_seen, mm, ss) }
    end

    -- Evaluate and copy/link
    local sample_emitted = 0
    for idx, item in ipairs(files) do
        local src = item.src
        local rel = item.rel
        local sz  = item.size or 0
        local dst = join(dst_root, rel)

        -- Skip identical quickly
        if file_exists(dst) and nearly_same_file(src, dst) then
            stats.skipped_identical = stats.skipped_identical + 1
            stats.bytes_skipped = stats.bytes_skipped + sz
        else
            -- For large equal-sized files, verify by hash if enabled
            local do_copy = true
            if file_exists(dst) and verify_hash_for_large then
                local ds = get_file_size(dst)
                if ds and ds == sz and sz >= large_bytes_threshold then
                    local h1 = sha1(src)
                    local h2 = sha1(dst)
                    if h1 and h2 and h1 == h2 then
                        do_copy = false
                        stats.skipped_identical = stats.skipped_identical + 1
                        stats.bytes_skipped = stats.bytes_skipped + sz
                    end
                end
            end

            if do_copy then
                local action = use_hardlinks and "link" or "copy"
                local at = string.format("%s: %s -> %s", action, src, dst)
                table.insert(stats.actions, at)
                if dry_run then write_log("INFO", at) end
                if not dry_run then
                    local ok = false
                    if use_hardlinks then
                        ok = try_hardlink(src, dst)
                        if ok then stats.hardlinked = stats.hardlinked + 1 end
                    end
                    if not ok then
                        local ok2, err = pcall(copy_file, src, dst)
                        if not ok2 then
                            stats.errors = stats.errors + 1
                            log_warn(string.format("Copy failed '%s' -> '%s': %s", src, dst, tostring(err)))
                        else
                            stats.copied = stats.copied + 1
                            stats.bytes_copied = stats.bytes_copied + sz
                        end
                    else
                        stats.bytes_copied = stats.bytes_copied + sz
                    end
                else
                    -- Dry-run: treat as would-copy
                    stats.copied = stats.copied + 1
                    stats.bytes_copied = stats.bytes_copied + sz
                end
            end
        end

        processed_bytes = processed_bytes + sz
        if progress_handle then progress_handle:Update(1) end
        maybe_print_eta(idx)

        if dry_run and sample_emitted < log_sample_actions then
            colour_print{ colour = Colours.GRAY, message = stats.actions[#stats.actions] or "" }
            sample_emitted = sample_emitted + 1
        end
    end

    if progress_handle and stats.total_seen > 0 then progress_handle:Update(0) end
    return stats
end

-- Constants
local AUDIO_TOP = "audiostreams"
local AUDIO_LANG_FOLDERS = { EN=true, ES=true, FR=true, IT=true, Global=true }

-- Create and import Godot project
local function create_godot_project(project_name, project_path, extracted_root, scripts_folder, addons_folder, conf_folder, godot_exe, no_exit, logo_images, asset_exts, dry_run)
    local project_dir = join(project_path, project_name)
    if not dry_run then ensure_dir(project_dir) end
    log_info("Godot Project Directory: " .. project_dir)

    -- Open log (project-local)
    local project_log = join(project_dir, "godot-init.log")
    if not dry_run then open_log(project_log) end
    write_log("INFO", string.format("init.lua started for project '%s'", project_name))

    -- project.godot from conf template
    local proj_file = join(project_dir, "project.godot")
    --if not file_exists(proj_file) then
    --    local conf_path = normalize(join(dirname(project_path), join("conf", "project.godot")))
    --    local inf, err = io.open(conf_path, "r")
    --    if not inf then error("Cannot open conf template: " .. tostring(err)) end
    --    local content = inf:read("*a") or ""
    --    inf:close()
    --    local outf = assert(io.open(proj_file, "w"))
    --    outf:write(content)
    --    outf:close()
    --    colour_print{ colour = Colours.CYAN, message = "Created project.godot" }
    --end

    local assets_dst_root = join(project_dir, "assets")
    if not dry_run then ensure_dir(assets_dst_root) end

    -- Copy addons, scene_config.json and tool scripts early so they are available
    -- during per-batch headless imports. This was previously done after
    -- importing assets; move it here to ensure tools/scripts are present.
    if addons_folder and is_dir(addons_folder) then
        -- copy tree into project_dir/addons (dirs_exist_ok)
        local dst = join(project_dir, "addons")
        local function copytree(src, dstroot)
            walk_files(src, function(ap, rp, _)
                local outp = join(dstroot, rp)
                if not dry_run then
                    ensure_dir(dirname(outp))
                    local ok, err = pcall(copy_file, ap, outp)
                    if not ok then
                        log_warn(string.format("Addon copy failed '%s' -> '%s': %s", ap, outp, tostring(err)))
                    end
                else
                    -- dry-run preview
                    write_log("INFO", string.format("addon copy: %s -> %s", ap, outp))
                end
            end)
        end
        copytree(addons_folder, dst)
        log_info("Prepared addons in project before asset import (" .. (dry_run and "dry-run" or "copied") .. ")")
    end

    if conf_folder and is_dir(conf_folder) then
        local dst = project_dir -- copy conf contents into project root
        local function copytree(src, dstroot)
            walk_files(src, function(ap, rp, _)
                local outp = join(dstroot, rp)
                if not dry_run then
                    ensure_dir(dirname(outp))
                    local ok, err = pcall(copy_file, ap, outp)
                    if not ok then
                        log_warn(string.format("Conf copy failed '%s' -> '%s': %s", ap, outp, tostring(err)))
                    end
                else
                    write_log("INFO", string.format("conf copy: %s -> %s", ap, outp))
                end
            end)
        end
        copytree(conf_folder, dst)
        log_info("Prepared conf files in project root (" .. (dry_run and "dry-run" or "copied") .. ")")
    end

    if scripts_folder and is_dir(scripts_folder) then
        local scripts_dst = join(project_dir, "Scripts")
        local function copytree(src, dstroot)
            walk_files(src, function(ap, rp, _)
                local outp = join(dstroot, rp)
                if not dry_run then
                    ensure_dir(dirname(outp))
                    local ok, err = pcall(copy_file, ap, outp)
                    if not ok then
                        log_warn(string.format("Script copy failed '%s' -> '%s': %s", ap, outp, tostring(err)))
                    end
                else
                    write_log("INFO", string.format("script copy: %s -> %s", ap, outp))
                end
            end)
        end
        copytree(scripts_folder, scripts_dst)
        log_info("Prepared scene_config.json and tool scripts (" .. (dry_run and "dry-run" or "copied") .. ")")
    end

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

    -- Discover top-level folders under ExtractedOut
    local top_folders = {}
    local it = lfs.dir(extracted_root)
    if it then
        for d in it do
            if d ~= "." and d ~= ".." then
                local p = join(extracted_root, d)
                if is_dir(p) then table.insert(top_folders, d) end
            end
        end
    end
    table.sort(top_folders)

    log_info("Top-level batches " .. tableToString(top_folders))

    if next(top_folders) == nil then
        log_warn("No top-level batches found; exiting.")
        close_log()
        return
    end

    -- Confirm potentially destructive operations once per run
    local confirm_overwrite = true
    if not dry_run then
        -- If destination contains existing assets, prompt for confirmation
        local assets_exists = is_dir(assets_dst_root)
        if assets_exists then
            local ans = prompt("Assets already exist in project; files may be overwritten. Continue? (y/N)", "confirm_overwrite", false)
            if not ans or (ans:lower() ~= "y" and ans:lower() ~= "yes") then
                log_warn("Operation cancelled by user before copying assets.")
                close_log()
                return
            end
        end
    else
        log_info("Dry-run mode: no files will be created, removed or modified.")
    end

    local case_insensitive = (path_sep == "\\") or false -- assume Windows as case-insensitive

    for batch_idx, top in ipairs(top_folders) do
        local src_top = join(extracted_root, top)
        if top == AUDIO_TOP then
            -- sub-batch by language folders
            local langs = {}
            local it2 = lfs.dir(src_top)
            if it2 then
                for name in it2 do
                    if name ~= "." and name ~= ".." then
                        local p = join(src_top, name)
                        if is_dir(p) then table.insert(langs, name) end
                    end
                end
            end
            table.sort(langs, function(a,b)
                local aa = not not AUDIO_LANG_FOLDERS[a]
                local bb = not not AUDIO_LANG_FOLDERS[b]
                if aa ~= bb then return aa end
                return a < b
            end)

            for _,lang in ipairs(langs) do
                local src_lang = join(src_top, lang)
                local dst_lang = join(join(assets_dst_root, top), lang)
                if not dry_run then ensure_dir(dst_lang) end

                -- gate with .gdignore during placement
                local gdignore_path = join(dst_lang, ".gdignore")
                if not dry_run then local f = io.open(gdignore_path, "a"); if f then f:close() end end

                log_info(string.format("\n=== Batch %d: %s/%s ===", batch_idx, top, lang))

                -- Progress for file copy
                local list_counter = { count = 0 }
                walk_files(src_lang, function(ap, rp, fn)
                    if asset_exts then
                        local low = fn:lower(); local match=false; for _,e in ipairs(asset_exts) do if low:sub(-#e) == e then match=true; break end end; if not match then return end
                    end
                    list_counter.count = list_counter.count + 1
                end)
                local p = progress(list_counter.count, "copy_"..top.."_"..lang, string.format("Copy %s/%s", top, lang))
                local stats = copy_tree_incremental(src_lang, dst_lang, {
                    use_hardlinks = true,
                    verify_hash_for_large = true,
                    large_bytes_threshold = 50*1024*1024,
                    exts = asset_exts,
                    dry_run = dry_run,
                    progress_handle = p,
                    case_insensitive = case_insensitive,
                    log_sample_actions = 50,
                })
                p:Complete()

                log_info(string.format("Placed %d file(s), copied %d, hardlinked %d, skipped %d, bytes copied %.2f MiB", stats.total_seen, stats.copied, stats.hardlinked, stats.skipped_identical, stats.bytes_copied / (1024*1024)))

                if not dry_run then remove_file(gdignore_path) end

                if not dry_run then
                    run_godot({ godot_exe, "--headless", "--path", project_dir, "--import", "-v", "--quit" }, string.format("Headless Import: %s/%s", top, lang))
                end
            end
        else
            local dst_top = join(assets_dst_root, top)
            if not dry_run then ensure_dir(dst_top) end
            local gdignore_path = join(dst_top, ".gdignore")
            if not dry_run then local f = io.open(gdignore_path, "a"); if f then f:close() end end

            log_info(string.format("\n=== Batch %d: %s ===", batch_idx, top))

            local list_counter = { count = 0 }
            walk_files(src_top, function(ap, rp, fn)
                if asset_exts then local low = fn:lower(); local match=false; for _,e in ipairs(asset_exts) do if low:sub(-#e) == e then match=true; break end end; if not match then return end end
                list_counter.count = list_counter.count + 1
            end)
            local p = progress(list_counter.count, "copy_"..top, string.format("Copy %s", top))
            local stats = copy_tree_incremental(src_top, dst_top, {
                use_hardlinks = true,
                verify_hash_for_large = true,
                large_bytes_threshold = 50*1024*1024,
                exts = asset_exts,
                dry_run = dry_run,
                progress_handle = p,
                case_insensitive = case_insensitive,
                log_sample_actions = 50,
            })
            p:Complete()

            log_info(string.format("Placed %d file(s), copied %d, hardlinked %d, skipped %d, bytes copied %.2f MiB", stats.total_seen, stats.copied, stats.hardlinked, stats.skipped_identical, stats.bytes_copied / (1024*1024)))

            if not dry_run then remove_file(gdignore_path) end

            if not dry_run then
                run_godot({ godot_exe, "--headless", "--path", project_dir, "--import", "-v", "--quit" }, string.format("Headless Import: %s", top))
            end
        end
    end

    log_info("\nAssets are ready. Preparing to run tool scripts.")
    if not dry_run then countdown(1) end

    -- (Addons and scripts were copied earlier to ensure availability during imports.)

    -- Logos
    if logo_images and #logo_images > 0 then
        local logos_dst = join(project_dir, "logos")
        if not dry_run then ensure_dir(logos_dst) end
        for _,f in ipairs(logo_images) do
            local target = join(logos_dst, basename(f))
            if not dry_run then
                local ok, err = pcall(copy_file, f, target)
                if not ok then
                    log_warn(string.format("Logo copy failed '%s' -> '%s': %s", f, target, tostring(err)))
                end
            else
                write_log("INFO", string.format("logo copy: %s -> %s", f, target))
            end
        end
    end

    -- Run scene builder
    if not dry_run then
        local cmd = { godot_exe, "--editor", "--path", project_dir, "--script", "res://Scripts/_BuildScenes.gd" }
        if no_exit then table.insert(cmd, "--no-exit"); log_info("\n'--no-exit' flag detected. Godot will remain open after script execution.") end
        run_godot(cmd, "Scene Building")
        log_info("\n✅✅✅ Godot project setup and scene generation complete! ✅✅✅")
        countdown(1)
    else
        log_info("Dry-run complete. No Godot commands executed.")
    end

    close_log()
end

-- CLI
local function parse_args(argv)
    local opts = { ["project-name"] = "Game", ["no-exit"] = false, ["dry-run"] = false }
    local i = 1
    while i <= #argv do
        local a = argv[i]
        if a == "--project-name" and argv[i+1] then
            opts["project-name"] = argv[i+1]; i = i + 2
        elseif a == "--repo-root" and argv[i+1] then
            opts["repo-root"] = argv[i+1]; i = i + 2
        elseif a == "--no-exit" then
            opts["no-exit"] = true; i = i + 1
        elseif a == "--sourcePath" and argv[i+1] then
            opts["sourcePath"] = argv[i+1]; i = i + 2
        elseif a == "--dry-run" then
            opts["dry-run"] = true; i = i + 1
        else
            -- unknown or trailing
            i = i + 1
        end
    end
    return opts
end

local function resolve_godot()
    -- Engine tool resolver is guaranteed by runtime
    return tool("Godot")
end

-- Discover PNG files only in the specified directory (non-recursive)
local function discover_pngs_in_dir(dir)
    local list = {}
    if not dir or dir == "" then return list end
    dir = normalize(dir)
    local it = lfs.dir(dir)
    if not it then return list end
    for name in it do
        if name ~= "." and name ~= ".." then
            local p = join(dir, name)
            local a = lfs.attributes(p)
            if a and a.mode == "file" then
                if name:lower():sub(-4) == ".png" then
                    table.insert(list, p)
                end
            end
        end
    end
    return list
end

local function main(project_name, repo_root, no_exit, sourcePath, dry_run)
    -- Locate this module directory
    local this_source = debug and debug.getinfo and debug.getinfo(1, 'S')
    local this_path = this_source and this_source.source or ""
    if this_path:sub(1,1) == "@" then this_path = this_path:sub(2) end
    local godot_module_root = dirname(this_path)
    local module_root = dirname(godot_module_root)

    -- Open a bootstrap log in module root immediately (independent from project log)
    local bootstrap_log = join(godot_module_root, "godot-init.log")
    if not dry_run then open_log(bootstrap_log) end
    write_log("INFO", "bootstrap logging started")

    log_info("Godot Module Root: " .. godot_module_root)
    log_info("Repository Root: " .. repo_root)

    local extracted_root = join(join(module_root, "GameFiles"), "STROUT")
    -- for testing use temp dir for game files
    --local extracted_root = join(godot_module_root, "assets")
    log_info("Using Extracted Root: " .. extracted_root)
    local scripts_folder = join(godot_module_root, "Scripts")
    local addons_folder = join(godot_module_root, "addons")
    local conf_folder = join(godot_module_root, "rootfiles")
    local project_parent = join(godot_module_root, "GodotGame")

    local godot_exe = resolve_godot()

    -- Pre-flight validations
    local stage = script_progress(6, "preflight", "Pre-flight checks")
    -- 1. Validate Godot tool
    if not godot_exe or godot_exe == "" or not is_file(godot_exe) then
        fatal("Godot executable not found. Ensure 'Godot' tool is configured.")
    end
    stage:Update(1)
    -- 2. Godot version check (fast)
    local ok_version = sdk.execSilent({ godot_exe, "--version" }, { wait = true })
    if not (ok_version and ok_version.success == true) then
        log_warn("Unable to validate Godot via '--version'. Continuing, but import may fail.")
    end
    stage:Update(1)
    -- 3. Source root exists
    if not is_dir(extracted_root) then
        fatal("Extracted source root not found: " .. extracted_root)
    end
    stage:Update(1)
    -- 4. Optional folders logged
    if not is_dir(scripts_folder) then log_warn("Scripts folder not found: " .. scripts_folder) end
    stage:Update(1)
    if not is_dir(addons_folder) then log_warn("Addons folder not found: " .. addons_folder) end
    stage:Update(1)
    if not is_dir(conf_folder) then log_warn("Conf folder not found: " .. conf_folder) end
    stage:Update(1)
    -- Close preflight stage
    stage:Complete()

    local asset_exts = { ".png", ".glb", ".wav", ".ogv" }

    local logos = {}
    local ok, err = pcall(function()
        -- logo discovery
        local logo_dir = join(module_root, "Source")
        if is_dir(logo_dir) then
            logos = discover_pngs_in_dir(logo_dir)
        else
            log_warn("Logo directory not found: " .. logo_dir)
            logos = {}
        end
        if #logos > 0 then
            log_info("Found game logo images: " .. table.concat(logos, ", "))
        end
    end)
    if not ok then
        log_warn("Logo scan warning: " .. tostring(err))
    end

    create_godot_project(project_name, project_parent, extracted_root, scripts_folder, addons_folder, conf_folder, godot_exe, no_exit, logos, asset_exts, dry_run)
    -- Close bootstrap log if still open (create_godot_project opens a project-local log and then closes it)
    close_log()
end

-- Entrypoint (when executed as a script by the engine)
local function run()
    -- argv is guaranteed by engine runtime
    local opts = parse_args(argv)
    if not opts["repo-root"] or not opts["sourcePath"] then
        fatal("Missing required args: --repo-root and --sourcePath")
    end
    main(opts["project-name"], normalize(opts["repo-root"]), opts["no-exit"], normalize(opts["sourcePath"]), opts["dry-run"])
end

if ... == nil then
    run()
end

return {
    main = main,
    run = run,
}
