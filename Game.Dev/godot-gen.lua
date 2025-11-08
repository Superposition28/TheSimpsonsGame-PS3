-- EngineApps/Games/TheSimpsonsGame-PS3/Game/init.lua
--[[
Folder-batched Godot import with per-language sub-batches for audio.
- No temp projects
- No staging mirror
- No batch_* folders
- Preserves final res://assets/<TopFolder>/... paths so scene JSON stays valid

Lua port of init.py with equivalent behavior.
Runtime: Lua 5.1+ under RemakeEngine LuaScriptAction (MoonSharp)
Dependencies provided by engine: lfs (shim), dkjson (shim), global `sdk` (EngineSdk bridge), global `tool(name)` resolver, global `argv` args.
]]

local lfs = require("lfs")
local path_sep = package.config:sub(1,1)
local sdk = rawget(_G, "sdk")

-- Colours (match engine SDK names)
local PREFIX = "Godot Init"
-- Console colour names (used only if host SDK supports coloured printing)
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

-- Print via SDK (if available) to preserve colour, otherwise fallback to plain print
local function colour_print(opts)
    if sdk and sdk.colour_print then
        sdk.colour_print(opts)
    else
        print(opts.message)
    end
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
    local target = normalize(p)
    local attr = lfs.attributes(target)
    if attr and attr.mode == "directory" then return true end
    -- try lfs.mkdir first (single level)
    local ok = false
    if lfs.mkdir then ok = lfs.mkdir(target) and true or false end
    if ok then return true end
    -- fallback to engine SDK (no shell execution)
    if sdk and type(sdk.ensure_dir) == "function" then
        return sdk.ensure_dir(target) == true
    end
    return false
end

local function file_exists(p)
    local a = lfs.attributes(p)
    return a ~= nil
end

local function is_dir(p)
    local a = lfs.attributes(p)
    return a and a.mode == "directory"
end

local function is_file(p)
    local a = lfs.attributes(p)
    return a and a.mode == "file"
end

local function get_file_size(p)
    local a = lfs.attributes(p)
    if a and a.mode == "file" then return a.size end
    return nil
end

-- Create a temporary file path (tries to use system temp on Windows)
local function tmpfile(suffix)
    local name = os.tmpname()
    if path_sep == "\\" then
        -- Ensure it's in a writable temp directory
        local t = (os.getenv and (os.getenv("TMP") or os.getenv("TEMP"))) or "."
        local base = basename(name)
        name = join(t, base)
    end
    if suffix then name = name .. suffix end
    return normalize(name)
end

-- May return false on missing; true if size equal and (if available) mtime comparable
local function nearly_same_file(src, dst)
    local sa = lfs.attributes(src)
    local da = lfs.attributes(dst)
    if not sa or not da then return false end
    if (sa.size or -1) ~= (da.size or -2) then return false end
    -- Our lfs shim exposes ISO string modtime; real lfs uses numeric. We accept equal string if present.
    if type(sa.modtime) == "string" and type(da.modtime) == "string" then
        return sa.modtime == da.modtime
    end
    return true
end

-- Compute SHA1 by shelling out where possible; returns lowercase hex string or nil on failure
local function sha1(path)
    path = normalize(path)
    if sdk and type(sdk.sha1_file) == "function" then
        local ok, res = pcall(function() return sdk.sha1_file(path) end)
        if ok and type(res) == "string" and #res >= 40 then
            return res
        end
    end
    return nil
end

-- Compare two files for exact equality.
-- Strategy: quick size check -> SHA1 if available -> buffered byte-by-byte compare.
local function files_equal(src, dst)
    local ss = get_file_size(src)
    local ds = get_file_size(dst)
    if not ss or not ds or ss ~= ds then return false end
    -- Try hash first if available (fast for large files due to streaming in SDK)
    local h1, h2 = sha1(src), sha1(dst)
    if h1 and h2 then return h1 == h2 end
    -- Fallback: buffered compare
    local f1 = io.open(src, "rb"); if not f1 then return false end
    local f2 = io.open(dst, "rb"); if not f2 then f1:close(); return false end
    local equal = true
    local chunk = 1024 * 1024 -- 1 MiB
    while true do
        local b1 = f1:read(chunk)
        local b2 = f2:read(chunk)
        if b1 ~= b2 then equal = false; break end
        if not b1 or #b1 == 0 then break end
    end
    f1:close(); f2:close()
    return equal
end

local function countdown(sec)
    sec = tonumber(sec) or 0
    while sec > 0 do
    colour_print{ colour = Colours.DARKCYAN, message = string.format("Waiting... %d seconds remaining.", sec) }
        local ossleep = rawget(os, "sleep")
        if type(ossleep) == "function" then ossleep(1) else
            -- busy-wait fallback (MoonSharp may not support socket.sleep)
            local t0 = os.time()
            repeat until os.time() > t0
        end
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
local function run_cmd(args, opts)
    opts = opts or {}
    local cmdline = build_cmdline(args)
    colour_print{ colour = Colours.MAGENTA, message = "Exec: " .. cmdline }
    -- exec or execSilent
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
    colour_print{ colour = Colours.MAGENTA, message = string.format("\n--- %s ---", label) }
    colour_print{ colour = Colours.MAGENTA, message = "Command: " .. build_cmdline(command) }
    local ok = run_cmd(command)
    --if ok then
    colour_print{ colour = Colours.CYAN, message = string.format("--- %s finished ---", label) }
end

-- File ops
local function copy_file(src, dst)
    ensure_dir(dirname(dst))
    local function lua_copy()
        local inf = assert(io.open(src, "rb"))
        local outf = assert(io.open(dst, "wb"))
        local chunk = 1024 * 1024 -- 1 MiB
        while true do
            local data = inf:read(chunk)
            if not data or #data == 0 then break end
            outf:write(data)
        end
        inf:close(); outf:close()
        return true
    end

    local function safe_remove(path)
        if sdk and type(sdk.remove_file) == "function" then
            pcall(function() sdk.remove_file(path) end)
        else
            pcall(function() os.remove(path) end)
        end
    end

    local used_sdk = false
    -- Prefer SDK file copy (uses .NET File.Copy) when available
    if sdk and type(sdk.copy_file) == "function" then
        local ok_call, ok = pcall(function() return sdk.copy_file(src, dst, true) end)
        used_sdk = true
        if ok_call and ok == true and files_equal(src, dst) then
            return
        end
        -- SDK path failed or produced mismatch; fall back to Lua copy
        safe_remove(dst)
        local ok2, err2 = pcall(lua_copy)
        if not ok2 then error("Lua copy failed: " .. tostring(err2)) end
        if not files_equal(src, dst) then
            error(string.format("Copy validation failed (SDK->Lua): '%s' -> '%s'", src, dst))
        end
        return
    end

    -- No SDK copy available; do Lua copy then validate, try SDK as a last resort if present later
    local ok_lua, err_lua = pcall(lua_copy)
    if not ok_lua then error("Lua copy failed: " .. tostring(err_lua)) end
    if files_equal(src, dst) then return end
    -- If SDK appears after, try it
    if sdk and type(sdk.copy_file) == "function" and not used_sdk then
        safe_remove(dst)
        local ok_call2, ok2 = pcall(function() return sdk.copy_file(src, dst, true) end)
        if ok_call2 and ok2 == true and files_equal(src, dst) then return end
    end
    error(string.format("Copy validation failed: '%s' -> '%s'", src, dst))
end

local function remove_file(path)
    if sdk and type(sdk.remove_file) == "function" then
        sdk.remove_file(path)
        return
    end
    -- fallback to Lua: best-effort via io
    if is_file(path) then
        pcall(function() os.remove(path) end)
    end
end

local function try_hardlink(src, dst)
    -- returns true on success, false otherwise
    remove_file(dst)
    ensure_dir(dirname(dst))
    if sdk and type(sdk.create_hardlink) == "function" then
        local ok = false
        local ok_call, res = pcall(function() return sdk.create_hardlink(src, dst) end)
        if ok_call then ok = res == true end
        return ok
    end
    return false
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
-- Only copy when changed. Returns total_seen, total_copied.
local function copy_tree_incremental(src_root, dst_root, use_hardlinks, verify_hash_for_large, large_bytes_threshold, exts)
    use_hardlinks = (use_hardlinks ~= false)
    verify_hash_for_large = (verify_hash_for_large == true)
    large_bytes_threshold = large_bytes_threshold or (50 * 1024 * 1024)

    local total_seen, total_copied = 0, 0
    local extset = nil
    if exts and #exts > 0 then
        extset = {}
        for _,e in ipairs(exts) do extset[e:lower()] = true end
    end

    ensure_dir(dst_root)

    walk_files(src_root, function(src, rel, fn)
        if extset then
            local low = fn:lower()
            local match = false
            for e,_ in pairs(extset) do
                if low:sub(-#e) == e then match = true break end
            end
            if not match then return end
        end
        local dst = join(dst_root, rel)
        ensure_dir(dirname(dst))
        total_seen = total_seen + 1

        if file_exists(dst) and nearly_same_file(src, dst) then
            return -- skip identical (quick)
        end

        if file_exists(dst) and verify_hash_for_large then
            local ss = get_file_size(src)
            local ds = get_file_size(dst)
            if ss and ds and ss == ds and ss >= large_bytes_threshold then
                local h1 = sha1(src)
                local h2 = sha1(dst)
                if h1 and h2 and h1 == h2 then
                    return -- skip identical by hash
                end
            end
        end

        local ok = false
        if use_hardlinks then
            ok = try_hardlink(src, dst)
        end
        if not ok then
            local ok2, err = pcall(copy_file, src, dst)
            if not ok2 then
                colour_print{ colour = Colours.YELLOW, message = string.format("Warn: copy/link failed '%s' -> '%s': %s", src, dst, tostring(err)) }
            else
                ok = true
            end
        end
        -- Post-copy validation: ensure exact match even for hardlinks (paranoia) or copies
        if ok then
            local valid = files_equal(src, dst)
            if not valid then
                -- Attempt a re-copy using strict path
                -- local safe remove (duplicate minimal logic to avoid dependency)
                local function _rm(p)
                    if sdk and type(sdk.remove_file) == "function" then pcall(function() sdk.remove_file(p) end)
                    else pcall(function() os.remove(p) end) end
                end
                _rm(dst)
                local ok3, err3 = pcall(copy_file, src, dst)
                if not ok3 or not files_equal(src, dst) then
                    colour_print{ colour = Colours.RED, message = string.format("ERROR: Copy validation failed after retry '%s' -> '%s' (%s)", src, dst, tostring(err3)) }
                    ok = false
                end
            end
        end
        if ok then total_copied = total_copied + 1 end
    end)

    return total_seen, total_copied
end

-- Constants
local AUDIO_TOP = "audiostreams"
local AUDIO_LANG_FOLDERS = { EN=true, ES=true, FR=true, IT=true, Global=true }

-- Create and import Godot project
local function create_godot_project(project_name, project_path, extracted_root, scripts_folder, addons_folder, conf_folder, godot_exe, no_exit, logo_images, asset_exts)
    local project_dir = join(project_path, project_name)
    ensure_dir(project_dir)
    colour_print{ colour = Colours.BLUE, message = "Godot Project Directory: " .. project_dir }

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
    ensure_dir(assets_dst_root)

    -- Logos
    if logo_images and #logo_images > 0 then
        local logos_dst = join(project_dir, "logos")
        ensure_dir(logos_dst)
        for _,f in ipairs(logo_images) do
            local ok, err = pcall(copy_file, f, join(logos_dst, basename(f)))
            if not ok then
                colour_print{ colour = Colours.YELLOW, message = string.format("Warn: logo copy failed '%s': %s", f, tostring(err)) }
            end
        end
        colour_print{ colour = Colours.BLUE, message = "Copied logo images into project." }
    end

    -- Copy addons, scene_config.json and tool scripts early so they are available
    -- during per-batch headless imports. This was previously done after
    -- importing assets; move it here to ensure tools/scripts are present.
    if addons_folder and is_dir(addons_folder) then
        -- copy tree into project_dir/addons (dirs_exist_ok)
        local dst = join(project_dir, "addons")
        local function copytree(src, dstroot)
            walk_files(src, function(ap, rp, _)
                local outp = join(dstroot, rp)
                ensure_dir(dirname(outp))
                local ok, err = pcall(copy_file, ap, outp)
                if not ok then
                    colour_print{ colour = Colours.YELLOW, message = string.format("Warn: addon copy failed '%s' -> '%s': %s", ap, outp, tostring(err)) }
                end
            end)
        end
        copytree(addons_folder, dst)
        colour_print{ colour = Colours.BLUE, message = "Copied addons into project before asset import." }
    end

    if conf_folder and is_dir(conf_folder) then
        local dst = project_dir -- copy conf contents into project root
        local function copytree(src, dstroot)
            walk_files(src, function(ap, rp, _)
                local outp = join(dstroot, rp)
                ensure_dir(dirname(outp))
                local ok, err = pcall(copy_file, ap, outp)
                if not ok then
                    colour_print{ colour = Colours.YELLOW, message = string.format("Warn: conf copy failed '%s' -> '%s': %s", ap, outp, tostring(err)) }
                end
            end)
        end
        copytree(conf_folder, dst)
        colour_print{ colour = Colours.BLUE, message = "Copied conf contents into project root before asset import." }
    end

    if scripts_folder and is_dir(scripts_folder) then
        local scripts_dst = join(project_dir, "Scripts")
        local function copytree(src, dstroot)
            walk_files(src, function(ap, rp, _)
                local outp = join(dstroot, rp)
                ensure_dir(dirname(outp))
                local ok, err = pcall(copy_file, ap, outp)
                if not ok then
                    colour_print{ colour = Colours.YELLOW, message = string.format("Warn: script copy failed '%s' -> '%s': %s", ap, outp, tostring(err)) }
                end
            end)
        end
        copytree(scripts_folder, scripts_dst)
        colour_print{ colour = Colours.BLUE, message = "Copied scene_config.json and tool scripts into project before asset import." }
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

    colour_print{ colour = Colours.BLUE, message = "\nDiscovered top-level asset batches in extracted source. Preparing to process..." }
    colour_print{ colour = Colours.BLUE, message = ("batches " .. tableToString(top_folders)) }

    if next(top_folders) == nil then
        colour_print{ colour = Colours.YELLOW, message = "No top-level batches found; exiting." }
        return
    end

    colour_print{ colour = Colours.BLUE, message = "\nBeginning asset placement into Godot project. This may take a while..." }
    countdown(15)

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
                ensure_dir(dst_lang)

                -- gate with .gdignore during placement
                local gdignore_path = join(dst_lang, ".gdignore")
                local f = io.open(gdignore_path, "a"); if f then f:close() end

                colour_print{ colour = Colours.BLUE, message = string.format("\n=== Batch %d: %s/%s ===", batch_idx, top, lang) }
                local seen, copied = copy_tree_incremental(src_lang, dst_lang, true, true, 50*1024*1024, asset_exts)
                colour_print{ colour = Colours.BLUE, message = string.format("Placed %d file(s), copied %d new/changed.", seen, copied) }

                remove_file(gdignore_path)

                colour_print{ colour = Colours.BLUE, message = string.format("Running headless import for: %s/%s", top, lang) }
                run_godot({ godot_exe, "--headless", "--path", project_dir, "--import", "-v", "--quit" }, string.format("Headless Import: %s/%s", top, lang))
            end
        else
            local dst_top = join(assets_dst_root, top)
            ensure_dir(dst_top)
            local gdignore_path = join(dst_top, ".gdignore")
            local f = io.open(gdignore_path, "a"); if f then f:close() end

            colour_print{ colour = Colours.BLUE, message = string.format("\n=== Batch %d: %s ===", batch_idx, top) }
            local seen, copied = copy_tree_incremental(src_top, dst_top, true, true, 50*1024*1024, asset_exts)
            colour_print{ colour = Colours.BLUE, message = string.format("Placed %d file(s), copied %d new/changed.", seen, copied) }

            remove_file(gdignore_path)

            colour_print{ colour = Colours.BLUE, message = string.format("Running headless import for: %s", top) }
            run_godot({ godot_exe, "--headless", "--path", project_dir, "--import", "-v", "--quit" }, string.format("Headless Import: %s", top))
        end
    end

    colour_print{ colour = Colours.BLUE, message = "\nAssets are ready. Preparing to run tool scripts." }
    countdown(10)

    -- Run scene builder
    local cmd = { godot_exe, "--editor", "--path", project_dir, "--script", "res://Scripts/import.gd" }
    if no_exit then table.insert(cmd, "--no-exit"); colour_print{ colour = Colours.BLUE, message = "\n'--no-exit' flag detected. Godot will remain open after script execution." } end
    run_godot(cmd, "Scene Building")

    colour_print{ colour = Colours.GREEN, message = "\n✅✅✅ Godot project setup and scene generation complete! ✅✅✅" }
    countdown(10)
end

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

local function resolve_godot()
    -- Prefer engine tool resolver if available; fall back to environment
    local tool_fn = rawget(_G, "tool")
    if type(tool_fn) == "function" then
        local p = tool_fn("Godot")
        if p and p ~= "" then return p end
    end
    error("Godot executable not found via tool resolver or GODOT env var")
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

local function main(project_name, repo_root, no_exit, sourcePath, iconPath)
    -- Locate this module directory
    local this_source = debug and debug.getinfo and debug.getinfo(1, 'S')
    local this_path = this_source and this_source.source or ""
    if this_path:sub(1,1) == "@" then this_path = this_path:sub(2) end
    local godot_module_root = dirname(this_path)
    local module_root = dirname(godot_module_root)

    colour_print{ colour = Colours.BLUE, message = "Godot Module Root: " .. godot_module_root }
    colour_print{ colour = Colours.BLUE, message = "Repository Root: " .. repo_root }

    colour_print{ colour = Colours.BLUE, message = "Using sourcePath: " .. sourcePath }
    local scripts_folder = join(godot_module_root, "Scripts")
    local addons_folder = join(godot_module_root, "addons")
    local conf_folder = join(godot_module_root, "rootfiles")
    local project_parent = join(godot_module_root, "GodotGame")

    local godot_exe = resolve_godot()

    --local asset_exts = { ".png", ".glb", ".wav", ".ogv" }
    local asset_exts = { ".png", ".glb", ".ogv" } -- exclude audio for now, too many files

    local logos = {}
    local ok, err = pcall(function()
        -- logo discovery
        local logo_dir = iconPath
        if is_dir(logo_dir) then
            logos = discover_pngs_in_dir(logo_dir)
        else
            colour_print{ colour = Colours.YELLOW, message = "Logo directory not found: " .. logo_dir }
            logos = {}
        end
        if #logos > 0 then
            colour_print{ colour = Colours.BLUE, message = "Found game logo images: " .. table.concat(logos, ", ") }
        end
    end)
    if not ok then
    colour_print{ colour = Colours.YELLOW, message = "Logo scan warning: " .. tostring(err) }
    end

    create_godot_project(project_name, project_parent, sourcePath, scripts_folder, addons_folder, conf_folder, godot_exe, no_exit, logos, asset_exts)
end

-- Main
local function run()
    local args = rawget(_G, "argv") or {}
    local opts = parse_args(args)
    if not opts["repo-root"] or not opts["sourcePath"] then
        error("Missing required args: --repo-root and --sourcePath")
    end
    main(opts["project-name"], normalize(opts["repo-root"]), opts["no-exit"], normalize(opts["sourcePath"]), normalize(opts["iconPath"]))
end

-- if invoked directly
if ... == nil then
    run()
end

return {
    main = main,
    run = run,
}
