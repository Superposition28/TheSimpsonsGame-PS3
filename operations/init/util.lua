---@class SfoData
---@field app_ver string|nil
---@field attribute integer|nil
---@field bootable integer|nil
---@field category string|nil
---@field license string|nil
---@field parental_level integer|nil
---@field ps3_system_ver string|nil
---@field resolution integer|nil
---@field sound_format integer|nil
---@field title string|nil
---@field title_id string|nil
---@field version string|nil
---@field entries table<string, string|integer>

---@class GameVersionInfo
---@field platform "PS3"|"XBOX360"
---@field region "EU"|"US"|"DEMO"|nil
---@field game_type "Full"|"Demo"
---@field title_id string|nil
---@field title string|nil
---@field category string|nil
---@field version string|nil
---@field app_ver string|nil
---@field ps3_system_ver string|nil
---@field sfo_path string|nil
---@field sfo_data SfoData|nil
---@field support_level "full"|"partial"|"unsupported"
---@field support_message string

---@class SourceValidationResult
---@field valid boolean
---@field error_kind "unextracted_xbox_iso"|"missing_dirs"|"missing_binary"|"invalid_game"|"not_found"|nil
---@field error_message string|nil
---@field resolved string
---@field copy_root string
---@field version_info GameVersionInfo|nil
---@field warnings table<integer, string>

---@class init
---@field USRDIR_DIRS table<integer, string>
---@field USRDIR_DIRS_ORIGINAL table<integer, string>
---@field USRDIR_DIRS_DEMO table<integer, string>
---@field USRDIR_OPTIONAL_FILES table<integer, string>
---@field ends_with_usrdir fun(p: string|nil): boolean
---@field normalize_region fun(value: string|nil): ("US"|"EU"|"DEMO"|"BOTH")|nil
---@field normalize_game_type fun(value: string|nil): ("Full"|"Demo")|nil
---@field check_dirs_exist fun(base_path: string, required_dirs: table<integer, string>): boolean, table<integer, string>
---@field check_dirs_exist_verbose fun(base_path: string, required_dirs: table<integer, string>, list_name?: string): boolean
---@field read_placeholders fun(cfg_path: string): table
---@field write_placeholders fun(cfg_path: string, new_placeholders: table): nil
---@field count_files fun(path: string): integer
---@field parse_sfo fun(sfo_path: string): SfoData|nil, string|nil
---@field is_ps3_game_folder fun(path: string): boolean
---@field is_unextracted_xbox_iso fun(path: string): boolean
---@field build_support_info fun(platform: "PS3"|"XBOX360", region: "EU"|"US"|"DEMO"|nil, game_type: "Full"|"Demo", title_id: string|nil): ("full"|"partial"|"unsupported", string)
---@field inspect_source_path fun(path: string): SourceValidationResult
---@field validate_source_path fun(path: string): boolean, string, string, SourceValidationResult
---@field print_version_report fun(result: SourceValidationResult): nil

--- Checks whether a path ends with a directory named USRDIR.
---@param p string|nil
---@return boolean
function ends_with_usrdir(p)
    if not p then
        return false
    end
    local name = basename(p)
    return name ~= nil and name:lower() == "usrdir"
end

--- Normalizes a region string into "US", "EU", "DEMO", or "BOTH".
---@param value string|nil
---@return ("US"|"EU"|"DEMO"|"BOTH")|nil
function normalize_region(value)
    if type(value) ~= "string" then
        return nil
    end
    local region = trim(value)
    if not region or region == "" then
        return nil
    end
    region = region:upper()
    if region == "US" or region == "EU" or region == "DEMO" or region == "BOTH" then
        return region
    end
    return nil
end

--- Normalizes a game type string into "Full" or "Demo".
---@param value string|nil
---@return ("Full"|"Demo")|nil
function normalize_game_type(value)
    if type(value) ~= "string" then
        return nil
    end
    local cleaned = trim(value):lower()
    if cleaned == "full" then
        return "Full"
    end
    if cleaned == "demo" then
        return "Demo"
    end
    return nil
end

-- Required directory sets (Renamed Full, Original Full, and Original Demo layouts)
USRDIR_DIRS = {
    "A1_Audio", "A1_Video", "A2_Characters",
    "A2_Frontend", "LHub-00_GameHub", "LHub-00_SprHub", "L01_LandOfChocolate",
    "L02_BartmanBegins", "L03_HungryHungryHomer", "L04_TreeHugger",
    "L05_MobRules", "L06_EnterTheCheatrix", "L07_DayOfTheDolphin",
    "L08_TheColossalDonut", "L09_Invasion", "L10_BargainBin",
    "L11_NeverQuest", "L12_GrandTheftScratchy", "L13_MedalOfHomer",
    "L14_BigSuperHappy", "L15_Rhymes", "L16_MeetThyPlayer",
}

USRDIR_DIRS_ORIGINAL = {
    "audiostreams", "bargainbin", "bigsuperhappy", "brt", "cheater", "colossaldonut",
    "dayofthedolphins", "dayspringfieldstoodstill", "eighty_bites", "frontend", "gamehub",
    "grand_theft_scratchy", "loc", "medal_of_homer", "meetthyplayer", "mob_rules",
    "movies", "neverquest", "rhymes", "simpsons_chars", "spr_hub", "text", "tree_hugger",
}

USRDIR_DIRS_DEMO = {
    "audiostreams", "demo_frontend", "demo_scd", "movies", "simpsons_chars", "text",
}

USRDIR_OPTIONAL_FILES = {
    "simpsons_gameflow.lua",
    "simpsons_gameflow_helpers.lua",
    "simpsons_scores.lua",
}

local PS3_ROOT_OPTIONAL_COMMON = {
    "ICON0.PNG",
    "PS3LOGO.DAT",
}

local PS3_ROOT_OPTIONAL_EU = {
    "PIC0.PNG", "PIC0_01.PNG", "PIC0_02.PNG", "PIC0_03.PNG", "PIC0_05.PNG", "PIC0_12.PNG",
    "PIC1.PNG",
    "PIC2.PNG", "PIC2_01.PNG", "PIC2_02.PNG", "PIC2_03.PNG", "PIC2_05.PNG", "PIC2_12.PNG",
}

local PS3_ROOT_OPTIONAL_US = {
    "PIC0.PNG", "PIC1.PNG", "PIC2.PNG",
}

--- Checks whether all required subdirectories exist under base_path.
---@param base_path string
---@param required_dirs table<integer, string>
---@return boolean ok, table<integer, string> missing
function check_dirs_exist(base_path, required_dirs)
    ---@type table<integer, string>
    local missing = {}
    if type(required_dirs) ~= "table" or not sdk.is_dir(base_path) then
        return false, missing
    end
    for _, dir_name in ipairs(required_dirs) do
        local full_path = join(base_path, dir_name)
        if not sdk.is_dir(full_path) then
            table.insert(missing, dir_name)
        end
    end
    return #missing == 0, missing
end

--- Verbose variant for logging which directory list is being checked.
---@param base_path string
---@param required_dirs table<integer, string>
---@param list_name? string
---@return boolean
function check_dirs_exist_verbose(base_path, required_dirs, list_name)
    local ok, missing = check_dirs_exist(base_path, required_dirs)
    if ok and #missing == 0 then
        colour_print({
            colour = Colours.GREEN,
            message = list_name
                and ("All %d required '%s' subdirectories found in '%s'."):format(#required_dirs, list_name, base_path)
                or ("All %d required subdirectories found in '%s'."):format(#required_dirs, base_path)
        })
        return true
    end
    return false
end

--- Reads placeholders table from config.toml.
---@param cfg_path string
---@return table
function read_placeholders(cfg_path)
    local doc = sdk.toml_read_file(cfg_path)
    if not doc then
        return {}
    end
    local ph = doc["placeholders"]
    if type(ph) == "table" then
        if ph[1] and type(ph[1]) == "table" then
            return ph[1]
        end
        return ph
    end
    return {}
end

--- Writes placeholders table to config.toml.
---@param cfg_path string
---@param new_placeholders table
---@return nil
function write_placeholders(cfg_path, new_placeholders)
    local doc = {}
    doc["placeholders"] = { new_placeholders }
    sdk.toml_write_file(cfg_path, doc)
end

--- Counts files recursively (files only).
---@param path string
---@return integer
function count_files(path)
    local count = 0
    for _, file in ipairs(sdk.list_dir(path)) do
        local full = join(path, file)
        local attr = sdk.attributes(full)
        if attr and attr.mode == "file" then
            count = count + 1
        elseif attr and attr.mode == "directory" then
            count = count + count_files(full)
        end
    end
    return count
end

--- Reads a 16-bit unsigned little-endian integer from a binary string at 1-based offset pos.
---@param data string
---@param pos integer
---@return integer
local function ReadU16LE(data, pos)
    local b1, b2 = string.byte(data, pos, pos + 1)
    return (b1 or 0) + ((b2 or 0) * 256)
end

--- Reads a 32-bit unsigned little-endian integer from a binary string at 1-based offset pos.
---@param data string
---@param pos integer
---@return integer
local function ReadU32LE(data, pos)
    local b1, b2, b3, b4 = string.byte(data, pos, pos + 3)
    return (b1 or 0) + ((b2 or 0) * 256) + ((b3 or 0) * 65536) + ((b4 or 0) * 16777216)
end

--- Encodes a raw binary string as uppercase hexadecimal (matching Python's raw_data.hex().upper()).
---@param raw string
---@return string
local function ToHexUpper(raw)
    ---@type table<integer, string>
    local hex_parts = {}
    for i = 1, #raw do
        hex_parts[i] = string.format("%02X", string.byte(raw, i))
    end
    return table.concat(hex_parts)
end

--- Strips trailing null (0x00) bytes from a raw binary string (matching Python's raw_data.rstrip(b'\x00')).
---@param raw string
---@return string
local function StripTrailingNulls(raw)
    local end_pos = #raw
    while end_pos >= 1 and string.byte(raw, end_pos) == 0 do
        end_pos = end_pos - 1
    end
    if end_pos < 1 then
        return ""
    end
    return raw:sub(1, end_pos)
end

--- Decodes a raw UTF-8 byte sequence (stored in a Latin1 MoonSharp string) into a Unicode string.
--- Also counts unprintable characters (excluding \n, \r, \t) to match reversing/sfo.csv.py.
---@param raw string
---@param replace_invalid boolean
---@return string|nil decoded, integer unprintable_count
local function DecodeUtf8(raw, replace_invalid)
    ---@type table<integer, string>
    local chars = {}
    local unprintable = 0
    local i = 1
    local len = #raw

    ---@param cp integer
    local function CheckPrintable(cp)
        if (cp < 0x20 and cp ~= 0x09 and cp ~= 0x0A and cp ~= 0x0D) or (cp >= 0x7F and cp <= 0x9F) then
            unprintable = unprintable + 1
        end
    end

    while i <= len do
        local b1 = string.byte(raw, i)
        if b1 < 0x80 then
            CheckPrintable(b1)
            table.insert(chars, string.char(b1))
            i = i + 1
        elseif b1 >= 0xC2 and b1 <= 0xDF then
            local b2 = i + 1 <= len and string.byte(raw, i + 1) or nil
            if b2 and b2 >= 0x80 and b2 <= 0xBF then
                local cp = ((b1 - 0xC0) * 64) + (b2 - 0x80)
                CheckPrintable(cp)
                table.insert(chars, string.char(cp))
                i = i + 2
            elseif replace_invalid then
                table.insert(chars, string.char(0xFFFD))
                i = i + 1
            else
                return nil, unprintable
            end
        elseif b1 >= 0xE0 and b1 <= 0xEF then
            local b2 = i + 1 <= len and string.byte(raw, i + 1) or nil
            local b3 = i + 2 <= len and string.byte(raw, i + 2) or nil
            local valid_b2 = b2 ~= nil and b2 >= 0x80 and b2 <= 0xBF
                and not (b1 == 0xE0 and b2 < 0xA0)
                and not (b1 == 0xED and b2 >= 0xA0)
            if valid_b2 and b3 and b3 >= 0x80 and b3 <= 0xBF then
                local cp = ((b1 - 0xE0) * 4096) + ((b2 - 0x80) * 64) + (b3 - 0x80)
                CheckPrintable(cp)
                table.insert(chars, string.char(cp))
                i = i + 3
            elseif replace_invalid then
                table.insert(chars, string.char(0xFFFD))
                i = i + 1
            else
                return nil, unprintable
            end
        elseif b1 >= 0xF0 and b1 <= 0xF4 then
            local b2 = i + 1 <= len and string.byte(raw, i + 1) or nil
            local b3 = i + 2 <= len and string.byte(raw, i + 2) or nil
            local b4 = i + 3 <= len and string.byte(raw, i + 3) or nil
            local valid_b2 = b2 ~= nil and b2 >= 0x80 and b2 <= 0xBF
                and not (b1 == 0xF0 and b2 < 0x90)
                and not (b1 == 0xF4 and b2 >= 0x90)
            if valid_b2 and b3 and b3 >= 0x80 and b3 <= 0xBF and b4 and b4 >= 0x80 and b4 <= 0xBF then
                local cp = ((b1 - 0xF0) * 262144) + ((b2 - 0x80) * 4096) + ((b3 - 0x80) * 64) + (b4 - 0x80)
                local offset = cp - 0x10000
                local high = 0xD800 + math.floor(offset / 1024)
                local low = 0xDC00 + (offset % 1024)
                table.insert(chars, string.char(high, low))
                i = i + 4
            elseif replace_invalid then
                table.insert(chars, string.char(0xFFFD))
                i = i + 1
            else
                return nil, unprintable
            end
        elseif replace_invalid then
            table.insert(chars, string.char(0xFFFD))
            i = i + 1
        else
            return nil, unprintable
        end
    end

    return table.concat(chars), unprintable
end

--- Reads a null-terminated key string from binary Latin1 data starting at 1-based start_pos.
---@param data string
---@param start_pos integer
---@return string
local function ReadNullTerminatedUtf8(data, start_pos)
    local end_pos = start_pos - 1
    for pos = start_pos, #data do
        if string.byte(data, pos) == 0 then
            break
        end
        end_pos = pos
    end
    if end_pos < start_pos then
        return ""
    end
    local raw = data:sub(start_pos, end_pos)
    local decoded = DecodeUtf8(raw, true)
    return decoded or raw
end

--- Parses a PS3 PARAM.SFO binary file and extracts all key-value entries,
--- matching the reference implementation in reversing/sfo.csv.py.
---@param sfo_path string
---@return SfoData|nil sfo_data, string|nil err
function parse_sfo(sfo_path)
    if type(sfo_path) ~= "string" or not sdk.is_file(sfo_path) then
        return nil, "PARAM.SFO file does not exist: " .. tostring(sfo_path)
    end

    local handle, open_err = io.open(sfo_path, "rb")
    if not handle then
        return nil, "Unable to open PARAM.SFO: " .. tostring(open_err)
    end
    ---@cast handle FileHandle
    local data = handle:read("*a")
    handle:close()

    if type(data) ~= "string" or #data < 20 then
        return nil, "File is too small to be a valid SFO."
    end

    -- magic (\0PSF) and version are at bytes 1..8; key_table_start, data_table_start, tables_entries at 9..20 (Little Endian)
    local m1, m2, m3, m4 = string.byte(data, 1, 4)
    if m1 ~= 0x00 or m2 ~= 0x50 or m3 ~= 0x53 or m4 ~= 0x46 then
        return nil, "Invalid magic number. Not a PARAM.SFO file."
    end

    local key_table_start = ReadU32LE(data, 9)
    local data_table_start = ReadU32LE(data, 13)
    local tables_entries = ReadU32LE(data, 17)

    if 20 + (tables_entries * 16) > #data or key_table_start >= #data or data_table_start > #data then
        return nil, "PARAM.SFO header offsets are out of bounds."
    end

    ---@type table<string, string|integer>
    local entries = {}

    for index = 0, tables_entries - 1 do
        local entry_pos = 21 + (index * 16)
        local key_offset = ReadU16LE(data, entry_pos)
        local data_fmt = ReadU16LE(data, entry_pos + 2)
        local data_len = ReadU32LE(data, entry_pos + 4)
        local data_offset = ReadU32LE(data, entry_pos + 12)

        -- 1. Extract Key (NULL-terminated UTF-8)
        local key_start = key_table_start + key_offset + 1
        if key_start <= #data then
            local key = ReadNullTerminatedUtf8(data, key_start)
            -- 2. Extract Data (only read the used bytes: data_len)
            local val_start = data_table_start + data_offset + 1
            if key ~= "" and val_start <= (#data + 1) then
                local val_end = math.min(#data, val_start + data_len - 1)
                local raw_data = (data_len > 0 and val_start <= #data) and data:sub(val_start, val_end) or ""

                -- 3. Interpret Data based on data_fmt (matching reversing/sfo.csv.py)
                if data_fmt == 0x0404 then
                    -- fmt 04 04 -> int32 (Little Endian 0x0404)
                    if #raw_data >= 4 then
                        entries[key] = ReadU32LE(raw_data, 1)
                    end
                elseif data_fmt == 0x0204 then
                    -- fmt 04 02 -> utf8, NULL terminated (Little Endian 0x0204)
                    local stripped = StripTrailingNulls(raw_data)
                    entries[key] = DecodeUtf8(stripped, true) or ""
                elseif data_fmt == 0x0004 then
                    -- fmt 04 00 -> utf8-S, NOT NULL terminated / reserved binary (Little Endian 0x0004)
                    local decoded, unprintable = DecodeUtf8(raw_data, false)
                    if decoded ~= nil and unprintable <= 5 then
                        entries[key] = decoded
                    else
                        entries[key] = "RAW_HEX:" .. ToHexUpper(raw_data)
                    end
                else
                    entries[key] = "RAW_HEX:" .. ToHexUpper(raw_data)
                end
            end
        end
    end

    ---@type SfoData
    local sfo_data = {
        app_ver = type(entries["APP_VER"]) == "string" and trim(entries["APP_VER"]) or nil,
        attribute = type(entries["ATTRIBUTE"]) == "number" and entries["ATTRIBUTE"] --[[@as integer]] or nil,
        bootable = type(entries["BOOTABLE"]) == "number" and entries["BOOTABLE"] --[[@as integer]] or nil,
        category = type(entries["CATEGORY"]) == "string" and trim(entries["CATEGORY"]) or nil,
        license = type(entries["LICENSE"]) == "string" and entries["LICENSE"] or nil,
        parental_level = type(entries["PARENTAL_LEVEL"]) == "number" and entries["PARENTAL_LEVEL"] --[[@as integer]] or nil,
        ps3_system_ver = type(entries["PS3_SYSTEM_VER"]) == "string" and trim(entries["PS3_SYSTEM_VER"]) or nil,
        resolution = type(entries["RESOLUTION"]) == "number" and entries["RESOLUTION"] --[[@as integer]] or nil,
        sound_format = type(entries["SOUND_FORMAT"]) == "number" and entries["SOUND_FORMAT"] --[[@as integer]] or nil,
        title = type(entries["TITLE"]) == "string" and trim(entries["TITLE"]) or nil,
        title_id = type(entries["TITLE_ID"]) == "string" and trim(entries["TITLE_ID"]) or nil,
        version = type(entries["VERSION"]) == "string" and trim(entries["VERSION"]) or nil,
        entries = entries,
    }

    return sfo_data, nil
end

--- Builds support status level and helpful message for a given version configuration.
---@param platform "PS3"|"XBOX360"
---@param region "EU"|"US"|"DEMO"|nil
---@param game_type "Full"|"Demo"
---@param title_id string|nil
---@return "full"|"partial"|"unsupported" support_level, string support_message
function build_support_info(platform, region, game_type, title_id)
    if platform == "XBOX360" then
        return "unsupported",
            "Notice: Xbox 360 version detected. Initialization supports setting up Xbox 360 source files, "
            .. "but downstream extraction/conversion operations do not currently work with Xbox 360 assets "
            .. "(only the EU PS3 Full version is targeted for full support)."
    end

    if game_type == "Demo" or region == "DEMO" then
        local id_label = title_id and (" (" .. title_id .. ")") or ""
        return "partial",
            "Notice: PS3 Demo version" .. id_label .. " detected. Currently only the EU PS3 Full version (BLES00142) "
            .. "is targeted for full support; operations expecting full-game levels or assets may not fully work."
    end

    if region == "EU" and (title_id == nil or title_id == "BLES00142") then
        return "full",
            "PS3 EU Full version" .. (title_id and (" (" .. title_id .. ")") or "")
            .. " detected. This version is the primary target for full support."
    end

    if region == "US" then
        local id_label = title_id and (" (" .. title_id .. ")") or ""
        return "partial",
            "Notice: PS3 US Full version" .. id_label .. " detected. Currently only the EU PS3 version (BLES00142) "
            .. "is targeted for full support; some operations or assets may not fully work."
    end

    local id_label = title_id and (" (" .. title_id .. ")") or ""
    return "partial",
        "Notice: PS3 version" .. id_label .. " detected. Currently only the EU PS3 version (BLES00142) "
        .. "is targeted for full support; other versions may not fully work."
end

--- Classifies a parsed SfoData structure into platform/region/type and checks that it belongs to The Simpsons Game.
---@param sfo SfoData
---@param sfo_path string
---@return GameVersionInfo|nil info, string|nil err
local function ClassifySfoVersion(sfo, sfo_path)
    local title_id = sfo.title_id and sfo.title_id:upper() or nil
    local title = sfo.title or ""
    local category = sfo.category and sfo.category:upper() or nil

    local known_ids = {
        ["BLES00142"] = { region = "EU", game_type = "Full" },
        ["BLES00138"] = { region = "EU", game_type = "Full" },
        ["BLES00139"] = { region = "EU", game_type = "Full" },
        ["BLES00140"] = { region = "EU", game_type = "Full" },
        ["BLES00141"] = { region = "EU", game_type = "Full" },
        ["BLUS30065"] = { region = "US", game_type = "Full" },
        ["NPEB90029"] = { region = "DEMO", game_type = "Demo" },
        ["NPUB90035"] = { region = "DEMO", game_type = "Demo" },
    }

    local known = title_id and known_ids[title_id] or nil
    local is_simpsons_title = title:lower():find("simpson", 1, true) ~= nil
    if not known and not is_simpsons_title then
        return nil, string.format(
            "PARAM.SFO at '%s' belongs to an unrecognized game: TITLE='%s', TITLE_ID='%s'.",
            sfo_path,
            tostring(sfo.title),
            tostring(sfo.title_id)
        )
    end

    ---@type "Full"|"Demo"
    local game_type = known and known.game_type or "Full"
    if not known then
        if category == "HG" or title:lower():find("demo", 1, true) ~= nil then
            game_type = "Demo"
        end
    end

    ---@type "EU"|"US"|"DEMO"|nil
    local region = known and known.region or nil
    if game_type == "Demo" then
        region = "DEMO"
    elseif not region and title_id then
        if title_id:match("^BLES") or title_id:match("^BCES") then
            region = "EU"
        elseif title_id:match("^BLUS") or title_id:match("^BCUS") then
            region = "US"
        elseif title_id:match("^NPEB") or title_id:match("^NPUB") then
            region = "DEMO"
            game_type = "Demo"
        end
    end

    local support_level, support_message = build_support_info("PS3", region, game_type, title_id)

    ---@type GameVersionInfo
    local info = {
        platform = "PS3",
        region = region,
        game_type = game_type,
        title_id = title_id,
        title = sfo.title,
        category = category,
        version = sfo.version,
        app_ver = sfo.app_ver,
        ps3_system_ver = sfo.ps3_system_ver,
        sfo_path = sfo_path,
        sfo_data = sfo,
        support_level = support_level,
        support_message = support_message,
    }
    return info, nil
end

--- Checks if a folder contains USRDIR (PS3 game container folder).
---@param path string
---@return boolean
function is_ps3_game_folder(path)
    if not sdk.is_dir(path) then
        return false
    end
    return sdk.is_dir(join(path, "USRDIR"))
end

--- Detects whether the path points to an unextracted Xbox 360 ISO mounted in Windows (AUDIO_TS / VIDEO_TS).
---@param path string
---@return boolean
function is_unextracted_xbox_iso(path)
    if not path or path == "" or not sdk.is_dir(path) then
        return false
    end

    local leaf = tostring(basename(path) or ""):upper()
    if leaf == "AUDIO_TS" or leaf == "VIDEO_TS" then
        return true
    end

    local has_video_ts = sdk.is_dir(join(path, "VIDEO_TS"))
    local has_audio_ts = sdk.is_dir(join(path, "AUDIO_TS"))
    if (has_video_ts or has_audio_ts)
        and not sdk.is_dir(join(path, "PS3_GAME"))
        and not sdk.is_dir(join(path, "USRDIR"))
        and not sdk.is_file(join(path, "default.xex"))
        and not sdk.is_file(join(path, "EBOOT.BIN"))
    then
        return true
    end

    return false
end

--- Collects warnings for optional files in USRDIR and parent PS3_GAME / Xbox root folders.
---@param usrdir string
---@param ps3_game_root string|nil
---@param platform "PS3"|"XBOX360"
---@param region "EU"|"US"|"DEMO"|nil
---@param game_type "Full"|"Demo"
---@param title_id string|nil
---@param warnings table<integer, string>
---@return nil
local function CollectOptionalFileWarnings(usrdir, ps3_game_root, platform, region, game_type, title_id, warnings)
    ---@type table<integer, string>
    local missing_lua = {}
    for _, lua_file in ipairs(USRDIR_OPTIONAL_FILES) do
        if not sdk.is_file(join(usrdir, lua_file)) then
            table.insert(missing_lua, lua_file)
        end
    end
    if #missing_lua > 0 then
        table.insert(warnings, "Optional script file(s) missing in game directory: " .. table.concat(missing_lua, ", "))
    end

    if platform == "PS3" and ps3_game_root then
        ---@type table<integer, string>
        local missing_root = {}
        for _, root_file in ipairs(PS3_ROOT_OPTIONAL_COMMON) do
            if not sdk.is_file(join(ps3_game_root, root_file)) then
                table.insert(missing_root, root_file)
            end
        end

        if game_type == "Full" then
            local pic_list = nil
            if title_id == "BLES00142" or (title_id == nil and region == "EU") then
                pic_list = PS3_ROOT_OPTIONAL_EU
            elseif title_id == "BLUS30065" or (title_id == nil and region == "US") then
                pic_list = PS3_ROOT_OPTIONAL_US
            end
            if pic_list then
                for _, pic_file in ipairs(pic_list) do
                    if not sdk.is_file(join(ps3_game_root, pic_file)) then
                        table.insert(missing_root, pic_file)
                    end
                end
            end
        end

        if #missing_root > 0 then
            table.insert(warnings, "Optional PS3 metadata/icon file(s) missing in parent folder: " .. table.concat(missing_root, ", "))
        end
    elseif platform == "XBOX360" then
        if not sdk.is_dir(join(usrdir, "$systemupdate")) then
            table.insert(warnings, "Optional '$systemupdate' folder not present in extracted Xbox 360 directory.")
        end
    end
end

--- Inspects a candidate source path, resolving ISO root / PS3_GAME / USRDIR / Xbox 360 root,
--- parsing PARAM.SFO when available, and validating required folders and executables.
---@param path string
---@return SourceValidationResult
function inspect_source_path(path)
    ---@type SourceValidationResult
    local result = {
        valid = false,
        error_kind = nil,
        error_message = nil,
        resolved = path or "",
        copy_root = path or "",
        version_info = nil,
        warnings = {},
    }

    if not path or path == "" then
        result.error_kind = "not_found"
        result.error_message = "No source path was provided."
        return result
    end

    -- When the user provides USRDIR directly, check its parent directory first so RemakeEngine's
    -- security prompt approves the parent root (covering both PARAM.SFO and USRDIR in one prompt).
    if ends_with_usrdir(path) then
        local parent_dir = dirname(path)
        if parent_dir and parent_dir ~= "" and parent_dir ~= path then
            sdk.is_dir(parent_dir)
        end
    end

    if not sdk.is_dir(path) then
        result.error_kind = "not_found"
        result.error_message = "The provided path is not an existing directory: '" .. tostring(path) .. "'."
        return result
    end

    -- Check for unextracted Xbox 360 ISO opened directly in Windows (AUDIO_TS / VIDEO_TS fake DVD partition)
    if is_unextracted_xbox_iso(path) then
        result.error_kind = "unextracted_xbox_iso"
        result.error_message = "Detected an unextracted Xbox 360 ISO (AUDIO_TS/VIDEO_TS DVD partition). "
            .. "Windows only shows the fake DVD video partition when mounting an Xbox 360 ISO directly. "
            .. "Please extract the ISO manually first and provide the extracted file path instead."
        return result
    end

    -- Resolve candidate USRDIR / game data directory and PS3 parent folder
    ---@type string
    local candidate_usrdir = path
    ---@type string
    local candidate_copy_root = path
    ---@type string|nil
    local ps3_game_root = nil

    local disc_ps3_game = join(path, "PS3_GAME")
    local disc_usrdir = join(disc_ps3_game, "USRDIR")
    local direct_usrdir = join(path, "USRDIR")

    if sdk.is_dir(disc_ps3_game) and sdk.is_dir(disc_usrdir) then
        -- User provided PS3 ISO root (e.g. E:\ containing PS3_GAME, PS3_UPDATE, PS3_DISC.SFB)
        ps3_game_root = disc_ps3_game
        candidate_usrdir = disc_usrdir
        candidate_copy_root = disc_ps3_game
    elseif sdk.is_dir(direct_usrdir) then
        -- User provided PS3_GAME or NPEB90029 folder containing USRDIR
        ps3_game_root = path
        candidate_usrdir = direct_usrdir
        candidate_copy_root = path
    elseif ends_with_usrdir(path) then
        -- User provided USRDIR directly
        candidate_usrdir = path
        local parent = dirname(path)
        if parent and parent ~= "" and parent ~= path and sdk.is_dir(parent) then
            ps3_game_root = parent
            candidate_copy_root = parent
        else
            candidate_copy_root = path
        end
    else
        -- Check if user provided a wrapper folder containing a single PS3 container folder (e.g. Demo/NPEB90029/USRDIR)
        local subdirs = list_subdirs(path)
        if #subdirs == 1 then
            local single_sub = join(path, subdirs[1])
            local nested_usrdir = join(single_sub, "USRDIR")
            if sdk.is_dir(nested_usrdir) then
                ps3_game_root = single_sub
                candidate_usrdir = nested_usrdir
                candidate_copy_root = single_sub
            end
        end
    end

    result.resolved = normalize(candidate_usrdir)
    result.copy_root = normalize(candidate_copy_root)

    -- Attempt to locate and parse PARAM.SFO in the parent of USRDIR (if applicable)
    ---@type string|nil
    local sfo_path = nil
    if ps3_game_root then
        local candidate_sfo = join(ps3_game_root, "PARAM.SFO")
        if sdk.is_file(candidate_sfo) then
            sfo_path = candidate_sfo
        end
    else
        local parent = dirname(candidate_usrdir)
        if parent and parent ~= "" and parent ~= candidate_usrdir then
            local parent_sfo = join(parent, "PARAM.SFO")
            if sdk.is_file(parent_sfo) then
                ps3_game_root = parent
                sfo_path = parent_sfo
                if ends_with_usrdir(candidate_usrdir) then
                    result.copy_root = normalize(parent)
                end
            end
        end
    end

    ---@type GameVersionInfo|nil
    local sfo_version_info = nil
    if sfo_path then
        local sfo_data, sfo_err = parse_sfo(sfo_path)
        if not sfo_data then
            table.insert(result.warnings, "Found PARAM.SFO at '" .. sfo_path .. "' but failed to parse it: " .. tostring(sfo_err))
        else
            local classified, classify_err = ClassifySfoVersion(sfo_data, sfo_path)
            if not classified then
                result.error_kind = "invalid_game"
                result.error_message = classify_err
                return result
            end
            sfo_version_info = classified
        end
    end

    -- Check executables in candidate_usrdir
    local has_eboot = sdk.is_file(join(candidate_usrdir, "EBOOT.BIN"))
    local has_xex = sdk.is_file(join(candidate_usrdir, "default.xex"))

    -- Check folder sets in candidate_usrdir
    local has_full_orig, missing_full_orig = check_dirs_exist(candidate_usrdir, USRDIR_DIRS_ORIGINAL)
    local has_full_renamed, _ = check_dirs_exist(candidate_usrdir, USRDIR_DIRS)
    local has_demo_dirs, missing_demo_dirs = check_dirs_exist(candidate_usrdir, USRDIR_DIRS_DEMO)

    -- Determine platform
    ---@type "PS3"|"XBOX360"|nil
    local platform = nil
    if sfo_version_info then
        platform = "PS3"
    elseif has_eboot or ps3_game_root ~= nil then
        platform = "PS3"
    elseif has_xex then
        platform = "XBOX360"
    end

    -- Validate directory structure
    ---@type "Full"|"Demo"|nil
    local detected_type = sfo_version_info and sfo_version_info.game_type or nil

    if detected_type == "Demo" then
        if not has_demo_dirs then
            result.error_kind = "missing_dirs"
            result.error_message = string.format(
                "PS3 Demo (%s) is missing %d required USRDIR folder(s) in '%s': %s",
                tostring(sfo_version_info and sfo_version_info.title_id or "Demo"),
                #missing_demo_dirs,
                candidate_usrdir,
                table.concat(missing_demo_dirs, ", ")
            )
            return result
        end
    elseif detected_type == "Full" then
        if not has_full_orig and not has_full_renamed then
            result.error_kind = "missing_dirs"
            result.error_message = string.format(
                "PS3 Full version (%s) is missing %d required USRDIR folder(s) in '%s': %s",
                tostring(sfo_version_info and sfo_version_info.title_id or "Full"),
                #missing_full_orig,
                candidate_usrdir,
                table.concat(missing_full_orig, ", ")
            )
            return result
        end
    else
        if has_full_orig or has_full_renamed then
            detected_type = "Full"
        elseif has_demo_dirs then
            detected_type = "Demo"
        else
            result.error_kind = "missing_dirs"
            if #missing_full_orig < #USRDIR_DIRS_ORIGINAL then
                result.error_message = string.format(
                    "Incomplete game directory at '%s'. Missing %d required folder(s): %s",
                    candidate_usrdir,
                    #missing_full_orig,
                    table.concat(missing_full_orig, ", ")
                )
            else
                result.error_message = "The provided path '" .. tostring(path) .. "' does not contain a valid Simpsons Game folder structure (PS3_GAME/USRDIR or extracted Xbox 360 root)."
            end
            return result
        end
    end

    -- Validate required binary executable (EBOOT.BIN for PS3, default.xex for Xbox 360)
    if platform == "PS3" and not has_eboot then
        result.error_kind = "missing_binary"
        result.error_message = "Missing required PS3 executable 'EBOOT.BIN' in '" .. candidate_usrdir .. "'."
        return result
    elseif platform == "XBOX360" and not has_xex then
        result.error_kind = "missing_binary"
        result.error_message = "Missing required Xbox 360 executable 'default.xex' in '" .. candidate_usrdir .. "'."
        return result
    elseif platform == nil then
        result.error_kind = "missing_binary"
        result.error_message = "Missing required game executable ('EBOOT.BIN' for PS3 or 'default.xex' for Xbox 360) in '" .. candidate_usrdir .. "'."
        return result
    end

    -- Build version_info if SFO was missing
    if not sfo_version_info then
        ---@type "EU"|"US"|"DEMO"|nil
        local inferred_region = detected_type == "Demo" and "DEMO" or nil
        if platform == "PS3" then
            if inferred_region == "DEMO" then
                table.insert(result.warnings, "PARAM.SFO was not found in parent folder; detected Demo region from USRDIR layout.")
            else
                table.insert(result.warnings, "PARAM.SFO was not found in parent folder; region will need to be specified or prompted.")
            end
        end
        local support_level, support_message = build_support_info(platform, inferred_region, detected_type, nil)
        sfo_version_info = {
            platform = platform,
            region = inferred_region,
            game_type = detected_type,
            title_id = nil,
            title = nil,
            category = nil,
            version = nil,
            app_ver = nil,
            ps3_system_ver = nil,
            sfo_path = nil,
            sfo_data = nil,
            support_level = support_level,
            support_message = support_message,
        }
    end

    CollectOptionalFileWarnings(
        candidate_usrdir,
        ps3_game_root,
        sfo_version_info.platform,
        sfo_version_info.region,
        sfo_version_info.game_type,
        sfo_version_info.title_id,
        result.warnings
    )

    result.valid = true
    result.version_info = sfo_version_info
    return result
end

--- Validates and resolves a source path.
---@param path string
---@return boolean ok, string usrdir_path, string folder_to_copy, SourceValidationResult details
function validate_source_path(path)
    local details = inspect_source_path(path)
    return details.valid, details.resolved, details.copy_root, details
end

--- Prints a formatted summary of the detected game version, SFO metadata, support status, and optional warnings.
---@param result SourceValidationResult
---@return nil
function print_version_report(result)
    if not result or not result.version_info then
        return
    end

    local info = result.version_info
    colour_print({ colour = Colours.CYAN, message = "=== Detected Game Source ===" })
    colour_print({ colour = Colours.WHITE, message = "  Resolved Data Path : " .. result.resolved })
    if result.copy_root ~= result.resolved then
        colour_print({ colour = Colours.WHITE, message = "  Container Root     : " .. result.copy_root })
    end

    local region_label = info.region or "Unknown (will prompt)"
    colour_print({
        colour = Colours.WHITE,
        message = string.format("  Platform / Region  : %s | Region: %s | Edition: %s", info.platform, region_label, info.game_type)
    })

    if info.sfo_data then
        colour_print({
            colour = Colours.CYAN,
            message = string.format(
                "  PARAM.SFO Metadata : TITLE='%s' | TITLE_ID=%s | CATEGORY=%s | VER=%s (APP_VER=%s, SYS_VER=%s)",
                tostring(info.title or "N/A"),
                tostring(info.title_id or "N/A"),
                tostring(info.category or "N/A"),
                tostring(info.version or "N/A"),
                tostring(info.app_ver or "N/A"),
                tostring(info.ps3_system_ver or "N/A")
            )
        })
    end

    local support_colour = info.support_level == "full" and Colours.GREEN or Colours.YELLOW
    colour_print({ colour = support_colour, message = "  " .. info.support_message })

    for _, warning_msg in ipairs(result.warnings) do
        colour_print({ colour = Colours.YELLOW, message = "  Warning: " .. warning_msg })
    end
end

