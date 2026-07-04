--- SetupMusicFiles.lua
--- Purpose: Extracts .mus files and converts audio streams to .wav using QuickBMS and vgmstream.

-- make all shared util functions globally available
---@type SharedUtils
import("SharedUtils")

---@class SetupMusicFilesOptions
---@field bmsscript string?
---@field GameDir string?

--- Parse command line arguments
---@param list string[]
---@return SetupMusicFilesOptions
local function parse_args(list)
    ---@type SetupMusicFilesOptions
    local opts = {}
    local i = 1
    while i <= #list do
        local key = list[i]
        if key == "--bmsscript" and list[i + 1] then
            opts.bmsscript = list[i + 1]
            i = i + 2
        elseif key == "--GameDir" and list[i + 1] then
            opts.GameDir = list[i + 1]
            i = i + 2
        else
            i = i + 1
        end
    end
    return opts
end

local opts = parse_args(argv or {...})

if not opts.bmsscript then
    error("Missing required argument: --bmsscript")
end
if not opts.GameDir then
    error("Missing required argument: --GameDir")
end

sdk.colour_print({ colour = Colours.CYAN, message = "=== Converting Music (.mus -> .snr/.sns -> .wav) ===" })
sdk.colour_print({ colour = Colours.WHITE, message = "  BMS Script: " .. opts.bmsscript })
sdk.colour_print({ colour = Colours.WHITE, message = "  Game Directory: " .. opts.GameDir })

-- Resolve Tools
---@type string
local bms_exe = tool("QuickBMS")
---@type string
local vgmstream_exe = tool("vgmstream-cli")

if not bms_exe or bms_exe == "" then
    error("QuickBMS tool not found via tool('QuickBMS'). Please check installation.")
end
if not vgmstream_exe or vgmstream_exe == "" then
    error("vgmstream-cli tool not found via tool('vgmstream-cli'). Please check installation.")
end

-- Validate and use quickbms_4gb_files.exe if present next to quickbms.exe
---@type string
local dir_bms = dirname(bms_exe)
---@type string
local bms_4gb = join(dir_bms, "quickbms_4gb_files.exe")
if sdk.is_file(bms_4gb) then
    sdk.colour_print({ colour = Colours.GRAY, message = "  Found 4GB enabled QuickBMS executable. Using: " .. bms_4gb })
    bms_exe = bms_4gb
else
    sdk.colour_print({ colour = Colours.GRAY, message = "  Using: " .. bms_exe })
end
sdk.colour_print({ colour = Colours.GRAY, message = "  Using vgmstream: " .. vgmstream_exe })

-- Locate active Audio directory (robust scans)
---@type string|nil
local audio_dir = nil
---@type string[]
local candidates = {
    join(opts.GameDir, "A1_Audio"),
    join(opts.GameDir, "audiostreams"),
    opts.GameDir
}
for _, cand in ipairs(candidates) do
    if sdk.is_dir(cand) then
        local found_mus = false
        local files = sdk.list_dir(cand)
        if files then
            for _, f in ipairs(files) do
                if f:lower():sub(-4) == ".mus" then
                    found_mus = true
                    break
                end
            end
        end
        if found_mus then
            audio_dir = cand
            break
        end
    end
end

if not audio_dir then
    audio_dir = join(opts.GameDir, "A1_Audio")
    sdk.colour_print({ colour = Colours.YELLOW, message = "  Warning: No directories with .mus folders found. Defaulting to: " .. audio_dir })
else
    sdk.colour_print({ colour = Colours.WHITE, message = "  Active Audio Folder: " .. audio_dir })
end

-- Ensure target Music directory exists
---@type string
local music_dir = join(audio_dir, "Music")
sdk.ensure_dir(music_dir)
sdk.colour_print({ colour = Colours.WHITE, message = "  Output Directory: " .. music_dir })

-- Mapping logic from original PowerShell
---@param filename string
---@return string
local function GetFriendlyFolderName(filename)
    -- Strip potential suffix & extension
    local name = filename:lower():gsub("_mus%.mus", ""):gsub("%.mus", "")
    ---@type table<string, string>
    local mapping = {
        menu = "A2_Menu",
        loc = "L01_LandOfChocolate",
        brt = "L02_BartmanBegins",
        ["80b"] = "L03_HungryHungryHomer",
        treetemp = "L04_TreeHugger",
        mob = "L05_MobRules",
        cheater = "L06_EnterTheCheatrix",
        dod = "L07_DayOfTheDolphin",
        scd = "L08_TheColossalDonut",
        sss = "L09_Invasion",
        bin = "L10_BargainBin",
        nvq = "L11_NeverQuest",
        gts = "L12_GrandTheftScratchy",
        moh = "L13_MedalOfHomer",
        bsh = "L14_BigSuperHappy",
        rwc = "L15_Rhymes",
        mtp = "L16_MeetThyPlayer",
        hub = "LHub-00_GameHub",
        spr = "LHub-00_SprHub"
    }
    return mapping[name] or name:gsub(" ", "_")
end

-- Collect .mus files to establish loop count
---@type string[]
local mus_files = {}
---@type string[]|nil
local listed = sdk.list_dir(audio_dir)
if listed then
    for _, f in ipairs(listed) do
        if f:lower():sub(-4) == ".mus" and sdk.is_file(join(audio_dir, f)) then
            table.insert(mus_files, f)
        end
    end
end

if #mus_files == 0 then
    sdk.colour_print({ colour = Colours.YELLOW, message = "No .mus files found in " .. audio_dir })
    progress.script.start(1, "Convert Music Files")
    progress.script.step("No files to process")
    progress.script.finish()
    return
end

sdk.colour_print({ colour = Colours.WHITE, message = string.format("Found %d music files to process.", #mus_files) })

-- Initialize progress tracking
progress.script.start(#mus_files, "Extracting and Converting Music")

for idx, filename in ipairs(mus_files) do
    ---@type string
    local folderName = GetFriendlyFolderName(filename)
    ---@type string
    local outputDir = join(music_dir, folderName)
    sdk.ensure_dir(outputDir)

    progress.script.step(string.format("(%d/%d) %s -> %s", idx, #mus_files, filename, folderName))
    sdk.colour_print({ colour = Colours.WHITE, message = string.format("\n--- Processing %d of %d: %s -> %s ---", idx, #mus_files, filename, folderName) })

    -- 1. Extract SNR/SNS using QuickBMS
    -- Command format: quickbms.exe -o <script> <archive> <output_folder>
    ---@type string
    local input_archive = join(audio_dir, filename)
    sdk.colour_print({ colour = Colours.GRAY, message = "  Extracting archive via QuickBMS..." })

    local bms_result = sdk.run_process({ bms_exe, "-o", opts.bmsscript, input_archive, outputDir }, { capture_stdout = true, capture_stderr = true })

    if bms_result and bms_result.success then
        sdk.colour_print({ colour = Colours.GREEN, message = "  Extraction successful." })

        -- 2. Convert each .snr to .wav using vgmstream
        ---@type string[]|nil
        local extracted_files = sdk.list_dir(outputDir)
        local conv_count = 0
        if extracted_files then
            for _, ext_file in ipairs(extracted_files) do
                if ext_file:lower():sub(-4) == ".snr" then
                    ---@type string
                    local snr_path = join(outputDir, ext_file)
                    ---@type string
                    local wav_path = join(outputDir, ext_file:sub(1, -5) .. ".wav")

                    sdk.colour_print({ colour = Colours.GRAY, message = "    Decoding to WAV: " .. ext_file })
                    local vgm_res = sdk.run_process({ vgmstream_exe, "-o", wav_path, snr_path }, { capture_stdout = true, capture_stderr = true })

                    if vgm_res and vgm_res.success then
                        conv_count = conv_count + 1
                    else
                        sdk.colour_print({ colour = Colours.RED, message = "    Failed decoding: " .. ext_file })
                    end
                end
            end
        end
        sdk.colour_print({ colour = Colours.GREEN, message = string.format("  Decoded %d file(s) to WAV.", conv_count) })

        -- 3. Cleanup intermediate .snr and .sns files
        -- We re-query the directory contents for cleanup to ensure we get any intermediate or leftover files
        ---@type string[]|nil
        local final_files = sdk.list_dir(outputDir)
        local clean_count = 0
        if final_files then
            for _, final_file in ipairs(final_files) do
                local ext = final_file:lower():sub(-4)
                if ext == ".snr" or ext == ".sns" then
                    sdk.remove_file(join(outputDir, final_file))
                    clean_count = clean_count + 1
                end
            end
        end
        sdk.colour_print({ colour = Colours.GRAY, message = string.format("  Cleaned up %d temporary files.", clean_count) })
    else
        sdk.colour_print({ colour = Colours.RED, message = "  Extraction failed for " .. filename })
        if bms_result and bms_result.stderr and bms_result.stderr ~= "" then
            sdk.colour_print({ colour = Colours.RED, message = "  Error: " .. bms_result.stderr })
        end
    end
end

progress.script.finish()
sdk.colour_print({ colour = Colours.GREEN, message = "=== Music extraction and conversion complete! ===" })

