--[[
EA FONT v6 (big-endian .inf) to Godot-compatible AngelCode BMFont .fnt.
Lua counterpart of inf_to_fnt.Fonts.py, using Remake Engine's sandboxed SDK.

Options: --input-dir/-i DIR, --output-dir/-o DIR, --copy-png,
        --no-unicode-aliases, --help/-h.
Without --output-dir, descriptors are written beside their .inf files. PNG
references use forward slashes; --copy-png copies the atlas beside the output.
The 24-byte glyph layout, six-byte kerning preamble, truncated kerning handling,
raw character IDs and optional Unicode aliases match the Python implementation.
]]

---@class InfGlyph
---@field CharCode integer|table<integer, integer>
---@field Width integer
---@field Height integer
---@field XAdvance integer
---@field XOffset integer
---@field YOffset integer
---@field X integer
---@field Y integer
---@field X1 integer
---@field Y1 integer
---@field Index integer Original order, for stable sorting of duplicate IDs.

---@class InfKerning
---@field FirstChar integer|table<integer, integer>
---@field SecondChar integer|table<integer, integer>
---@field Amount integer

---@class InfFont
---@field FilePath string
---@field GlyphCount integer
---@field MaxGlyphWidth integer
---@field LineHeight integer
---@field Baseline integer
---@field DeclaredKerningCount integer
---@field Glyphs InfGlyph[]
---@field Kernings InfKerning[]

---@class InfFontOptions
---@field InputDir string
---@field OutputDir string|nil
---@field CopyPng boolean
---@field IncludeUnicodeAliases boolean
---@field Help boolean

---@class InfCharEntry
---@field Id integer|table<integer, integer>
---@field Glyph InfGlyph
---@field Index integer Original order, for stable sorting of duplicate IDs.

---@type table<integer, integer>
local ExtendedUnicodeAliases = {
    [0xAC] = 0x2122, -- Trade mark sign.
    [0xB1] = 0x0160, -- Capital S with caron.
    [0xB2] = 0x0152, -- Capital ligature OE.
    [0xB3] = 0x0161, -- Small s with caron.
    [0xBC] = 0x221E, -- Infinity / Simpsons special symbol.
    [0xBD] = 0x20AC, -- Euro sign.
    [0xBE] = 0x0153, -- Small ligature oe.
}
local ButtonPuaBase = 0xE000
local IsWindows = sdk.is_absolute("C:/")

--- Split paths into components for archive matching and relative PNG references.
---@param Path string
---@return string[]
local function PathParts(Path)
    local Parts = {}
    for Part in Path:gsub("\\", "/"):gmatch("[^/]+") do
        Parts[#Parts + 1] = Part
    end
    return Parts
end

---@param Text string
---@return string
local function PathKey(Text)
    return IsWindows and Text:lower() or Text
end

--- Match pathlib's component-wise path ordering (case insensitive on Windows).
---@param Left string
---@param Right string
---@return boolean
local function PathLess(Left, Right)
    local LeftParts, RightParts = PathParts(Left), PathParts(Right)
    for Index = 1, math.min(#LeftParts, #RightParts) do
        local LeftKey, RightKey = PathKey(LeftParts[Index]), PathKey(RightParts[Index])
        if LeftKey ~= RightKey then
            return LeftKey < RightKey
        end
    end
    return #LeftParts < #RightParts
end

---@param Path string
---@return string
local function FileName(Path)
    return Path:match("[^/\\]+$") or Path
end

---@param Path string
---@return string
local function Stem(Path)
    return (FileName(Path):gsub("%.[^.]*$", ""))
end

---@param Name string
---@return string
local function StripHashSuffix(Name)
    return (Name:gsub("_%x%x%x%x%x%x$", ""))
end

--- Return an os.path.relpath-style reference, including ../ segments.
---@param Path string Absolute path.
---@param BaseDir string Absolute directory.
---@return string
local function RelativePath(Path, BaseDir)
    local Parts, BaseParts = PathParts(Path), PathParts(BaseDir)
    assert(not IsWindows or PathKey(Parts[1]) == PathKey(BaseParts[1]),
        "Cannot make a relative PNG reference across drives; use --copy-png.")
    local Common = 0
    while Common < math.min(#Parts, #BaseParts)
        and PathKey(Parts[Common + 1]) == PathKey(BaseParts[Common + 1]) do
        Common = Common + 1
    end
    local Result = {}
    for Index = Common + 1, #BaseParts do
        Result[#Result + 1] = ".."
    end
    for Index = Common + 1, #Parts do
        Result[#Result + 1] = Parts[Index]
    end
    return #Result > 0 and table.concat(Result, "/") or "."
end

--- Read bytes through io.open: SDK text helpers decode binary data as UTF-8.
---@param Path string
---@param Count integer|nil Read the whole file when nil.
---@return string
local function ReadBinary(Path, Count)
    local Handle, Message = io.open(Path, "rb")
    assert(Handle, Message or ("Could not open " .. Path))
    ---@cast Handle FileHandle
    local Data = Handle:read(Count or "*a") or ""
    Handle:close()
    return Data
end

--- Read a big-endian integer using zero-based file offsets, without Lua 5.3 operators.
--- MoonSharp string.byte ASCII-encodes high bytes as 63; string.unicode preserves
--- the 0..255 codepoints returned by the engine's Latin-1 binary reader.
---@param Data string
---@param Offset integer
---@param Count integer
---@param Signed boolean|nil
---@return integer
local function ReadInteger(Data, Offset, Count, Signed)
    assert(Offset >= 0 and Offset + Count <= #Data, "Truncated binary integer.")
    local Value = 0
    for Index = Offset + 1, Offset + Count do
        Value = Value * 256 + string.unicode(Data, Index)
    end
    local Range = 256 ^ Count
    if Signed and Value >= Range / 2 then
        Value = Value - Range
    end
    return Value
end

--- Validate FONT headers, signed bearings, fixed-point rectangles and surviving kernings.
---@param Path string
---@return InfFont
local function ParseInfFile(Path)
    local Data = ReadBinary(Path)
    local Name = FileName(Path)
    assert(#Data >= 0x434, Name .. ": File too small (1076 bytes minimum).")
    assert(Data:sub(1, 4) == "FONT", Name .. ": Invalid magic, expected FONT.")
    assert(ReadInteger(Data, 4, 4) == #Data, Name .. ": Header size mismatch.")
    local GlyphCount = ReadInteger(Data, 0x0A, 2)
    local GlyphOffset = ReadInteger(Data, 0x0C, 4)
    local DeclaredKerningCount = ReadInteger(Data, 0x428, 2)
    local KerningOffset = ReadInteger(Data, 0x42C, 4)
    assert(GlyphOffset + GlyphCount * 24 <= #Data, Name .. ": Glyph table exceeds file size.")
    ---@type InfFont
    local Font = {
        FilePath = Path, GlyphCount = GlyphCount,
        MaxGlyphWidth = ReadInteger(Data, 0x14, 4),
        LineHeight = ReadInteger(Data, 0x18, 4),
        Baseline = ReadInteger(Data, 0x1C, 4),
        DeclaredKerningCount = DeclaredKerningCount, Glyphs = {}, Kernings = {},
    }
    for Index = 0, GlyphCount - 1 do
        local Offset = GlyphOffset + Index * 24
        assert(string.unicode(Data, Offset + 2) == 0, string.format("%s: Unexpected non-zero char pad at glyph %d.", Name, Index))
        ---@type InfGlyph
        local Glyph = {
            CharCode = string.unicode(Data, Offset + 1), Index = Index,
            Width = ReadInteger(Data, Offset + 2, 2),
            Height = ReadInteger(Data, Offset + 4, 2),
            XAdvance = ReadInteger(Data, Offset + 6, 2),
            XOffset = ReadInteger(Data, Offset + 8, 2, true),
            YOffset = ReadInteger(Data, Offset + 10, 2, true),
            X = math.floor(ReadInteger(Data, Offset + 12, 2) / 16),
            Y = math.floor(ReadInteger(Data, Offset + 14, 2) / 16),
            X1 = math.floor(ReadInteger(Data, Offset + 16, 2) / 16),
            Y1 = math.floor(ReadInteger(Data, Offset + 18, 2) / 16),
        }
        assert(Glyph.X1 - Glyph.X == Glyph.Width and Glyph.Y1 - Glyph.Y == Glyph.Height,
            string.format("%s: Glyph %d (char 0x%02X) UV box does not match WxH.", Name, Index, Glyph.CharCode))
        Font.Glyphs[#Font.Glyphs + 1] = Glyph
    end
    -- EA's exporter truncated the tail: consume only complete four-byte records
    -- after the six-byte preamble, stopping on padding just like the Python reader.
    if DeclaredKerningCount > 0 and KerningOffset > 0 then
        local Offset = KerningOffset + 6
        while Offset + 4 <= #Data and #Font.Kernings < DeclaredKerningCount do
            local First = string.unicode(Data, Offset + 1)
            local Second = string.unicode(Data, Offset + 2)
            local Pad = string.unicode(Data, Offset + 3)
            if Pad ~= 0 then
                break
            end
            if First ~= 0 and Second ~= 0 then
                Font.Kernings[#Font.Kernings + 1] = {
                    FirstChar = First, SecondChar = Second,
                    Amount = ReadInteger(Data, Offset + 3, 1, true),
                }
            end
            Offset = Offset + 4
        end
    end
    return Font
end

---@param Path string
---@return integer Width, integer Height
local function ReadPngDimensions(Path)
    local Header = ReadBinary(Path, 24)
    assert(#Header >= 24 and Header:sub(1, 8) == "\137PNG\r\n\26\n"
        and Header:sub(13, 16) == "IHDR", "Invalid or corrupt PNG header in " .. Path)
    return ReadInteger(Header, 16, 4), ReadInteger(Header, 20, 4)
end

--- Discover once, then sort to make texture fallback selection deterministic.
---@param Directory string
---@param InfFiles string[]
---@param PngFiles string[]
---@return nil
local function FindFiles(Directory, InfFiles, PngFiles)
    for _, Name in ipairs(sdk.list_dir(Directory)) do
        local Path = join(Directory, Name)
        if sdk.is_dir(Path) then
            -- pathlib.rglob does not recurse into directory symlinks by default.
            if not sdk.is_symlink(Path) then
                FindFiles(Path, InfFiles, PngFiles)
            end
        else
            local Extension = PathKey(Name):match("%.[^.]+$")
            if Extension == ".inf" then
                InfFiles[#InfFiles + 1] = Path
            elseif Extension == ".png" then
                PngFiles[#PngFiles + 1] = Path
            end
        end
    end
end

--- Prefer a matching clean name in the same first two archive components.
---@param InfPath string
---@param PngFiles string[]
---@param RootDir string
---@return string
local function MatchPngForInf(InfPath, PngFiles, RootDir)
    local CleanName = StripHashSuffix(Stem(InfPath)):lower()
    local InfParts = PathParts(RelativePath(InfPath, RootDir))
    local Fallback = nil
    for _, PngPath in ipairs(PngFiles) do
        if StripHashSuffix(Stem(PngPath)):lower() == CleanName then
            Fallback = Fallback or PngPath
            local PngParts = PathParts(RelativePath(PngPath, RootDir))
            local SameArchive = true
            for Index = 1, math.min(2, #InfParts) do
                if not PngParts[Index] or PathKey(PngParts[Index]) ~= PathKey(InfParts[Index]) then
                    SameArchive = false
                end
            end
            if SameArchive then
                return PngPath
            end
        end
    end
    assert(Fallback, "Could not find a matching .png texture for " .. InfPath .. " (clean name: '" .. CleanName .. "').")
    return Fallback
end

---@param Left InfGlyph
---@param Right InfGlyph
---@return boolean
local function GlyphLess(Left, Right)
    if Left.CharCode == Right.CharCode then
        return Left.Index < Right.Index
    end
    return Left.CharCode < Right.CharCode
end

---@param Left InfCharEntry
---@param Right InfCharEntry
---@return boolean
local function CharEntryLess(Left, Right)
    if Left.Id == Right.Id then
        return Left.Index < Right.Index
    end
    return Left.Id < Right.Id
end

--- Serialize with the same ordering, whitespace and LF terminators as Python.
---@param Font InfFont
---@param FaceName string
---@param PngRelativePath string
---@param ScaleW integer
---@param ScaleH integer
---@param IncludeUnicodeAliases boolean
---@return string
local function FormatBmFont(Font, FaceName, PngRelativePath, ScaleW, ScaleH, IncludeUnicodeAliases)
    local LowerFace = FaceName:lower()
    local Bold = LowerFace:find("bold", 1, true) and 1 or 0
    local LineHeight = Font.LineHeight > 0 and Font.LineHeight or 60
    local Base = Font.Baseline > 0 and Font.Baseline or LineHeight
    local IsButtonFont = LowerFace:sub(1, 7) == "buttons"
    ---@type InfCharEntry[]
    local CharEntries = {}
    ---@type table<integer, boolean>
    local SeenIds = {}
    table.sort(Font.Glyphs, GlyphLess)
    for _, Glyph in ipairs(Font.Glyphs) do
        assert(Glyph.X + Glyph.Width <= ScaleW and Glyph.Y + Glyph.Height <= ScaleH,
            string.format("%s: Glyph 0x%02X rect exceeds PNG dimensions (%dx%d).",
                FileName(Font.FilePath), Glyph.CharCode, ScaleW, ScaleH))
        CharEntries[#CharEntries + 1] = { Id = Glyph.CharCode, Glyph = Glyph, Index = #CharEntries + 1 }
        SeenIds[Glyph.CharCode] = true
        if IncludeUnicodeAliases then
            local Alias = ExtendedUnicodeAliases[Glyph.CharCode]
            if IsButtonFont and Glyph.CharCode <= 0x20 then
                Alias = ButtonPuaBase + Glyph.CharCode
            end
            if Alias and not SeenIds[Alias] then
                CharEntries[#CharEntries + 1] = { Id = Alias, Glyph = Glyph, Index = #CharEntries + 1 }
                SeenIds[Alias] = true
            end
        end
    end
    table.sort(CharEntries, CharEntryLess)
    ---@type string[]
    local KerningLines = {}
    ---@type table<string, boolean>
    local SeenPairs = {}
    for _, Kerning in ipairs(Font.Kernings) do
        local FirstIds, SecondIds = { Kerning.FirstChar }, { Kerning.SecondChar }
        if IncludeUnicodeAliases and not IsButtonFont then
            FirstIds[2] = ExtendedUnicodeAliases[Kerning.FirstChar]
            SecondIds[2] = ExtendedUnicodeAliases[Kerning.SecondChar]
        end
        for _, FirstId in ipairs(FirstIds) do
            for _, SecondId in ipairs(SecondIds) do
                local Key = string.format("%d:%d", FirstId, SecondId)
                if not SeenPairs[Key] then
                    SeenPairs[Key] = true
                    KerningLines[#KerningLines + 1] = string.format(
                        "kerning first=%d second=%d amount=%d", FirstId, SecondId, Kerning.Amount)
                end
            end
        end
    end
    local Lines = {
        string.format('info face="%s" size=%d bold=%d italic=0 charset="" unicode=1 stretchH=100 smooth=1 aa=1 padding=0,0,0,0 spacing=1,1 outline=0',
            FaceName, LineHeight, Bold),
        string.format("common lineHeight=%d base=%d scaleW=%d scaleH=%d pages=1 packed=0 alphaChnl=0 redChnl=0 greenChnl=0 blueChnl=0",
            LineHeight, Base, ScaleW, ScaleH),
        string.format('page id=0 file="%s"', PngRelativePath),
        string.format("chars count=%d", #CharEntries),
    }
    for _, Entry in ipairs(CharEntries) do
        local Glyph = Entry.Glyph
        Lines[#Lines + 1] = string.format(
            "char id=%d x=%d y=%d width=%d height=%d xoffset=%d yoffset=%d xadvance=%d page=0 chnl=15",
            Entry.Id, Glyph.X, Glyph.Y, Glyph.Width, Glyph.Height,
            Glyph.XOffset, Glyph.YOffset, Glyph.XAdvance)
    end
    if #KerningLines > 0 then
        Lines[#Lines + 1] = string.format("kernings count=%d", #KerningLines)
        for _, Line in ipairs(KerningLines) do
            Lines[#Lines + 1] = Line
        end
    end
    return table.concat(Lines, "\n") .. "\n"
end

---@param Arguments string[]
---@return InfFontOptions
local function ParseArguments(Arguments)
    ---@type InfFontOptions
    local Options = {
        InputDir = join(Game_Root, "GameFiles", "PS3-EU-FullFlattened-audio_reorg-isRenamed"),
        CopyPng = false, IncludeUnicodeAliases = true, Help = false,
    }
    local Index = 1
    while Index <= #Arguments do
        local Argument = Arguments[Index]
        local Option, InlineValue = Argument:match("^(%-%-[^=]+)=(.*)$")
        Option = Option or Argument
        if Option == "--input-dir" or Option == "-i" or Option == "--output-dir" or Option == "-o" then
            local Value = InlineValue
            if not Value then
                Index = Index + 1
                Value = Arguments[Index]
            end
            assert(Value and Value ~= "" and Value:sub(1, 1) ~= "-", Option .. " requires a directory.")
            if Option == "--input-dir" or Option == "-i" then
                Options.InputDir = Value
            else
                Options.OutputDir = Value
            end
        elseif Option == "--copy-png" and not InlineValue then
            Options.CopyPng = true
        elseif Option == "--no-unicode-aliases" and not InlineValue then
            Options.IncludeUnicodeAliases = false
        elseif (Option == "--help" or Option == "-h") and not InlineValue then
            Options.Help = true
        else
            assert(false, "Unknown argument: " .. Argument)
        end
        Index = Index + 1
    end
    Options.InputDir = sdk.absolute_path(Options.InputDir)
    if Options.OutputDir then
        Options.OutputDir = sdk.absolute_path(Options.OutputDir)
    end
    return Options
end

---@param Options InfFontOptions
---@return integer ConvertedCount
local function ConvertAllFonts(Options)
    assert(sdk.path_exists(Options.InputDir), "Input directory does not exist: " .. Options.InputDir)
    local InfFiles, PngFiles = {}, {}
    ---@cast InfFiles table<string>

    FindFiles(Options.InputDir, InfFiles, PngFiles)
    table.sort(InfFiles, PathLess)
    table.sort(PngFiles, PathLess)
    if #InfFiles == 0 then
        print("[WARN] No .inf files found under: " .. Options.InputDir)
        return 0
    end
    print(string.format("Found %d .inf font file(s) and %d .png texture(s) under %s\n", #InfFiles, #PngFiles, Options.InputDir))

    for _, InfPath in ipairs(InfFiles) do
        ---@cast InfPath string

        local Font = ParseInfFile(InfPath)
        local PngPath = MatchPngForInf(InfPath, PngFiles, Options.InputDir)
        local ScaleW, ScaleH = ReadPngDimensions(PngPath)
        local TargetDir = Options.OutputDir or InfPath:match("^(.*)[/\\][^/\\]+$")
        assert(sdk.ensure_dir(TargetDir), "Could not create output directory: " .. TargetDir)
        local FntPath = join(TargetDir, Stem(InfPath) .. ".fnt")
        local PngRelativePath
        if Options.CopyPng then
            local CopiedPngPath = join(TargetDir, FileName(PngPath))
            if PathKey(sdk.realpath(CopiedPngPath) or sdk.absolute_path(CopiedPngPath))
                ~= PathKey(sdk.realpath(PngPath) or sdk.absolute_path(PngPath)) then
                assert(sdk.copy_file(PngPath, CopiedPngPath, true), "Could not copy PNG: " .. PngPath)
            end
            PngRelativePath = FileName(PngPath)
        else
            PngRelativePath = RelativePath(PngPath, TargetDir)
        end
        local Content = FormatBmFont(Font, StripHashSuffix(Stem(InfPath)), PngRelativePath,
            ScaleW, ScaleH, Options.IncludeUnicodeAliases)
        assert(sdk.write_file(FntPath, Content), "Could not write output: " .. FntPath)
        print("[OK] " .. RelativePath(InfPath, Options.InputDir))
        print(string.format("     -> Texture : %s (%dx%d px)", RelativePath(PngPath, Options.InputDir), ScaleW, ScaleH))
        print(string.format("     -> Metrics : glyphs=%d, lineHeight=%dpx, base=%dpx, maxW=%dpx, kernings=%d/%d",
            Font.GlyphCount, Font.LineHeight, Font.Baseline, Font.MaxGlyphWidth, #Font.Kernings, Font.DeclaredKerningCount))
        print(string.format('     -> Output  : %s (page file="%s")\n',
            Options.OutputDir and FntPath or RelativePath(FntPath, Options.InputDir), PngRelativePath))
    end
    print(string.format("Successfully converted %d/%d .inf font files to Godot .fnt format.", #InfFiles, #InfFiles))
    return #InfFiles
end

---@return nil
local function Main()
    local Options = ParseArguments(argv or {})
    if Options.Help then
        print("Convert The Simpsons Game (PS3) .inf fonts to Godot-compatible AngelCode .fnt files.\n"
            .. "Options: --input-dir/-i DIR, --output-dir/-o DIR, --copy-png, --no-unicode-aliases, --help/-h\n"
            .. "Default input: " .. Options.InputDir .. "\nDefault output: beside each .inf file.")
        return
    end
    ConvertAllFonts(Options)
end

local Success, Message = pcall(Main)
if not Success then
    print("[ERROR] " .. tostring(Message))
    os.exit(1)
end
