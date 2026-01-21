#$dbPath="EngineApps\Games\TheSimpsonsGame-PS3\config\GameFilesIndex_EU_FullFlattened-audio_reorg-isRenamed.db";$dbName=[System.IO.Path]::GetFileNameWithoutExtension($dbPath);$outRoot="EngineApps\Games\TheSimpsonsGame-PS3\config\jsonexport";$outDir=Join-Path $outRoot $dbName;New-Item -ItemType Directory -Force -Path $outDir|Out-Null;$tables=(& sqlite3.exe $dbPath ".tables") -split '\s+'|Where-Object{ -not [string]::IsNullOrWhiteSpace($_)};foreach($t in $tables){$outfile=Join-Path $outDir "$t.json";& sqlite3.exe $dbPath ".mode json" ".headers on" ".once $outfile" "SELECT * FROM ""$t"";"};"Export complete to: $outDir"


# Path to your DB file
$dbPath = "EngineApps\Games\TheSimpsonsGame-PS3\config\GameFilesIndex_EU_FullFlattened-audio_reorg-isRenamed.db"

# Derive {dbfilename} (no extension)
$dbName = [System.IO.Path]::GetFileNameWithoutExtension($dbPath)

# Output directory: ...\{dbfilename}\
$outRoot = "EngineApps\Games\TheSimpsonsGame-PS3\config"
$outDir  = Join-Path $outRoot $dbName

# Ensure output directory exists
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

# Get table list (space-separated) and split into names
$tables = (& sqlite3.exe $dbPath ".tables") -split '\s+' |
          Where-Object { -not [string]::IsNullOrWhiteSpace($_) }

foreach ($t in $tables) {
    $outfile = Join-Path $outDir "$t.json"

    & sqlite3.exe $dbPath `
        ".mode json" `
        ".headers on" `
        ".once $outfile" `
        "SELECT * FROM ""$t"";"
}

"Export complete to: $outDir"

