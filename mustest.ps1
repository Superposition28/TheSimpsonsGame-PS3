# Paths
$bmsPath = "A:\RemakeEngine\Main\EngineApps\Tools\QuickBMS-0.12.0-win-x64\quickbms_4gb_files.exe"
$scriptPath = "A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\operations\mus.bms"
$vgmstreamPath = "A:\RemakeEngine\Main\EngineApps\Tools\vgmstream-cli-r2023-win-x64\vgmstream-cli.exe"
$sourceDir = "A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\EU-FullFlattened-audio_reorg-isRenamed\A1_Audio"

# Create the master Music folder
$musicFolder = Join-Path $sourceDir "Music"
if (!(Test-Path $musicFolder)) { New-Item -ItemType Directory -Path $musicFolder | Out-Null }

# Normalization Function
function Get-FriendlyFolderName($fileName) {
    # Strip extension and potential _mus suffix
    $cleanName = $fileName -replace "_mus\.mus", "" -replace "\.mus", ""

    # Map technical name to Human-Readable name with underscores
    switch ($cleanName) {
        "menu"     { return "A2_Menu" }

        "loc"      { return "L01_LandOfChocolate" }
        "brt"      { return "L02_BartmanBegins" }
        "80b"      { return "L03_HungryHungryHomer" }
        "treetemp" { return "L04_TreeHugger" }
        "mob"      { return "L05_MobRules" }
        "cheater"  { return "L06_EnterTheCheatrix" }
        "dod"      { return "L07_DayOfTheDolphin" }
        "scd"      { return "L08_TheColossalDonut" }
        "sss"      { return "L09_Invasion" }
        "bin"      { return "L10_BargainBin" }
        "nvq"      { return "L11_NeverQuest" }
        "gts"      { return "L12_GrandTheftScratchy" }
        "moh"      { return "L13_MedalOfHomer" }
        "bsh"      { return "L14_BigSuperHappy" }
        "rwc"      { return "L15_Rhymes" }
        "mtp"      { return "L16_MeetThyPlayer" }
        "hub"      { return "LHub-00_GameHub" }
        "spr"      { return "LHub-00_SprHub" }
        Default    { return $cleanName.Replace(" ", "_") }
    }
}

# Get all .mus files
$musFiles = Get-ChildItem -Path $sourceDir -Filter "*.mus"

foreach ($musFile in $musFiles) {
    # Get the underscore-formatted folder name
    $folderName = Get-FriendlyFolderName $musFile.Name
    $outputDir = Join-Path $musicFolder $folderName

    Write-Host "--- Processing: $($musFile.Name) -> $folderName ---" -ForegroundColor Cyan

    # 1. Create directory
    if (!(Test-Path $outputDir)) { New-Item -ItemType Directory -Path $outputDir | Out-Null }

    # Run QuickBMS
    & $bmsPath -o $scriptPath $musFile.FullName $outputDir

    # 2. Convert SNR/SNS to WAV
    Get-ChildItem -Path $outputDir -Filter "*.snr" | ForEach-Object {
        $wavOutput = ($_.FullName -replace '\.snr$', '.wav')
        & $vgmstreamPath -o $wavOutput $_.FullName
    }

    # 3. Clean up intermediate files
    Remove-Item -Path "$outputDir\*.snr" -ErrorAction SilentlyContinue
    Remove-Item -Path "$outputDir\*.sns" -ErrorAction SilentlyContinue

    Write-Host "Finished: $folderName" -ForegroundColor Green
}