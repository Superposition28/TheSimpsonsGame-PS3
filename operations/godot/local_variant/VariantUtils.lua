-- General path and logging functions come from the module's existing utilities.
---@type SharedUtils
import(join(Game_Root, "operations", "SharedUtils.lua"))
import("VariantTypes.lua")

---@param Path string
---@return string
function VariantAbsolute(Path)
    local Result = sdk.absolute_path(Path):gsub("\\", "/"):gsub("^//%?/UNC/", "//"):gsub("^//%?/", "")
    return (Result:gsub("/+$", ""))
end

---@param Path string
---@param Root string
---@return boolean
function VariantWithin(Path, Root)
    local Left, Right = VariantAbsolute(Path), VariantAbsolute(Root)
    if sdk.is_absolute("C:/") then Left, Right = Left:lower(), Right:lower() end
    return Left == Right or Left:sub(1, #Right + 1) == Right .. "/"
end

--- Long imported filenames exceed MoonSharp's greedy-pattern recursion limit.
---@param Path string
---@return string
function VariantParent(Path)
    local Normalized = Path:gsub("\\", "/"):gsub("/+$", "")
    for Index = #Normalized, 1, -1 do
        if Normalized:sub(Index, Index) == "/" then
            if Index == 1 or Index == 3 and Normalized:sub(2, 2) == ":" then return Normalized:sub(1, Index) end
            return Normalized:sub(1, Index - 1)
        end
    end
    return "."
end

--- The SDK's realpath is lexical. Check every ancestor explicitly for links.
---@param Path string
---@return nil
function VariantNoLinks(Path)
    local Current = VariantAbsolute(Path)
    while Current and Current ~= "" do
        -- The SDK reports ReparsePoint for nonexistent paths (attributes=-1).
        -- readlink inspects the link itself; path_exists resolves its target.
        -- Both are needed to distinguish missing outputs from broken junctions.
        if sdk.is_symlink(Current) then
            assert(not sdk.readlink(Current) and not sdk.path_exists(Current), "Linked path is not supported: " .. Current)
        end
        local Parent = VariantParent(Current)
        if Parent == Current or Parent == "." then break end
        Current = Parent
    end
end

--- Allow file-relative ../ dependencies only while they stay inside the root.
---@param Root string
---@param Relative string
---@return string
function VariantCheckedPath(Root, Relative)
    assert(type(Relative) == "string" and not Relative:find(":", 1, true)
        and not Relative:find("%c") and not Relative:match("^[/\\]"), "Unsafe relative path: " .. tostring(Relative))
    local Path = VariantAbsolute(join(Root, Relative))
    assert(VariantWithin(Path, Root), "Path escapes input root: " .. Relative)
    VariantNoLinks(Path)
    return Path
end

---@param Path string
---@return string
function VariantRead(Path)
    local Content = sdk.read_file(Path)
    assert(Content, "Cannot read " .. Path)
    return (Content:gsub("\r\n", "\n"):gsub("\r", "\n"))
end

---@param Path string
---@param Content string
---@return nil
function VariantWrite(Path, Content)
    assert(sdk.write_file(Path, Content), "Cannot write " .. Path)
end

---@param Path string
---@return table
function VariantReadJson(Path)
    local Data = sdk.text.json.decode(VariantRead(Path))
    assert(type(Data) == "table", "Invalid JSON: " .. Path)
    return Data
end

---@param Path string
---@param Data table
---@return nil
function VariantWriteJson(Path, Data)
    VariantWrite(Path, sdk.text.json.encode(Data, { indent = true }) .. "\n")
end

---@param Source string
---@param Target string
---@return nil
function VariantCopy(Source, Target)
    GodotProgressDetail(Target)
    VariantNoLinks(Source)
    VariantNoLinks(Target)
    assert(sdk.ensure_dir(dirname(Target)), "Cannot create " .. dirname(Target))
    assert(sdk.copy_file(Source, Target, true), "Cannot copy " .. Source .. " to " .. Target)
end

---@param Text string
---@param Old string
---@param New string
---@return string
function VariantReplace(Text, Old, New)
    local Parts, Start = {}, 1
    while true do
        local First, Last = Text:find(Old, Start, true)
        if not First then Parts[#Parts + 1] = Text:sub(Start); break end
        Parts[#Parts + 1] = Text:sub(Start, First - 1)
        Parts[#Parts + 1] = New
        Start = Last + 1
    end
    return table.concat(Parts)
end

---@param Path string
---@return string
function VariantExtension(Path)
    return (basename(Path):match("(%.[^.]+)$") or ""):lower()
end

---@param Root string
---@param Relative string
---@param Files string[]
---@param Exclude table<string, boolean>
---@param SkipImports boolean|nil
---@return nil
function VariantFindFiles(Root, Relative, Files, Exclude, SkipImports)
    local Directory = Relative == "" and Root or join(Root, Relative)
    local Names = sdk.list_dir(Directory)
    GodotProgressDiscover(#Names)
    for _, Name in ipairs(Names) do
        local Child = Relative == "" and Name or Relative .. "/" .. Name
        local Path = join(Root, Child)
        if not Exclude[Name] and not Exclude["./" .. Child] and not (SkipImports and Name:match("%.import$")) then
            VariantNoLinks(Path)
            if sdk.is_dir(Path) then VariantFindFiles(Root, Child, Files, Exclude, SkipImports)
            elseif sdk.is_file(Path) then Files[#Files + 1] = Child end
        end
        GodotProgressAdvance(Child)
    end
end

---@param Left string
---@param Right string
---@return boolean
function VariantSameFile(Left, Right)
    -- Native SDK hashing avoids reading large model/engine binaries into Lua.
    local LeftHash, RightHash = sdk.sha1_file(Left), sdk.sha1_file(Right)
    assert(LeftHash and RightHash, "Cannot compare files: " .. Left .. ", " .. Right)
    return LeftHash == RightHash
end

---@param Entries table<string, GodotAssetMapping[]>
---@return GodotAssetMapping[]
function VariantOrderedEntries(Entries)
    local Result = {}
    for _, Uid in ipairs(GodotSortedKeys(Entries)) do
        for _, Entry in ipairs(Entries[Uid]) do Result[#Result + 1] = Entry end
    end
    return Result
end

--- Accept the collision lab's current location as well as older module layouts.
---@return string
function VariantHavokReaderPath()
    local Candidates = {
        join(Game_Root, "operations", "godot", "variant_runtime", "tsg_havok_reader.gd"),
        join(Game_Root, "dev", "tmp", "collisionTest", "scripts", "tsg_havok_reader.gd"),
        join(Game_Root, "Godot", "GodotGame", "collisionTest", "scripts", "tsg_havok_reader.gd"),
        join(Game_Root, "Godot", "GodotGame", "tmp", "collisionTest", "scripts", "tsg_havok_reader.gd"),
    }
    for _, Path in ipairs(Candidates) do
        if sdk.is_file(Path) then return Path end
    end
    assert(false, "The collision lab's tsg_havok_reader.gd was not found")
end
