# TheSimpsonsGame-PS3 Game Module AGENTS.md

This file contains game module-specific guidelines that override general engine instructions.

## Lua Type System Requirements

### Class Definitions for Large Objects
For any object that is:
- Reused across multiple files or functions
- Has more than 3 fields
- Forms a core data structure or domain model

Define a `---@class` type definition at the top of the file or in a shared header module.

**Example:**
```lua
---@class Asset
---@field identifier string
---@field filename string
---@field preinstanced_symlink string
---@field blend_symlink string
---@field glb_symlink string
```

### Function Type Annotations - Mandatory
**ALL** functions must include complete type annotations:

1. **Parameter types** - Use `---@param` for every parameter
2. **Return types** - Use `---@return` for all return values
3. **Class parameters** - Reference defined classes when applicable
4. **Union types** - Use `type1|type2` for multiple possible types
5. **Optional parameters** - Suffix with `|nil` for optional values

**Example:**
```lua
---@param asset Asset
---@param export_set table
---@param verbose boolean
---@return boolean ok, boolean run_needed, string|nil reason
local function should_process_asset(asset, export_set, verbose)
    -- implementation
end
```

### Type Definition Patterns

**Tables with known structure:**
```lua
---@class ResultRecord
---@field asset_id string
---@field success boolean
---@field skipped boolean
---@field message string
```

**Arrays with typed elements:**
```lua
---@return table<integer, Asset>
local function load_assets(db_path)
```

**Tables as key-value stores:**
```lua
---@param export_set table<string, boolean>  -- { glb=true?, fbx=true? }
```

**Variadic or complex returns:**
```lua
---@return table set, table ordered
local function normalize_export_formats(list)
```

### IDE Intellisense Benefits
Proper type annotations enable:
- Autocomplete for object fields and methods
- Jump-to-definition for class types
- Inline error checking for type mismatches
- Parameter hints in function calls
- Documentation hover tooltips

### Class Type Reuse
Once a `---@class` is defined in a file, use it consistently:
- As function parameters: `---@param asset Asset`
- In return types: `---@return table<integer, Asset>`
- In local variable casts: `---@cast variable Asset`
- In table fields: `---@field asset Asset`

### Type Casting with `---@cast`
Use `---@cast` when a variable doesn't inherit type information automatically from its context. This is essential for IDE type checking after assignments or in loops.

**When to use `---@cast`:**

1. **Loop iteration over untyped collections:**
```lua
-- Without cast: f is typed as unknown
for _, f in ipairs(failures) do
    ---@cast f { asset_id: string, message: string }
    log(Utils.Colours.RED, string.format("Asset %s: %s", f.asset_id, f.message))
end
```

2. **Function returns that lose type information:**
```lua
-- Without cast: fh is typed as FILE* (generic)
local fh = io.open(batch_file, "w")
if fh then
    ---@cast fh FileHandle
    fh:write(data)
    fh:close()
end
```

3. **Variables extracted from generic containers:**
```lua
local batch_assets = table.remove(batches, 1)
for _, asset in ipairs(batch_assets) do
    ---@cast asset Asset
    local blend_file = Utils.get_path(asset.blend_symlink, asset.filename, ".blend")
end
```

4. **Inline anonymous tables with complex structure:**
```lua
for _, record in ipairs(results) do
    ---@cast record { id: string, status: boolean, error: string|nil }
    if not record.status then
        handle_error(record.error)
    end
end
```

**Cast Syntax:**
```lua
---@cast <variable_name> <type>
```

**Type formats for casts:**
- Class names: `---@cast var Asset`
- Inline tables: `---@cast var { field: type, ... }`
- Unions: `---@cast var string|nil`
- Generics: `---@cast var table<string, any>`
- File handles: `---@cast var FileHandle`

**Key principle:** Place `---@cast` immediately after the line where the variable is assigned or before first use in a context that needs type information.

### Best Practices
1. Define classes near the top of the file after imports
2. Name classes with PascalCase (e.g., `Asset`, `ResultRecord`, `BlenderConfig`)
3. Document class purpose in the `---@class` line if non-obvious
4. Keep class definitions DRY - if a class is needed in multiple files, define it in a shared module
5. Update class definitions when adding/removing fields to data structures
6. Use consistent naming conventions: prefer full field names over abbreviations

### Examples from this module
- See [BlenderCore.lua](operations/Blender/BlenderCore.lua) for proper class and function type usage
- All operation scripts should follow this pattern as reference
