local Utils = require("utils")
local Colours = Utils.Colours
local M = {}

-- Local application-specific helpers
function M.ends_with_usrdir(p)
    if not p then return false end
    local name = Utils.basename(p)
    return name and name:lower() == "usrdir"
end

function M.normalize_region(value)
    if type(value) ~= "string" then return nil end
    local region = Utils.trim(value)
    if not region or region == "" then return nil end
    region = region:upper()
    if region == "US" or region == "EU" or region == "BOTH" then
        return region
    end
    return nil
end

-- Input helper using engine's guaranteed prompt() global
function M.get_input(msg, id)
    return prompt(msg, id or "tsg_init", false)
end

-- Required directory sets (either original or USRDIR layout is accepted)
local USRDIR_DIRS = {
    "A1_Audio", "A1_Video", "A2_Characters",
    "A2_Frontend", "LHub-00_GameHub", "LHub-00_SprHub", "L01_LandOfChocolate",
    "L02_BartmanBegins", "L03_HungryHungryHomer", "L04_TreeHugger",
    "L05_MobRules", "L06_EnterTheCheatrix", "L07_DayOfTheDolphin",
    "L08_TheColossalDonut", "L09_Invasion", "L10_BargainBin",
    "L11_NeverQuest", "L12_GrandTheftScratchy", "L13_MedalOfHomer",
    "L14_BigSuperHappy", "L15_Rhymes", "L16_MeetThyPlayer",
}

local USRDIR_DIRS_ORIGINAL = {
    "audiostreams", "bargainbin", "bigsuperhappy", "brt", "cheater", "colossaldonut",
    "dayofthedolphins", "dayspringfieldstoodstill", "eighty_bites", "frontend", "gamehub",
    "grand_theft_scratchy", "loc", "medal_of_homer", "meetthyplayer", "mob_rules",
    "movies", "neverquest", "rhymes", "simpsons_chars", "spr_hub", "text", "tree_hugger",
}

function M.check_dirs_exist(base_path, required_dirs)
    if not sdk.is_dir(base_path) then return false end
    for _, dir_name in ipairs(required_dirs) do
        local full_path = join(base_path, dir_name)
        if not sdk.is_dir(full_path) then return false end
    end
    return true
end

-- Verbose variant for logging which list is being checked
function M.check_dirs_exist_verbose(base_path, required_dirs, list_name)
    if not sdk.is_dir(base_path) then return false end
    local missing = {}
    for _, dir_name in ipairs(required_dirs) do
        local full_path = join(base_path, dir_name)
        if not sdk.is_dir(full_path) then table.insert(missing, dir_name) end
    end
    if #missing == 0 then
        Utils.colour_print{colour=Colours.GREEN, message=(list_name and ("All %d required '%s' subdirectories found in '"..base_path.."'."):format(#required_dirs, list_name) or ("All %d required subdirectories found in '"..base_path.."'."):format(#required_dirs))}
        return true
    end
    return false
end

-- TOML helpers via engine SDK
function M.read_placeholders(cfg_path)
    local doc = sdk.toml_read_file(cfg_path)
    if not doc then return {} end
    local ph = doc["placeholders"]
    if type(ph) == "table" then
        if ph[1] and type(ph[1]) == "table" then
            return ph[1]
        end
        return ph
    end
    return {}
end

function M.write_placeholders(cfg_path, new_placeholders)
    local doc = {}
    doc["placeholders"] = { new_placeholders }
    sdk.toml_write_file(cfg_path, doc)
end

-- Count files recursively (files only)
function M.count_files(path)
    local count = 0
    for _, file in ipairs(sdk.list_dir(path)) do
        local full = join(path, file)
        local attr = sdk.attributes(full)
        if attr and attr.mode == "file" then
            count = count + 1
        elseif attr and attr.mode == "directory" then
            count = count + M.count_files(full)
        end
    end
    return count
end


-- Check if a folder contains USRDIR, PARAM.SFO, and at least one PNG (PS3_GAME folder structure)
function M.is_ps3_game_folder(path)
    if not sdk.is_dir(path) then return false end
    local has_usrdir = sdk.is_dir(join(path, "USRDIR"))
    local has_sfo = sdk.path_exists(join(path, "PARAM.SFO"))
    local has_png = false
    -- Check for any PNG file
    for _, file in ipairs(sdk.list_dir(path)) do
        if file:match("%.png$") or file:match("%.PNG$") then
            has_png = true
            break
        end
    end
    return has_usrdir and has_sfo and has_png
end

-- Validate and resolve the source path, checking multiple possible locations for USRDIR
-- Returns: ok (bool), usrdir_path (for validation), folder_to_copy (the PS3_GAME parent folder)
function M.validate_source_path(path)
    if not path or path == "" or not sdk.is_dir(path) then return false, path, path end

    -- Check if path itself is USRDIR (has game directories)
    local ok = M.check_dirs_exist(path, USRDIR_DIRS_ORIGINAL) or M.check_dirs_exist(path, USRDIR_DIRS)
    if ok then
        -- This is the USRDIR folder, so copy its parent (PS3_GAME)
        local parent = Utils.dirname(path)
        if M.is_ps3_game_folder(parent) then
            return true, path, parent
        end
        -- Fallback if parent doesn't have PS3_GAME structure
        return true, path, path
    end

    -- Check if path contains USRDIR subfolder (this is PS3_GAME folder)
    local usrdir = join(path, "USRDIR")
    if sdk.is_dir(usrdir) then
        ok = M.check_dirs_exist(usrdir, USRDIR_DIRS_ORIGINAL) or M.check_dirs_exist(usrdir, USRDIR_DIRS)
        if ok and M.is_ps3_game_folder(path) then
            -- This is the PS3_GAME folder itself, copy this folder
            return true, usrdir, path
        end
    end

    -- Check path/PS3_GAME/USRDIR (for disc root like D:\)
    local ps3_game = join(path, "PS3_GAME")
    if sdk.is_dir(ps3_game) then
        local ps3_usrdir = join(path, "PS3_GAME", "USRDIR")
        if sdk.is_dir(ps3_usrdir) then
            ok = M.check_dirs_exist(ps3_usrdir, USRDIR_DIRS_ORIGINAL) or M.check_dirs_exist(ps3_usrdir, USRDIR_DIRS)
            if ok and M.is_ps3_game_folder(ps3_game) then
                -- Found PS3_GAME subfolder, copy that folder
                return true, ps3_usrdir, ps3_game
            end
        end
    end

    return false, path, path
end

return M
