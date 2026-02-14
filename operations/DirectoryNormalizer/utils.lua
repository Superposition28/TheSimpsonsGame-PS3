local utils = {}

utils.path_sep = package.config:sub(1,1) or "/"

function utils.join(a, b)
    if not a or a == "" then return b end
    if not b or b == "" then return a end
    local last = a:sub(-1)
    if last == "/" or last == "\\" then return a .. b end
    return a .. utils.path_sep .. b
end

function utils.norm_slashes(p)
    if not p then return p end
    if utils.path_sep == "\\" then
        p = p:gsub("/", "\\")
    else
        p = p:gsub("\\", "/")
    end
    p = p:gsub("[/\\]+", utils.path_sep)
    return p
end

function utils.to_posix(p)
    if not p then return p end
    return p:gsub("\\", "/")
end

function utils.split_path(p)
    local parts = {}
    for part in p:gmatch("[^/\\]+") do table.insert(parts, part) end
    return parts
end

function utils.write_all_text(path, data)
    local parent = path:match("^(.*)[/\\][^/\\]+$")
    if parent and parent ~= "" then sdk.ensure_dir(parent) end
    local f = io.open(path, "wb"); if not f then return false end
    f:write(data); f:close(); return true
end

function utils.dirname(p)
    local s = utils.norm_slashes(p)
    local last = 0
    for i=1,#s do
        local ch = s:sub(i,i)
        if ch == '/' or ch == '\\' then last = i end
    end
    if last == 0 then return "" end
    return s:sub(1, last-1)
end

function utils.basename(p)
    local s = utils.norm_slashes(p)
    local last = 0
    for i=1,#s do
        local ch = s:sub(i,i)
        if ch == '/' or ch == '\\' then last = i end
    end
    if last == 0 then return s end
    return s:sub(last+1)
end

function utils.json_encode(obj, indent)
    return sdk.text.json.encode(obj, { indent = indent ~= false })
end

function utils.get_hex_uid(s, length)
    length = length or 6
    local hex = sdk.md5(s) or ""
    if hex == "" then return string.rep("0", length) end -- Fallback
    return string.lower(hex:sub(1, length))
end

function utils.multi_ext(name)
    local idx = nil
    for i = 1, #name do
        if name:sub(i, i) == '.' then
            idx = i
        end
    end
    if not idx then return name, "" end
    return name:sub(1, idx-1), name:sub(idx)
end

function utils.should_ignore_dir(name, ignore_list)
    local lname = string.lower(name)
    for _,ig in ipairs(ignore_list) do
        local v = string.lower(ig or "")
        if v ~= "" and lname == v then return true end
    end
    return false
end

function utils.ext_lower(name)
    local last = nil
    for i=1,#name do
        if name:sub(i,i) == '.' then last = i end
    end
    if not last then return "" end
    return string.lower(name:sub(last))
end

function utils.rel_path(full, root)
    local f = utils.norm_slashes(full)
    local r = utils.norm_slashes(root)
    if f:sub(1, #r) == r then
        local rest = f:sub(#r+1)
        if rest:sub(1,1) == utils.path_sep then rest = rest:sub(2) end
        return rest
    end
    return full
end

function utils.copy_with_collision_handling(src, dst)
    local parent = utils.dirname(dst)
    if parent and parent ~= "" then sdk.ensure_dir(parent) end
    local target = dst
    if sdk.path_exists(target) then
        local ext = utils.ext_lower(dst)
        local base
        if ext ~= "" then
            base = dst:sub(1, #dst - #ext)
        else
            base = dst
        end
        local i = 1
        repeat
            local suffix = (i==1) and "" or tostring(i)
            target = string.format("%s_dup%s%s", base, suffix, ext)
            i = i + 1
        until not sdk.path_exists(target)
    end
    return sdk.copy_file(src, target, false)
end

return utils
