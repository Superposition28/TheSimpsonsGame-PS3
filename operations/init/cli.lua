---@class InitCliArguments
---@field platform string|nil
---@field region string|nil
---@field path string|nil
---@field action string|nil
---@field us_path string|nil
---@field us_action string|nil

---@class InitCli
local Cli = {}

---@param flag string
---@return string
local function NormalizeFlag(flag)
    return flag:lower():gsub("_", "-")
end

--- Parses operation arguments injected by MoonSharp through argc and argv.
--- Supported path aliases preserve compatibility with earlier test scripts.
---@return InitCliArguments
function Cli.parse_args()
    ---@type InitCliArguments
    local arguments = {}

    for index = 1, argc do
        local flag = argv[index]
        local value = index < argc and argv[index + 1] or nil
        if type(flag) == "string" then
            local normalized_flag = NormalizeFlag(flag)
            if normalized_flag == "--platform" then
                arguments.platform = value
            elseif normalized_flag == "--region" then
                arguments.region = value
            elseif normalized_flag == "--path" or normalized_flag == "--main-source-path" then
                arguments.path = value
            elseif normalized_flag == "--action" then
                arguments.action = value
            elseif normalized_flag == "--us-path" then
                arguments.us_path = value
            elseif normalized_flag == "--us-action" then
                arguments.us_action = value
            end
        end
    end

    return arguments
end

return Cli