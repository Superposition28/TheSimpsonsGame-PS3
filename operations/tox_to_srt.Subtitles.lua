--[[
EA 1BOT (.tox.PS3) FMV timing tables to SRT, WebVTT and multilingual CSV.
Lua counterpart of tox_to_srt.Subtitles.py for Remake Engine's MoonSharp runtime.

Options: --input-dir/-i DIR, --output-dir/-o DIR, --no-video-pairing,
         --include-speaker, --help/-h.
Outputs default to beside each timing file. Matching A1_Video/<language>
movies also receive SRT/VTT companions unless pairing is disabled or an output
folder is selected. Localization comes from the first non-empty sorted
simpsons_global.{en,es,fr,it,ss}.LH2 table for each language/label column.
Windows-1252 decoding, the known missing Bart scream fallback, CSV CRLF rows,
and subtitle LF separators preserve the Python converter's output.
]]

---@class ToxRecord
---@field Index integer
---@field StringId integer
---@field StartMs integer
---@field DurationMs integer
---@field EndMs integer
---@field Flags integer
---@field Label string
---@field Speaker string
---@field Translations table<string, string>

---@class ToxFile
---@field FilePath string
---@field FileStem string Filename without .tox.PS3, preserving extraction hashes.
---@field CleanStem string Movie name with the six-hex extraction hash removed.
---@field RecordCount integer
---@field Records ToxRecord[]

---@class ToxOptions
---@field InputDir string
---@field OutputDir string|nil
---@field PairVideos boolean
---@field IncludeSpeaker boolean
---@field Help boolean

---@class ToxDiscovery
---@field TimingPaths string[]
---@field LocalizationPaths string[]
---@field VideoPaths string[]

---@class ToxLocalization
---@field LanguageTables table<string, table<integer, string>>
---@field LabelTable table<integer, string>


---@type string[]
local Languages = { "en", "es", "fr", "it" }
local IsWindows = sdk.is_absolute("C:/")

-- Bytes 0xA0..0xFF already have their Unicode values in the Latin-1 IO result.
-- Only 0x80..0x9F need remapping; undefined CP1252 bytes decode as U+FFFD.
---@type table<integer, string>
local Cp1252Overrides = {
    [0x80] = "€", [0x81] = "�", [0x82] = "‚", [0x83] = "ƒ",
    [0x84] = "„", [0x85] = "…", [0x86] = "†", [0x87] = "‡",
    [0x88] = "ˆ", [0x89] = "‰", [0x8A] = "Š", [0x8B] = "‹",
    [0x8C] = "Œ", [0x8D] = "�", [0x8E] = "Ž", [0x8F] = "�",
    [0x90] = "�", [0x91] = "‘", [0x92] = "’", [0x93] = "“",
    [0x94] = "”", [0x95] = "•", [0x96] = "–", [0x97] = "—",
    [0x98] = "˜", [0x99] = "™", [0x9A] = "š", [0x9B] = "›",
    [0x9C] = "œ", [0x9D] = "�", [0x9E] = "ž", [0x9F] = "Ÿ",
}

---@param Path string
---@return string
local function PathKey(Path)
    return IsWindows and Path:lower() or Path
end

---@param Path string
---@return string
local function FileName(Path)
    return Path:match("[^/\\]+$") or Path
end

---@param Path string
---@return string
local function ParentDirectory(Path)
    return assert(Path:match("^(.*)[/\\][^/\\]+$"), "Path has no parent directory: " .. Path)
end

---@param Name string
---@return string
local function StripHashSuffix(Name)
    return (Name:gsub("_%x%x%x%x%x%x$", ""))
end

---@param Path string
---@return string
local function TimingStem(Path)
    local Name = FileName(Path)
    if Name:lower():sub(-8) == ".tox.ps3" then
        return Name:sub(1, -9)
    end
    return (Name:gsub("%.[^.]*$", ""))
end

---@param Path string
---@param Root string
---@return string
local function RelativeDisplay(Path, Root)
    local Prefix = Root:gsub("\\", "/"):gsub("/+$", "")
    return Path:gsub("\\", "/"):sub(#Prefix + 2)
end

--- Cache component keys so sorted fallback selection matches pathlib efficiently.
---@param Paths string[]
---@return nil
local function SortPaths(Paths)
    ---@type table<string, string[]>
    local Keys = {}
    for _, Path in ipairs(Paths) do
        local Parts = {}
        for Part in PathKey(Path):gsub("\\", "/"):gmatch("[^/]+") do
            Parts[#Parts + 1] = Part
        end
        Keys[Path] = Parts
    end
    ---@param Left string
    ---@param Right string
    ---@return boolean
    local function Less(Left, Right)
        local LeftParts, RightParts = Keys[Left], Keys[Right]
        for Index = 1, math.min(#LeftParts, #RightParts) do
            if LeftParts[Index] ~= RightParts[Index] then
                return LeftParts[Index] < RightParts[Index]
            end
        end
        return #LeftParts < #RightParts
    end
    table.sort(Paths, Less)
end

--- Enumerate once without following directory symlinks, as pathlib.rglob does.
---@param Directory string
---@param InputRoot string
---@param Files ToxDiscovery
---@param PairVideos boolean
---@return nil
local function FindFiles(Directory, InputRoot, Files, PairVideos)
    for _, Name in ipairs(sdk.list_dir(Directory)) do
        local Path = join(Directory, Name)
        if sdk.is_dir(Path) then
            if not sdk.is_symlink(Path) then
                FindFiles(Path, InputRoot, Files, PairVideos)
            end
        else
            local Key = PathKey(Name)
            if Key:sub(-8) == PathKey(".tox.PS3") then
                Files.TimingPaths[#Files.TimingPaths + 1] = Path
            elseif Key:sub(-4) == ".LH2" or Key:sub(-4) == ".lh2" then
                Files.LocalizationPaths[#Files.LocalizationPaths + 1] = Path
            elseif PairVideos and (Key:sub(-4) == ".ogv" or Key:sub(-4) == ".vp6")
                and PathKey(RelativeDisplay(Path, InputRoot)):sub(1, 9) == PathKey("A1_Video/") then
                Files.VideoPaths[#Files.VideoPaths + 1] = Path
            end
        end
    end
end

---@param Path string
---@return string
local function ReadBinary(Path)
    local Handle, Message = io.open(Path, "rb")
    assert(Handle, Message or ("Could not open " .. Path))
    ---@cast Handle FileHandle
    local Data = Handle:read("*a") or ""
    Handle:close()
    return Data
end

--- Binary IO returns Latin-1 characters. MoonSharp string.byte ASCII-encodes
--- high bytes as '?', so use string.unicode to preserve all unsigned byte values.
---@param Data string
---@param Offset integer Zero-based byte offset.
---@return integer
local function ReadUInt32(Data, Offset)
    assert(Offset >= 0 and Offset + 4 <= #Data, "Truncated binary integer.")
    local Value = 0
    for Index = Offset + 1, Offset + 4 do
        Value = Value * 256 + string.unicode(Data, Index)
    end
    return Value
end

---@param Character string One Latin-1 character in the 0x80..0x9F range.
---@return string
local function DecodeCp1252Byte(Character)
    return Cp1252Overrides[string.unicode(Character)]
end

---@param Data string Latin-1 binary IO data.
---@param Offset integer Zero-based byte offset.
---@return string Text Windows-1252 decoded to Unicode, replacing undefined bytes.
local function ReadCStringCp1252(Data, Offset)
    if Offset < 0 or Offset >= #Data then
        return ""
    end
    -- MoonSharp's plain find does not match NUL; the Lua %z class does.
    local Terminator = Data:find("%z", Offset + 1) or (#Data + 1)
    -- Preserve the Latin-1 portion in one native substitution; only CP1252's
    -- remapped control range needs Lua callbacks across the localization tables.
    return (Data:sub(Offset + 1, Terminator - 1):gsub("[\128-\159]", DecodeCp1252Byte))
end

--- Only the first text column is used, including in multi-table LH2 files.
---@param Path string
---@return table<integer, string>
local function ParseLh2FirstTable(Path)
    local Data = ReadBinary(Path)
    assert(#Data >= 0x20 and Data:sub(1, 4) == "2HCL", FileName(Path) .. ": Invalid .LH2 header.")
    local Entries, Tables = ReadUInt32(Data, 0x10), ReadUInt32(Data, 0x14)
    local Result = {}
    if Entries == 0 or Tables == 0 then
        return Result
    end
    local PointersOffset = 0x20 + Entries * 4
    assert(PointersOffset + Entries * 4 <= #Data, FileName(Path) .. ": Truncated .LH2 ID/pointer table.")
    for Index = 0, Entries - 1 do
        local StringId = ReadUInt32(Data, 0x20 + Index * 4)
        local StringOffset = ReadUInt32(Data, PointersOffset + Index * 4)
        Result[StringId] = ReadCStringCp1252(Data, StringOffset)
    end
    return Result
end

---@param Paths string[] Sorted localization paths.
---@return ToxLocalization
local function BuildLocalizationDatabase(Paths)
    ---@type ToxLocalization
    local Database = { LanguageTables = {}, LabelTable = {} }
    for _, Language in ipairs(Languages) do
        Database.LanguageTables[Language] = {}
    end
    for _, Path in ipairs(Paths) do
        local Name = FileName(Path):lower()
        if Name:find("simpsons_global", 1, true) then
            if Name:find(".ss.lh2", 1, true) and next(Database.LabelTable) == nil then
                Database.LabelTable = ParseLh2FirstTable(Path)
            else
                for _, Language in ipairs(Languages) do
                    if Name:find("." .. Language .. ".lh2", 1, true)
                        and next(Database.LanguageTables[Language]) == nil then
                        Database.LanguageTables[Language] = ParseLh2FirstTable(Path)
                    end
                end
            end
        end
    end
    -- Verified lowercase SDBM("bart_igc_000602e") = 0xE6A49A45. This cutoff
    -- scream is missing from the shipped localization table (gam_igc04, #26).
    if Database.LabelTable[0xE6A49A45] == nil then
        Database.LabelTable[0xE6A49A45] = "bart_igc_000602e"
    end
    return Database
end

---@param Path string
---@param Database ToxLocalization
---@return ToxFile
local function ParseToxFile(Path, Database)
    local Data = ReadBinary(Path)
    local Name = FileName(Path)
    assert(#Data >= 16, Name .. ": File too small (16 bytes header minimum).")
    assert(Data:sub(1, 4) == "1BOT", Name .. ": Invalid magic, expected 1BOT.")
    assert(ReadUInt32(Data, 4) == #Data, Name .. ": Header size mismatch.")
    local RecordCount = ReadUInt32(Data, 12)
    assert(#Data == 16 + RecordCount * 16, Name .. ": Record count size mismatch.")
    local FileStem = TimingStem(Path)
    ---@type ToxFile
    local Tox = {
        FilePath = Path, FileStem = FileStem, CleanStem = StripHashSuffix(FileStem),
        RecordCount = RecordCount, Records = {},
    }
    for Index = 0, RecordCount - 1 do
        local Offset = 16 + Index * 16
        local StringId = ReadUInt32(Data, Offset)
        local StartMs, DurationMs = ReadUInt32(Data, Offset + 4), ReadUInt32(Data, Offset + 8)
        local Label = Database.LabelTable[StringId] or ""
        ---@type ToxRecord
        local Record = {
            Index = Index + 1, StringId = StringId, StartMs = StartMs,
            DurationMs = DurationMs, EndMs = StartMs + DurationMs,
            Flags = ReadUInt32(Data, Offset + 12), Label = Label,
            Speaker = (Label:match("^(.-)_") or ""):upper(), Translations = {},
        }
        for _, Language in ipairs(Languages) do
            local Table = Database.LanguageTables[Language]
            local Text = Table[StringId] or ""
            if Text == "" and StringId == 0xE6A49A45 then
                local Previous = Table[0xE6A49A44]
                if Previous == nil or Previous == "0" then
                    Text = "(SCREAMING)"
                else
                    Text = Previous
                end
            end
            Record.Translations[Language] = Text
        end
        Tox.Records[#Tox.Records + 1] = Record
    end
    return Tox
end

--- Python str.strip whitespace representable by this converter's CP1252 input.
---@param Code integer
---@return boolean
local function IsWhitespace(Code)
    return (Code >= 9 and Code <= 13) or (Code >= 28 and Code <= 32) or Code == 0x85 or Code == 0xA0
end

---@param Text string
---@return string
local function StripWhitespace(Text)
    local First, Last = 1, #Text
    while First <= Last and IsWhitespace(string.unicode(Text, First)) do
        First = First + 1
    end
    while Last >= First and IsWhitespace(string.unicode(Text, Last)) do
        Last = Last - 1
    end
    return Text:sub(First, Last)
end

--- Avoid signed integer conversions when formatting unsigned 32-bit IDs/flags.
---@param Value integer
---@return string
local function Hex32(Value)
    local Digits, Result = "0123456789ABCDEF", {}
    for Index = 8, 1, -1 do
        local Digit = Value % 16
        Result[Index] = Digits:sub(Digit + 1, Digit + 1)
        Value = math.floor(Value / 16)
    end
    return table.concat(Result)
end

---@param Milliseconds integer
---@param Separator string Comma for SRT, period for VTT.
---@return string
local function FormatTimestamp(Milliseconds, Separator)
    local Hours = math.floor(Milliseconds / 3600000)
    local Minutes = math.floor(Milliseconds / 60000) % 60
    local Seconds = math.floor(Milliseconds / 1000) % 60
    return string.format("%02d:%02d:%02d%s%03d", Hours, Minutes, Seconds, Separator, Milliseconds % 1000)
end

--- Preserve cue ordering, empty-translation skipping and exact trailing newlines.
---@param Tox ToxFile
---@param Language string
---@param IncludeSpeaker boolean
---@param WebVtt boolean
---@return string
local function FormatSubtitles(Tox, Language, IncludeSpeaker, WebVtt)
    local Blocks = {}
    if WebVtt then
        Blocks = { "WEBVTT", "NOTE Movie: " .. Tox.CleanStem .. " | Language: " .. Language:upper(), "" }
    end
    local CueNumber = 1
    for _, Record in ipairs(Tox.Records) do
        local Text = StripWhitespace(Record.Translations[Language] or "")
        if Text ~= "" then
            if IncludeSpeaker and Record.Speaker ~= "" then
                if WebVtt then
                    Text = "<v " .. Record.Speaker .. ">" .. Text
                else
                    Text = "[" .. Record.Speaker .. "] " .. Text
                end
            end
            local Separator = WebVtt and "." or ","
            local CueId = string.format("%d", CueNumber)
            if WebVtt then
                CueId = Record.Label ~= "" and Record.Label or Hex32(Record.StringId)
            end
            Blocks[#Blocks + 1] = CueId .. "\n" .. FormatTimestamp(Record.StartMs, Separator)
                .. " --> " .. FormatTimestamp(Record.EndMs, Separator) .. "\n" .. Text .. "\n"
            CueNumber = CueNumber + 1
        end
    end
    return table.concat(Blocks, "\n")
end

---@param Value string|integer
---@return string
local function CsvField(Value)
    local Text = type(Value) == "number" and string.format("%.0f", Value) or tostring(Value)
    -- MoonSharp patterns compare some characters by their low byte, so a
    -- quote pattern also matches U+2022/U+2122. Compare full codepoints here.
    local NeedsQuotes, Start = false, 1
    local Parts = {}
    for Index = 1, #Text do
        local Code = string.unicode(Text, Index)
        if Code == 34 then
            Parts[#Parts + 1] = Text:sub(Start, Index) .. '"'
            Start = Index + 1
            NeedsQuotes = true
        elseif Code == 44 or Code == 13 or Code == 10 then
            NeedsQuotes = true
        end
    end
    if NeedsQuotes then
        Parts[#Parts + 1] = Text:sub(Start)
        return '"' .. table.concat(Parts) .. '"'
    end
    return Text
end

--- csv.writer uses CRLF records even though subtitle text files use LF.
---@param Tox ToxFile
---@return string
local function FormatMultilingualCsv(Tox)
    local Lines = { "Index,String ID,String Label,Speaker,Start (ms),Duration (ms),End (ms),Start (SRT),End (SRT),Flags,EN,ES,FR,IT" }
    for _, Record in ipairs(Tox.Records) do
        local Fields = {
            Record.Index, Hex32(Record.StringId), Record.Label, Record.Speaker,
            Record.StartMs, Record.DurationMs, Record.EndMs,
            FormatTimestamp(Record.StartMs, ","), FormatTimestamp(Record.EndMs, ","),
            "0x" .. Hex32(Record.Flags),
        }
        for _, Language in ipairs(Languages) do
            Fields[#Fields + 1] = Record.Translations[Language] or ""
        end
        for Index, Value in ipairs(Fields) do
            Fields[Index] = CsvField(Value)
        end
        Lines[#Lines + 1] = table.concat(Fields, ",")
    end
    return table.concat(Lines, "\r\n") .. "\r\n"
end

---@param Paths string[] Sorted localized video paths.
---@return table<string, string[]>
local function IndexVideos(Paths)
    local Index = {}
    for _, Path in ipairs(Paths) do
        local Language = FileName(ParentDirectory(Path)):lower()
        local Stem = FileName(Path):gsub("%.[^.]*$", "")
        local Key = Language .. ":" .. StripHashSuffix(Stem):lower()
        Index[Key] = Index[Key] or {}
        Index[Key][#Index[Key] + 1] = Path
    end
    return Index
end

---@param Path string
---@param Content string
---@return nil
local function WriteText(Path, Content)
    assert(sdk.write_file(Path, Content), "Could not write output: " .. Path)
end

---@param Options ToxOptions
---@return integer ConvertedCount
local function ConvertAllTox(Options)
    assert(sdk.path_exists(Options.InputDir), "Input directory does not exist: " .. Options.InputDir)
    ---@type ToxDiscovery
    local Files = { TimingPaths = {}, LocalizationPaths = {}, VideoPaths = {} }
    print("Scanning timing tables and localization under: " .. Options.InputDir)
    FindFiles(Options.InputDir, Options.InputDir, Files, Options.PairVideos)
    SortPaths(Files.TimingPaths)
    if #Files.TimingPaths == 0 then
        print("[WARN] No .tox.PS3 files found under: " .. Options.InputDir)
        return 0
    end
    SortPaths(Files.LocalizationPaths)
    SortPaths(Files.VideoPaths)
    print(string.format("Loading localization from %d LH2 file(s)...", #Files.LocalizationPaths))
    local Database = BuildLocalizationDatabase(Files.LocalizationPaths)
    local LabelCount = 0
    for _ in pairs(Database.LabelTable) do
        LabelCount = LabelCount + 1
    end
    print(string.format("Found %d .tox.PS3 file(s) and loaded %d localization IDs across %d languages (%s).\n",
        #Files.TimingPaths, LabelCount, #Languages, table.concat(Languages, ", ")))
    local VideoIndex = IndexVideos(Files.VideoPaths)
    ---@type table<string, boolean>
    local WrittenVideoSubtitles = {}
    local PairedVideos = 0
    for _, Path in ipairs(Files.TimingPaths) do
        local Tox = ParseToxFile(Path, Database)
        local TargetDir = Options.OutputDir or ParentDirectory(Path)
        assert(sdk.ensure_dir(TargetDir), "Could not create output directory: " .. TargetDir)
        WriteText(join(TargetDir, FileName(Path) .. ".csv"), FormatMultilingualCsv(Tox))
        if Tox.RecordCount > 0 then
            for _, Language in ipairs(Languages) do
                local Srt = FormatSubtitles(Tox, Language, Options.IncludeSpeaker, false)
                local Vtt = FormatSubtitles(Tox, Language, Options.IncludeSpeaker, true)
                WriteText(join(TargetDir, Tox.FileStem .. "." .. Language .. ".srt"), Srt)
                WriteText(join(TargetDir, Tox.FileStem .. "." .. Language .. ".vtt"), Vtt)
                if Options.PairVideos and not Options.OutputDir then
                    local Videos = VideoIndex[Language .. ":" .. Tox.CleanStem:lower()] or {}
                    for _, VideoPath in ipairs(Videos) do
                        local VideoStem = VideoPath:gsub("%.[^.]*$", "")
                        local SrtPath = VideoStem .. ".srt"
                        local Key = PathKey(SrtPath)
                        if not WrittenVideoSubtitles[Key] then
                            WriteText(SrtPath, Srt)
                            WriteText(VideoStem .. ".vtt", Vtt)
                            WrittenVideoSubtitles[Key] = true
                            PairedVideos = PairedVideos + 1
                        end
                    end
                end
            end
        end
        print(string.format("[OK] %-82s | records=%2d | movie='%s'",
            RelativeDisplay(Path, Options.InputDir), Tox.RecordCount, Tox.CleanStem))
    end
    print(string.format("\nSuccessfully converted %d/%d .tox.PS3 files (and paired %d localized video streams in A1_Video with .srt/.vtt).",
        #Files.TimingPaths, #Files.TimingPaths, PairedVideos))
    return #Files.TimingPaths
end

---@param Arguments string[]
---@return ToxOptions
local function ParseArguments(Arguments)
    ---@type ToxOptions
    local Options = {
        InputDir = join(Game_Root, "GameFiles", "PS3-EU-FullFlattened-audio_reorg-isRenamed"),
        PairVideos = true, IncludeSpeaker = false, Help = false,
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
        elseif Option == "--no-video-pairing" and not InlineValue then
            Options.PairVideos = false
        elseif Option == "--include-speaker" and not InlineValue then
            Options.IncludeSpeaker = true
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

---@return nil
local function Main()
    local Options = ParseArguments(argv or {})
    if Options.Help then
        print("Convert The Simpsons Game (PS3) .tox.PS3 timing tables to .srt, .vtt and .csv.\n"
            .. "Options: --input-dir/-i DIR, --output-dir/-o DIR, --no-video-pairing, --include-speaker, --help/-h\n"
            .. "Default input: " .. Options.InputDir .. "\nDefault output: beside each .tox.PS3 file, with localized video companions.")
        return
    end
    ConvertAllTox(Options)
end

local Success, Message = pcall(Main)
if not Success then
    print("[ERROR] " .. tostring(Message))
    os.exit(1)
end
