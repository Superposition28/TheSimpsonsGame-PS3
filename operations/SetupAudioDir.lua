--[[
SetupAudioDir.lua

Purpose:
- Prepare the audio source directory by grouping subfolders into 'EN' and 'Global'.
- Skips language-specific folders in a blacklist.

Runtime guarantees: lfs, sdk, argv are provided by engine
]]

local lfs = require("lfs")

-- small path helpers
local path_sep = package.config:sub(1,1) or "/"
local function join(a, b)
	if not a or a == "" then return b end
	if not b or b == "" then return a end
	local last = a:sub(-1)
	if last == "/" or last == "\\" then return a .. b end
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
local function is_dir(p)
	return sdk.is_dir(p)
end
local function path_exists(p)
	return sdk.path_exists(p)
end
local function ensure_dir(p)
	return sdk.ensure_dir(p)
end
local function move_dir(src, dst)
	return sdk.move_dir(src, dst, false)
end

-- Colour print via SDK (guaranteed by engine runtime)
local function cprint(colour, message)
	sdk.colour_print({ colour = colour or "default", message = message or "", newline = true })
end

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

local function lower(s) return s and string.lower(s) or s end

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

local function get_user_input(msg)
	-- Use engine's global prompt() function
	return prompt(msg, "audio_dir_prompt", false)
end

local function main()
	local input = parse_argv()
	if not input or input == "" then
		input = get_user_input("Enter Audio Source Directory path:") or ""
	end

	input = normalize(input)

	if not input or input == "" then
		io.stderr:write("Error: AUDIO_SOURCE_DIR not provided or empty.\n")
		os.exit(1)
	end
	if not is_dir(input) then
		io.stderr:write(string.format("Error: Audio source directory does not exist: %s\n", input))
		os.exit(1)
	end

	-- check if input dir contains audiostreams/ folder or the A1_Audio/ folder
	if path_exists(join(input, "audiostreams")) then
		input = join(input, "audiostreams")
	elseif path_exists(join(input, "A1_Audio")) then
		input = join(input, "A1_Audio")
	end

	local en_dir_name = "EN"
	local global_dir_name = "Global"
	local en_dir_path = join(input, en_dir_name)
	local global_dir_path = join(input, global_dir_name)

	ensure_dir(en_dir_path)
	ensure_dir(global_dir_path)

	cprint("cyan", string.format("Organizing directories in '%s' into '%s' and '%s'...", input, en_dir_path, global_dir_path))

	local moved, skipped, errors = 0, 0, 0

	for name in lfs.dir(input) do
		if name ~= "." and name ~= ".." then
			local item = join(input, name)
			local attr = lfs.attributes(item)
			if attr and attr.mode == "directory" then
				local lname = lower(name)
				if name == en_dir_name or name == global_dir_name or language_blacklist[lname] then
					cprint("darkgray", string.format("Skipping directory: '%s'", name))
					skipped = skipped + 1
				else
					local parent = global_dirs[name] and global_dir_path or en_dir_path
					local target = join(parent, name)
					cprint("gray", string.format("Moving '%s' to '%s'...", name, target))
					if path_exists(target) then
						io.stderr:write(string.format("Warning: Target directory '%s' already exists. Skipping move for '%s'.\n", target, name))
						skipped = skipped + 1
					else
						local ok = move_dir(item, target)
						if ok then
							moved = moved + 1
						else
							io.stderr:write(string.format("Error moving directory %s to %s\n", name, (global_dirs[name] and global_dir_name or en_dir_name)))
							errors = errors + 1
						end
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

