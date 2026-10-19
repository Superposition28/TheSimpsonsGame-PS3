-- Audio-specific path validation; general path helpers come from SharedUtils.
---@type SharedUtils
import("../SharedUtils.lua")

---@class AudioPaths
---@field Require fun(Condition: any, Message: string): nil
---@field Component fun(Value: string): string
---@field Relative fun(Value: string): string
---@field Absolute fun(Path: string): string
---@field NoLinks fun(Path: string): nil
---@field Managed fun(Path: string): string
---@field Parent fun(Path: string): string
---@field Filename fun(Path: string): string
---@field Languages table<string, boolean>

---@param Condition any
---@param Message string
---@return nil
local function Require(Condition, Message)
    -- The engine replaces error() with a logging function. assert() still throws.
    assert(Condition, "Audio V2: " .. Message)
end

---@param Value string
---@return string
local function Component(Value)
    Require(type(Value) == "string" and Value ~= "" and Value ~= "." and Value ~= "..", "invalid path component")
    Require(not Value:find('[\\/:*?"<>|%c]') and not Value:find("[. ]$"), "unsafe component: " .. Value)
    local Stem = Value:upper():match("^[^.]+") or ""
    Require(not ({CON=true, PRN=true, AUX=true, NUL=true})[Stem]
        and not Stem:match("^COM[1-9]$") and not Stem:match("^LPT[1-9]$"), "reserved component: " .. Value)
    for _, Suffix in ipairs({"¹", "²", "³"}) do
        Require(Stem ~= "COM" .. Suffix and Stem ~= "LPT" .. Suffix, "reserved component: " .. Value)
    end
    return Value
end

---@param Value string
---@return string
local function Relative(Value)
    Require(type(Value) == "string" and Value ~= "" and not Value:find("\\", 1, true)
        and Value:sub(1,1) ~= "/" and Value:sub(-1) ~= "/" and not Value:find("//", 1, true), "invalid relative path")
    for Part in Value:gmatch("[^/]+") do Component(Part) end
    return Value
end

---@param Path string
---@return string
local function Absolute(Path)
    local Result = sdk.absolute_path(Path):gsub("\\", "/"):gsub("^//%?/", ""):gsub("/+$", "")
    return Result
end

---@param Path string
---@return nil
local function NoLinks(Path)
    Path = Absolute(Path)
    local Base = Absolute(Game_Root)
    Require(Path:lower() == Base:lower() or Path:lower():sub(1,#Base+1) == Base:lower() .. "/", "path leaves module root")
    while Path ~= "" do
        Require(not (sdk.lexists(Path) and sdk.is_symlink(Path)), "linked path is forbidden: " .. Path)
        if Path:lower() == Base:lower() then break end
        local Parent = Path:match("^(.*)/[^/]+$")
        if not Parent or Parent == Path then break end
        Path = Parent
    end
end

---@param Path string
---@return string
local function Managed(Path)
    Path = Absolute(Path)
    local Base = Absolute(Game_Root) .. "/GameFiles/"
    Require(Path:lower():sub(1, #Base) == Base:lower(), "runtime writes are restricted to GameFiles: " .. Path)
    NoLinks(Path)
    return Path
end

return {Require=Require, Component=Component, Relative=Relative, Absolute=Absolute,
    NoLinks=NoLinks, Managed=Managed, Parent=dirname, Filename=basename,
    Languages={EN=true, ES=true, FR=true, IT=true}}
