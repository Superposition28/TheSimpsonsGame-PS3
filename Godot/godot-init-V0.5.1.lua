-- EngineApps/Games/TheSimpsonsGame-PS3/Godot\Game\godot-init-V0.5.1.lua
--[[
Folder-batched Godot import with per-language sub-batches for audio.
- No temp projects
- No staging mirror
- No batch_* folders
- Preserves final res://assets/<TopFolder>/... paths so scene JSON stays valid

Lua port of init.py with equivalent behavior.
Runtime: Lua 5.1+ under RemakeEngine LuaScriptAction (MoonSharp)
Dependencies provided by engine (no fallbacks used):
    - sdk (EngineSdk bridge)
    - Diagnostics (Logging bridge)
    - tool(name) resolver
    - argv args
    - progress.new(total, id?, label?) -> Panel progress handle (Update/Complete)
    - script_progress(total, id?, label?) -> Stage progress indicator

Expected folder structure (relative to this module root):
    - GameFiles/STROUT/<TopFolder>/... assets to import
        - Special case: GameFiles/STROUT/audiostreams/<Lang>/...
    - Game/GodotGame/<ProjectName>/ project output
    - Game/addons, Game/Scripts, Game/rootfiles copied into project before import
]]

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

-- # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
-- # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

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

-- Inline logging to console (SDK) and engine diagnostics
local function log_info(msg)
    sdk.colour_print{ colour = Colours.CYAN, message = msg }
    Diagnostics.Log("[godot-init] INFO: " .. msg)
end

local function log_warn(msg)
    sdk.colour_print{ colour = Colours.YELLOW, message = msg }
    Diagnostics.Log("[godot-init] WARN: " .. msg)
    warn(msg)
end

local function log_error(msg)
    -- Engine error event (UI/log panels)
    sdk.colour_print{ colour = Colours.RED, message = msg }
    Diagnostics.Log("[godot-init] ERROR: " .. msg)
    error(msg) -- mapped by engine to EngineSdk.Error
end

-- Fatal helper: also raises a Lua error via assert to stop execution
local function fatal(msg)
    log_error(msg)
    assert(false, msg)
end

local function basename(p)
    return (p and p:match("([^/\\]+)$")) or p
end

local function get_file_size(p)
    local a = sdk.attributes(p)
    if a and a.mode == "file" then return a.size end
    return nil
end

-- May return false on missing; true if size equal and (if available) mtime comparable
local function nearly_same_file(src, dst)
    local sa = sdk.attributes(src)
    local da = sdk.attributes(dst)
    if not sa or not da then return false end
    if (sa.size or -1) ~= (da.size or -2) then return false end
    -- sdk.attributes exposes numeric 'modification' (Unix timestamp)
    if sa.modification and da.modification then
        return sa.modification == da.modification
    end
    return true
end

-- Compare two files for exact equality.
-- Strategy: quick size check -> SHA1 if available -> buffered byte-by-byte compare.
local function files_equal(src, dst)
    local ss = get_file_size(src)
    local ds = get_file_size(dst)
    if not ss or not ds or ss ~= ds then return false end
    -- Prefer hash comparison using SDK
    local h1, h2 = sdk.sha1_file(normalize(src)), sdk.sha1_file(normalize(dst))
    if h1 and h2 then return h1 == h2 end
    -- If hashing unavailable, assume equal when sizes match (SDK guarantees stable copy)
    return true
end

local function countdown(sec)
    sec = tonumber(sec) or 0
    while sec > 0 do
        sdk.colour_print{ colour = Colours.CYAN, message = string.format("Waiting... %d seconds remaining.", sec) }
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
    sdk.colour_print{ colour = Colours.CYAN, message = "Exec: " .. cmdline }
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
    src = normalize(src)
    dst = normalize(dst)
    sdk.ensure_dir(dirname(dst))
    local ok = sdk.copy_file(src, dst, true)
    if not ok then
        fatal(string.format("SDK copy failed: '%s' -> '%s'", src, dst))
    end
    if not files_equal(src, dst) then
        fatal(string.format("Copy validation failed: '%s' -> '%s'", src, dst))
    end
end

local function try_hardlink(src, dst)
    -- returns true on success, false otherwise
    sdk.remove_file(dst)
    sdk.ensure_dir(normalize(dirname(dst)))
    return sdk.create_hardlink(src, dst) == true
end

-- Walk a directory tree (breadth-first) and call cb(absPath, relPath, filename) for each file
local function walk_files(root, cb)
    root = normalize(root)
    local function walk_dir(dir, rel)
        local entries = sdk.list_dir(dir)
        if not entries then return end
        for i = 1, #entries do
            local name = entries[i]
            if name ~= "." and name ~= ".." then
                local ap = join(dir, name)
                local rp = rel and join(rel, name) or name
                local a = sdk.attributes(ap)
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
--   progress_handle (userdata from progress()) -> updated per processed file
--   case_insensitive (bool) -> treat destination as case-insensitive and detect collisions
--   log_sample_actions (integer) -> print first N planned actions to console; full list goes to log
local function copy_tree_incremental(src_root, dst_root, opts)
    opts = opts or {}
    local use_hardlinks = (opts.use_hardlinks ~= false)
    local verify_hash_for_large = (opts.verify_hash_for_large ~= false)
    local large_bytes_threshold = opts.large_bytes_threshold or (50 * 1024 * 1024)
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
        local a = sdk.attributes(src)
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
        actions = {},
    }

    if progress_handle then progress_handle:Update(0) end

    -- Ensure destination root
    sdk.ensure_dir(normalize(dst_root))

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
        sdk.colour_print{ colour = Colours.GRAY, message = string.format("Progress: %d/%d, ETA ~ %02d:%02d", processed_count, stats.total_seen, mm, ss) }
    end

    -- Evaluate and copy/link
    local sample_emitted = 0
    for idx, item in ipairs(files) do
        local src = item.src
        local rel = item.rel
        local sz  = item.size or 0
        local dst = join(dst_root, rel)

        -- Skip identical quickly
        if sdk.path_exists(dst) and nearly_same_file(src, dst) then
            stats.skipped_identical = stats.skipped_identical + 1
            stats.bytes_skipped = stats.bytes_skipped + sz
        else
            -- For large equal-sized files, verify by hash if enabled
            local do_copy = true
            if sdk.path_exists(dst) and verify_hash_for_large then
                local ds = get_file_size(dst)
                if ds and ds == sz and sz >= large_bytes_threshold then
                    local h1 = sdk.sha1_file(normalize(src))
                    local h2 = sdk.sha1_file(normalize(dst))
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

            end
        end

        processed_bytes = processed_bytes + sz
        if progress_handle then progress_handle:Update(1) end
        maybe_print_eta(idx)
    end

    if progress_handle and stats.total_seen > 0 then progress_handle:Update(0) end
    return stats
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


-- # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
-- # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #


local function resolve_godot()
    local tool_fn = rawget(_G, "tool")
    local p = tool_fn("Godot")
    if p and p ~= "" then return p end
    fatal("Godot executable not found via tool('Godot'); ensure Godot is installed and configured in the engine.")
end

-- Helper to extract parent directory using string patterns
local function get_parent_directory(path)
    if not path then return nil end
    -- Normalize to forward slashes for easier matching
    path = path:gsub("\\", "/")
    -- Remove trailing slash if present (e.g. "path/to/dir/" -> "path/to/dir")
    if path:sub(-1) == "/" then
        path = path:sub(1, -2)
    end
    -- Capture everything up to the last slash
    local parent = path:match("^(.*)/[^/]+$")
    return parent
end

local function discover_pngs_in_dir(dir)
    local list = {}
    if not dir or dir == "" then return list end
    dir = normalize(dir)
    log_info("Scanning for logo images in: " .. dir)

    -- Using sdk.list_dir from LuaSdkModule.cs
    local entries = sdk.list_dir(dir)
    if not entries then return list end

    for i = 1, #entries do
        local name = entries[i]
        if name ~= "." and name ~= ".." then
            local p = join(dir, name)
            -- Using sdk.attributes from LuaSdkModule.cs
            local a = sdk.attributes(p)
            if a and a.mode == "file" then
                if name:lower():sub(-4) == ".png" then
                    table.insert(list, p)
                end
            end
        end
    end
    return list
end

local function get_logos(iconPath)
    local logos = {}
    local ok, err = pcall(function()
        local logo_dir = iconPath

        -- 1. First Attempt: Check the specific iconPath
        if logo_dir and sdk.is_dir(logo_dir) then
            logos = discover_pngs_in_dir(logo_dir)
        elseif logo_dir then
            log_warn("Logo directory not found: " .. logo_dir)
        end

        -- 2. Fallback Attempt: If no logos found, check the parent directory
        if #logos == 0 and logo_dir then
            local parent_dir = get_parent_directory(logo_dir)

            -- Ensure parent exists and is actually different from the original dir
            if parent_dir and parent_dir ~= logo_dir and sdk.is_dir(parent_dir) then
                log_info("No PNGs found in icon path. Checking parent directory: " .. parent_dir)
                logos = discover_pngs_in_dir(parent_dir)
            end
        end

        if #logos > 0 then
            log_info("Found game logo images: " .. table.concat(logos, ", "))
        end
    end)

    if not ok then
        log_warn("Logo scan warning: " .. tostring(err))
    end
    return logos
end


-- # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
-- # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #


-- Constants
local AUDIO_TOP1 = "audiostreams" -- source name
local AUDIO_TOP2 = "A1_Audio" -- renamed
-- Map of language folder names under audiostreams to whether they should be prioritized first (true) or later (false) in processing order.
local AUDIO_LANG_FOLDERS = { EN=true, ES=true, FR=true, IT=true, Global=true }

-- Create and import Godot project
local function create_godot_project(project_name, project_path, assetSourcePath, addons_folder, rootfiles, godot_exe, no_exit, logo_images, asset_exts)
    local project_dir = normalize(join(project_path, project_name))
    sdk.ensure_dir(project_dir)
    log_info("Godot Project Directory: " .. project_dir)

    -- Engine diagnostics replaces local project log
    Diagnostics.Log(string.format("[godot-init] info: init.lua started for project '%s'", project_name))

    local assets_dst_root = normalize(join(project_dir, "assets"))

    -- Logos
    if logo_images and #logo_images > 0 then
        local logos_dst = normalize(join(project_dir, "logos"))
        sdk.ensure_dir(logos_dst)
        for _,f in ipairs(logo_images) do
            local ok, err = pcall(copy_file, f, join(logos_dst, basename(f)))
            if not ok then
                sdk.colour_print{ colour = Colours.YELLOW, message = string.format("Warn: logo copy failed '%s': %s", f, tostring(err)) }
            end
        end
        sdk.colour_print{ colour = Colours.BLUE, message = "Copied logo images into project." }
    end

    -- Copy addons, scene_config.json and tool scripts early so they are available
    -- during per-batch headless imports. This was previously done after
    -- importing assets; move it here to ensure tools/scripts are present.
    if addons_folder and sdk.is_dir(addons_folder) then
        -- copy tree into project_dir/addons (dirs_exist_ok)
        local dst = normalize(join(project_dir, "addons"))
        local function copytree(src, dstroot)
            walk_files(src, function(ap, rp, _)
                local outp = normalize(join(dstroot, rp))
                sdk.ensure_dir(dirname(outp))
                local ok, err = pcall(copy_file, ap, outp)
                if not ok then
                    log_warn(string.format("Warn: addon copy failed '%s' -> '%s': %s", ap, outp, tostring(err)))
                end
            end)
        end
        copytree(addons_folder, dst)
        log_info("Copied addons into project before asset import.")
    end

    if rootfiles and sdk.is_dir(rootfiles) then
        local dst = project_dir -- copy rootfiles contents into project root
        local function copytree(src, dstroot)
            walk_files(src, function(ap, rp, _)
                local outp = normalize(join(dstroot, rp))
                sdk.ensure_dir(dirname(outp))
                local ok, err = pcall(copy_file, ap, outp)
                if not ok then
                    log_warn(string.format("Warn: conf copy failed '%s' -> '%s': %s", ap, outp, tostring(err)))
                end
            end)
        end
        copytree(rootfiles, dst)
        log_info("Copied rootfiles contents into project root before asset import.")
    end

    -- Discover top-level folders under ExtractedOut
    local top_folders = {}
    local entries = sdk.list_dir(assetSourcePath)
    if entries then
        for i = 1, #entries do
            local d = entries[i]
            if d ~= "." and d ~= ".." then
                local p = normalize(join(assetSourcePath, d))
                if sdk.is_dir(p) then table.insert(top_folders, d) end
            end
        end
    end
    table.sort(top_folders)

    log_info("Top-level batches " .. tableToString(top_folders))

    if next(top_folders) == nil then
        log_warn("No top-level batches found; exiting.")
        return
    end

    -- Confirm potentially destructive operations once per run
    local confirm_overwrite = true
    local skip_import = false
    -- If destination contains existing assets, prompt for confirmation
    local existing_assets = sdk.list_dir(assets_dst_root)
    if existing_assets and #existing_assets > 0 then
        local ans = prompt("Assets already exist in project; files may be overwritten. Continue? (y/N)", "confirm_overwrite", false)
        if not ans or (ans:lower() ~= "y" and ans:lower() ~= "yes") then
            --log_info("Skipping asset copy and import.")
            --return
            skip_import = true
        end
    end

    -- Ensure destination root exists now
    sdk.ensure_dir(normalize(assets_dst_root))

    local case_insensitive = (path_sep == "\\") or false -- assume Windows as case-insensitive
    if skip_import then
        log_info("Skipping asset copy and import.")
    else
        for batch_idx, top in ipairs(top_folders) do
            local src_top = normalize(join(assetSourcePath, top))
            if top == AUDIO_TOP1 or top == AUDIO_TOP2 then
                -- sub-batch by language folders
                local langs = {}
                local entries2 = sdk.list_dir(src_top)
                if entries2 then
                    for i = 1, #entries2 do
                        local name = entries2[i]
                        if name ~= "." and name ~= ".." then
                            local p = normalize(join(src_top, name))
                            if sdk.is_dir(p) then table.insert(langs, name) end
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
                    local src_lang = normalize(join(src_top, lang))
                    local dst_lang = normalize(join(join(assets_dst_root, top), lang))
                    sdk.ensure_dir(dst_lang)

                    -- gate with .gdignore during placement
                    local gdignore_path = normalize(join(dst_lang, ".gdignore"))
                    sdk.write_file(gdignore_path, "")

                    log_info(string.format("\n=== Batch %d: %s/%s ===", batch_idx, top, lang))

                    -- Progress for file copy
                    local list_counter = { count = 0 }
                    walk_files(src_lang, function(ap, rp, fn)
                        if asset_exts then
                            local low = fn:lower(); local match=false; for _,e in ipairs(asset_exts) do if low:sub(-#e) == e then match=true; break end end; if not match then return end
                        end
                        list_counter.count = list_counter.count + 1
                    end)
                    local p = progress.new(list_counter.count, "copy_"..top.."_"..lang, string.format("Copy %s/%s", top, lang))
                    local stats = copy_tree_incremental(src_lang, dst_lang, {
                        use_hardlinks = true,
                        verify_hash_for_large = true,
                        large_bytes_threshold = 50*1024*1024,
                        exts = asset_exts,
                        progress_handle = p,
                        case_insensitive = case_insensitive,
                        log_sample_actions = 50,
                    })
                    p:Complete()

                    log_info(string.format("Placed %d file(s), copied %d, hardlinked %d, skipped %d, bytes copied %.2f MiB", stats.total_seen, stats.copied, stats.hardlinked, stats.skipped_identical, stats.bytes_copied / (1024*1024)))

                    sdk.remove_file(gdignore_path)

                    run_godot({ godot_exe, "--headless", "--path", project_dir, "--import", "-v", "--quit" }, string.format("Headless Import: %s/%s", top, lang))
                end
            else
                local dst_top = normalize(join(assets_dst_root, top))
                sdk.ensure_dir(dst_top)
                local gdignore_path = normalize(join(dst_top, ".gdignore"))
                sdk.write_file(gdignore_path, "")

                log_info(string.format("\n=== Batch %d: %s ===", batch_idx, top))

                local list_counter = { count = 0 }
                walk_files(src_top, function(ap, rp, fn)
                    if asset_exts then local low = fn:lower(); local match=false; for _,e in ipairs(asset_exts) do if low:sub(-#e) == e then match=true; break end end; if not match then return end end
                    list_counter.count = list_counter.count + 1
                end)
                local p = progress.new(list_counter.count, "copy_"..top, string.format("Copy %s", top))
                local stats = copy_tree_incremental(src_top, dst_top, {
                    use_hardlinks = true,
                    verify_hash_for_large = true,
                    large_bytes_threshold = 50*1024*1024,
                    exts = asset_exts,
                    progress_handle = p,
                    case_insensitive = case_insensitive,
                    log_sample_actions = 50,
                })
                p:Complete()

                log_info(string.format("Placed %d file(s), copied %d, hardlinked %d, skipped %d, bytes copied %.2f MiB", stats.total_seen, stats.copied, stats.hardlinked, stats.skipped_identical, stats.bytes_copied / (1024*1024)))

                sdk.remove_file(gdignore_path)

                run_godot({ godot_exe, "--headless", "--path", project_dir, "--import", "-v", "--quit" }, string.format("Headless Import: %s", top))
            end
        end
    end
    log_info("\nAssets are ready. Preparing to run tool scripts.")
    countdown(1)

    -- copy .json files from asset root folder into project assets folder
    -- open assetSourcePath and find all .json files (non-recursive) and copy them into assets_dst_root
    local entries = sdk.list_dir(assetSourcePath)
    if entries then
        for i = 1, #entries do
            local name = entries[i]
            if name ~= "." and name ~= ".." then
                local p = normalize(join(assetSourcePath, name))
                if sdk.is_file(p) and name:lower():sub(-5) == ".json" then
                    local dst = normalize(join(assets_dst_root, name))
                    local ok, err = pcall(copy_file, p, dst)
                    if not ok then
                        log_warn(string.format("Warn: JSON copy failed '%s' -> '%s': %s", p, dst, tostring(err)))
                    else
                        log_info(string.format("Copied JSON config '%s' into project assets.", name))
                    end
                end
            end
        end
    end

    -- pause with prompt to continue
    prompt("Press Enter to continue...")

    -- Run scene builder
    local cmd = { godot_exe, "--editor", "--path", project_dir, "--script", "res://Scripts/import-V0.5.2.gd" }
    if no_exit then table.insert(cmd, "--no-exit"); sdk.colour_print{ colour = Colours.CYAN, message = "\n'--no-exit' flag detected. Godot will remain open after script execution." } end
    run_godot(cmd, "Scene Building")

    log_info("\n✅✅✅ Godot project setup and scene generation complete! ✅✅✅")
    countdown(1)
end


-- # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
-- # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #


local function main(project_name, repo_root, no_exit, assetSourcePath, iconPath)
    -- Locate this module directory
    local godot_module_root = normalize(script_dir)
    local module_root = normalize(dirname(godot_module_root))

    -- Engine diagnostics replaces local bootstrapping
    Diagnostics.Log("[godot-init] info: bootstrap logging started")

    log_info("Godot Module Root: " .. godot_module_root)
    log_info("Repository Root: " .. repo_root)

    -- 3. Source root exists
    if not sdk.is_dir(assetSourcePath) then
        fatal("Asset source root not found: " .. assetSourcePath)
    end

    --local sourcePath = assetSourcePath -- EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\STROUT-EU_FullFlattened-audio_reorg-isRenamed
    log_info("Using assetSourcePath: " .. assetSourcePath)
    local addons_folder = normalize(join(godot_module_root, "addons"))
    local rootfiles = normalize(join(godot_module_root, "rootfiles"))
    local project_path = normalize(join(godot_module_root, "GodotGame"))

    local godot_exe = resolve_godot()

    -- Pre-flight validations
    local stage = progress.start(4, "Pre-flight checks")
    -- 1. Validate Godot tool
    if not godot_exe or godot_exe == "" or not sdk.is_file(godot_exe) then
        fatal("Godot executable not found. Ensure 'Godot' tool is configured.")
    end
    stage:Update(1)
    -- 2. Godot version check (fast)
    local ok_version = sdk.execSilent({ godot_exe, "--version" }, { wait = true })
    if not (ok_version and ok_version.success == true) then
        log_warn("Unable to validate Godot via '--version'. Continuing, but import may fail.")
    end

    stage:Update(1)
    -- 4. Optional folders logged
    if not sdk.is_dir(addons_folder) then log_warn("Addons folder not found: " .. addons_folder) end
    stage:Update(1)
    if not sdk.is_dir(rootfiles) then log_warn("Rootfiles folder not found: " .. rootfiles) end
    stage:Update(1)
    -- Close preflight stage
    stage:Complete()

    -- Asset extensions to consider for import (filter out unnecessary files)
    --local asset_exts = { ".png", ".glb", ".wav", ".ogv", ".graph" }
    local asset_exts = { ".png", ".glb", ".ogv", ".graph" }
    local logo_images = get_logos(iconPath)

    create_godot_project(project_name, project_path, assetSourcePath, addons_folder, rootfiles, godot_exe, no_exit, logo_images, asset_exts)
end


-- # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
-- # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #


-- CLI
local function parse_args(argv)
    local opts = { ["project-name"] = "Game", ["no-exit"] = false }
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
        elseif a == "--iconPath" and argv[i+1] then
            opts["iconPath"] = argv[i+1]; i = i + 2
        else
            -- unknown or trailing
            i = i + 1
        end
    end
    return opts
end

-- Main
local function run()
    local opts = parse_args(argv)

    if not opts["repo-root"] then
        fatal("Missing required arg --repo-root")
        return
    end
    if not opts["sourcePath"] then
        fatal("Missing required arg --sourcePath")
        return
    end

    if not opts["iconPath"] then
        fatal("Missing required arg --iconPath")
        return
    end

    main(opts["project-name"], normalize(opts["repo-root"]), opts["no-exit"], normalize(opts["sourcePath"]), opts["iconPath"] and normalize(opts["iconPath"]))
end


run()
