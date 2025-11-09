--[[
SetupAudioDir.lua

Purpose:
- Prepare the audio source directory by grouping subfolders into 'EN' and 'Global'.
- Skips language-specific folders in a blacklist.

Behavior parity with SetupAudioDir.py:
- Validates provided source directory path.
- Creates 'EN' and 'Global' subdirectories if missing.
- Moves top-level subdirectories (except EN/Global and language code folders) into the target bucket:
  - If the name is in the hardcoded Global set -> move under Global/<name>
  - Otherwise -> move under EN/<name>
- Prints progress and a final summary with counts.

Runtime:
- Integrates with RemakeEngine's Lua runtime (MoonSharp) and uses global 'sdk' helpers when available.
- Accepts the source dir as argv[1]; if missing, prompts the user.
]]

local lfs = require("lfs")
local sdk = rawget(_G, "sdk")

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
	if sdk and sdk.is_dir then return sdk.is_dir(p) end
	local a = lfs.attributes(p)
	return a and a.mode == "directory" or false
end
local function path_exists(p)
	if sdk and sdk.path_exists then return sdk.path_exists(p) end
	return lfs.attributes(p) ~= nil
end
local function ensure_dir(p)
	if sdk and sdk.ensure_dir then return sdk.ensure_dir(p) end
	-- basic fallback
	local ok = lfs.mkdir(p)
	if ok then return true end
	-- try to create parents
	local parts = {}
	for part in p:gmatch("[^/\\]+") do table.insert(parts, part) end
	local cur = (p:sub(1,1) == "/" or p:match("^%a:[/\\]")) and p:sub(1,1) or ""
	for i=1,#parts do
		cur = (cur == "" and parts[i]) or join(cur, parts[i])
		lfs.mkdir(cur)
	end
	return is_dir(p)
end
local function move_dir(src, dst)
	-- Prefer engine fast move if available
	if sdk and sdk.move_dir then
		local ok = sdk.move_dir(src, dst, false)
		if ok then return true end
	end
	-- fallback: try os.rename (same volume)
	if os.rename(src, dst) then return true end
	-- fallback: copy then remove
	local function copy_tree(s, d)
		ensure_dir(d)
		for name in lfs.dir(s) do
			if name ~= "." and name ~= ".." then
				local sp = join(s, name)
				local dp = join(d, name)
				local attr = lfs.attributes(sp)
				if attr and attr.mode == "directory" then
					if not copy_tree(sp, dp) then return false end
				else
					local inF = io.open(sp, "rb"); if not inF then return false end
					local data = inF:read("*a"); inF:close()
					local outF = io.open(dp, "wb"); if not outF then return false end
					outF:write(data); outF:close()
				end
			end
		end
		return true
	end
	local function remove_tree(p)
		for name in lfs.dir(p) do
			if name ~= "." and name ~= ".." then
				local child = join(p, name)
				local attr = lfs.attributes(child)
				if attr and attr.mode == "directory" then
					remove_tree(child)
				else
					os.remove(child)
				end
			end
		end
		lfs.rmdir(p)
	end
	if copy_tree(src, dst) then
		remove_tree(src)
		return true
	end
	return false
end

-- Colour print via SDK if available
local function cprint(colour, message)
	if sdk and (sdk.colour_print or sdk.color_print) then
		local fn = sdk.colour_print or sdk.color_print
		fn({ colour = colour or "default", message = message or "", newline = true })
	else
		print(message)
	end
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
	-- MoonSharp exposes C# array as userdata; try safe indexing
	local a = rawget(_G, "argv")
	if a ~= nil then
		local ok, v = pcall(function() return a[1] end)
		if ok and type(v) == "string" and v ~= "" then return v end
		-- some launchers may pass 0-based; try [0]
		ok, v = pcall(function() return a[0] end)
		if ok and type(v) == "string" and v ~= "" then return v end
	end
	return nil
end

local function prompt(msg)
	io.write(msg .. "\n")
	io.flush()
	return io.read()
end

local function main()
	local input = parse_argv()
	if not input or input == "" then
		input = prompt("Enter Audio Source Directory path:") or ""
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

	-- check if input dir contains audiostreams/ folder or the Assets_1_Audio_Streams/ folder
	if path_exists(join(input, "audiostreams")) then
		input = join(input, "audiostreams")
	elseif path_exists(join(input, "Assets_1_Audio_Streams")) then
		input = join(input, "Assets_1_Audio_Streams")
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

