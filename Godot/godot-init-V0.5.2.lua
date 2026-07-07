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
    - progress.panel.new(total, id?, label?) -> Panel progress handle (Update/Complete)
    - script_progress(total, id?, label?) -> Stage progress indicator

Expected folder structure (relative to this module root):
    - GameFiles/STROUT/<TopFolder>/... assets to import
        - Special case: GameFiles/STROUT/audiostreams/<Lang>/...
    - Game/GodotGame/<ProjectName>/ project output
    - Game/addons, Game/Scripts, Game/rootfiles copied into project before import
]]

import("utils")

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

-- Constants
local AUDIO_TOP1 = "audiostreams" -- source name
local AUDIO_TOP2 = "A1_Audio" -- renamed
-- Map of language folder names under audiostreams to whether they should be prioritized first (true) or later (false) in processing order.
local AUDIO_LANG_FOLDERS = { EN=true, ES=true, FR=true, IT=true, Global=true }

-- Create and import Godot project
---@param project_name string
---@param project_path string
---@param assetSourcePath string
---@param godot_Core_Files string|nil
---@param godot_exe string
---@param no_exit boolean
---@param logo_images table<integer, string>
---@param asset_exts table<integer, string>
---@return nil
local function create_godot_project(project_name, project_path, assetSourcePath, godot_Core_Files, godot_exe, no_exit, logo_images, asset_exts)
    local project_dir = join(project_path, project_name)
    -- if project_dir already exists, we append a number to project name, and recheck in loop until we find a name that doesn't exist, to avoid overwriting existing projects.
    local count = 1
    while sdk.is_dir(project_dir) do
        project_dir = join(project_path, project_name .. "_" .. count)
        count = count + 1
    end

    sdk.ensure_dir(project_dir)
    log_info("Godot Project Directory: " .. project_dir)

    -- Engine diagnostics replaces local project log
    Diagnostics.Log(string.format("[godot-init] info: init.lua started for project '%s'", project_name))

    local assets_dst_root = join(project_dir, "assets")

    -- Logos
    if logo_images and #logo_images > 0 then
        local logos_dst = join(project_dir, "logos")
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
    if godot_Core_Files and sdk.is_dir(godot_Core_Files) then
        -- copy all contents of Core/ into project_dir/ preserving structure.
        local dst = join(project_dir)
        ---@param src string
        ---@param dstroot string
        ---@return nil
        local function copytree(src, dstroot)
            walk_files(src, function(ap, rp, _)
                local outp = join(dstroot, rp)
                sdk.ensure_dir(dirname(outp))
                local ok, err = pcall(copy_file, ap, outp)
                if not ok then
                    log_warn(string.format("Warn: addon copy failed '%s' -> '%s': %s", ap, outp, tostring(err)))
                end
            end)
        end
        copytree(godot_Core_Files, dst)
        log_info("Copied core files into project before asset import.")
    end

    -- Discover top-level folders under ExtractedOut
    local top_folders = {}
    local entries = sdk.list_dir(assetSourcePath)
    if entries then
        for i = 1, #entries do
            local d = entries[i]
            if d ~= "." and d ~= ".." then
                local p = join(assetSourcePath, d)
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
            local src_top = join(assetSourcePath, top)
            if top == AUDIO_TOP1 or top == AUDIO_TOP2 then
                -- sub-batch by language folders
                local langs = {}
                local entries2 = sdk.list_dir(src_top)
                if entries2 then
                    for i = 1, #entries2 do
                        local name = entries2[i]
                        if name ~= "." and name ~= ".." then
                            local p = join(src_top, name)
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
                    local src_lang = join(src_top, lang)
                    local dst_lang = normalize(join(join(assets_dst_root, top), lang))
                    sdk.ensure_dir(dst_lang)

                    -- gate with .gdignore during placement
                    local gdignore_path = join(dst_lang, ".gdignore")
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
                    local p = progress.panel.new(list_counter.count, "copy_"..top.."_"..lang, string.format("Copy %s/%s", top, lang))
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
                local dst_top = join(assets_dst_root, top)
                sdk.ensure_dir(dst_top)
                local gdignore_path = join(dst_top, ".gdignore")
                sdk.write_file(gdignore_path, "")

                log_info(string.format("\n=== Batch %d: %s ===", batch_idx, top))

                local list_counter = { count = 0 }
                walk_files(src_top, function(ap, rp, fn)
                    if asset_exts then local low = fn:lower(); local match=false; for _,e in ipairs(asset_exts) do if low:sub(-#e) == e then match=true; break end end; if not match then return end end
                    list_counter.count = list_counter.count + 1
                end)
                local p = progress.panel.new(list_counter.count, "copy_"..top, string.format("Copy %s", top))
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
                local p = join(assetSourcePath, name)
                if sdk.is_file(p) and name:lower():sub(-5) == ".json" then
                    local dst = join(assets_dst_root, name)
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

    log_info("\n??? Godot project setup and scene generation complete! ???")
    countdown(1)
end


-- # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
-- # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #


---@param project_name string
---@param repo_root string
---@param no_exit boolean
---@param assetSourcePath string
---@param iconPath string|nil
---@return nil
local function main(project_name, repo_root, no_exit, assetSourcePath, iconPath)
    -- Locate this module directory
    local godot_module_root = normalize(script_dir)

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
    local godot_Core_Files = join(godot_module_root, "Core")
    local project_path = join(godot_module_root, "GodotGame")

    local godot_exe = resolve_godot()

    -- Pre-flight validations
    local stage = progress.script.start(4, "Pre-flight checks")
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
    if not sdk.is_dir(godot_Core_Files) then log_warn("Core files folder not found: " .. godot_Core_Files) end
    stage:Update(1)

    -- Close preflight stage
    stage:Complete()

    -- Asset extensions to consider for import (filter out unnecessary files)
    --local asset_exts = { ".png", ".glb", ".wav", ".ogv", ".graph" } -- temporarily exclude .wav to avoid importing 30,000 audio files for now
    local asset_exts = { ".png", ".glb", ".ogv", ".graph" }
    local logo_images = get_logos(iconPath)

    create_godot_project(project_name, project_path, assetSourcePath, godot_Core_Files, godot_exe, no_exit, logo_images, asset_exts)
end


-- # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
-- # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #


-- CLI
---@param argv table<integer, string>
---@return table<string, any>
local function parse_args(argv)
    local opts = { ["project-name"] = "Game", ["no-exit"] = false }
    ---@cast opts table<string, any>
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
