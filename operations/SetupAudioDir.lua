--[[
SetupAudioDir.lua

Purpose:
- Prepare the audio source directory by grouping subfolders into 'EN' and 'Global'.
- Skips language-specific folders in a blacklist.

Runtime guarantees: sdk, argv are provided by engine
]]

local Utils = import("SharedUtils")

-- Hardcoded Language Blacklist and Global Dirs (mirrors Python script)
local language_blacklist = { it=true, es=true, fr=true }
local global_dirs = {
	["80b_crow"]=true, ["amb_airc"]=true, ["amb_chao"]=true, ["amb_cour"]=true, ["amb_dung"]=true, ["amb_ext_"]=true,
	["amb_fore"]=true, ["amb_fren"]=true, ["amb_gara"]=true, ["amb_int_"]=true, ["amb_mans"]=true, ["amb_nort"]=true,
	["amb_riot"]=true, ["amb_shir"]=true, ["amb_vent"]=true, ["bin_rev0"]=true, ["brt_dino"]=true, ["brt_dior"]=true,
	["brt_myst"]=true, ["brt_plan"]=true, ["brt_temp"]=true, ["bsh_air_"]=true, ["bsh_beac"]=true, ["bsh_figh"]=true,
	["bsh_fire"]=true, ["bsh_ice_"]=true, ["bsh_vill"]=true, ["bsh__air"]=true, ["che_cart"]=true, ["che_cent"]=true,
	["che_mark"]=true, ["che_mo_b"]=true, ["che_q_an"]=true, ["dod_aqua"]=true, ["dod_dock"]=true, ["gamehub_"]=true,
	["gts_full"]=true, ["gts_seas"]=true, ["gts_stat"]=true, ["gts_subu"]=true, ["gts_vent"]=true, ["gts_viol"]=true,
	["mtp_heav"]=true, ["mus_simp"]=true, ["sss_cont"]=true, ["sss_lab_"]=true, ["sss_mall"]=true
}

local function lower(s)
	return s and string.lower(s) or s
end

local function parse_argv()
	-- Engine guarantees argv global; try index 1 first, then 0 for compatibility
	if argv and argv[1] and type(argv[1]) == "string" and argv[1] ~= "" then
		return argv[1]
	end
	if argv and argv[0] and type(argv[0]) == "string" and argv[0] ~= "" then
		return argv[0]
	end
	return nil
end

local function main()
	local input = parse_argv()
	if not input or input == "" then
		input = prompt("Enter Audio Source Directory path:", "audio_dir_prompt", false) or ""
	end

	input = Utils.normalize(input)

	if not input or input == "" then
		sdk.colour_print{ colour = "Red", message = "Error: AUDIO_SOURCE_DIR not provided or empty." }
		return
	end
	if not sdk.is_dir(input) then
		sdk.colour_print{ colour = "Red", message = string.format("Error: Audio source directory does not exist: %s", input) }
		return
	end

	-- check if input dir contains audiostreams/ folder or the A1_Audio/ folder
	if sdk.path_exists(Utils.join(input, "audiostreams")) then
		input = Utils.join(input, "audiostreams")
	elseif sdk.path_exists(Utils.join(input, "A1_Audio")) then
		input = Utils.join(input, "A1_Audio")
	end

	local en_dir_name = "EN"
	local global_dir_name = "Global"
	local en_dir_path = Utils.join(input, en_dir_name)
	local global_dir_path = Utils.join(input, global_dir_name)

	sdk.ensure_dir(en_dir_path)
	sdk.ensure_dir(global_dir_path)

	Utils.colour_print({ colour = "cyan", message = string.format("Organizing directories in '%s' into '%s' and '%s'...", input, en_dir_path, global_dir_path) })

	local moved, skipped, errors = 0, 0, 0

	local entries = sdk.list_dir(input)
	for _, name in ipairs(entries) do
		local item = Utils.join(input, name)
		if sdk.is_dir(item) then
			local lname = lower(name)
			if name == en_dir_name or name == global_dir_name or language_blacklist[lname] then
				Utils.colour_print({ colour = "darkgray", message = string.format("Skipping directory: '%s'", name) })
				skipped = skipped + 1
			else
				local parent = global_dirs[name] and global_dir_path or en_dir_path
				local target = Utils.join(parent, name)
				Utils.colour_print({ colour = "gray", message = string.format("Moving '%s' to '%s'...", name, target) })
				if sdk.path_exists(target) then
					Utils.colour_print({ colour = "yellow", message = string.format("Warning: Target directory '%s' already exists. Skipping move for '%s'.", target, name) })
					skipped = skipped + 1
				else
					local ok = sdk.move_dir(item, target, true) -- true = overwrite existing target
					if ok then
						moved = moved + 1
					else
						Utils.colour_print({ colour = "red", message = string.format("Error moving directory %s to %s", name, (global_dirs[name] and global_dir_name or en_dir_name)) })
						errors = errors + 1
					end
				end
			end
		end
	end

	print("Directory organization complete.")
	print(string.format("Moved: %d, Skipped: %d, Errors: %d", moved, skipped, errors))
	print(string.format("Setup operated on Audio Source Dir: %s", input))
end

-- run
main()

