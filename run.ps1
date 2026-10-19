<#
A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\run.ps1

// this tool is used to launch the Remake Engine from the current module's directory
// allowing a module dev to run the module without needing to navigate to the Remake Engine's root directory


Release Tree
+---win-x64-Debug
|   |   EngineNet.exe
|   |
|   +---EngineApps
|       +---Games
|       |   \---<Current Module>
|       |
|      \---Registries
|          +---Modules
|          +---ops
|          \---Tools
|
\---win-x64-Release
    |   EngineNet.exe
    |
    \---EngineApps
        +---Games
        |   \---<Current Module>
        |
        \---Registries
            +---Modules
            +---ops
            \---Tools

Source Tree

├── EngineApps
│   ├── .gitignore
│   ├── Games
│   │   ├── .gitignore
│   │   ├── SimpsonsHitAndRun
│   │   ├── TheSimpsonsGame-PS3
│   │   ├── TheSimpsonsRoadRage-PS2
│   │   └── demo
│   ├── Registries
│   │   ├── Modules
│   │   ├── Tools
│   │   └── ops
│   ├── api_definitions
│   │   ├── api_definitions.d.ts
│   │   ├── api_definitions.pyi
│   │   ├── moonsharp
│   │   └── remake-engine
│   └── jsconfig.json
├── EngineNet
│   ├── .gitignore
│   ├── EngineNet.csproj
│   ├── EngineNet.csproj.user
│   ├── Init.cs
│   ├── Program.cs
│   ├── Properties
│   │   └── launchSettings.json
│   ├── icon.ico
│   ├── readme.md
│   └── source
│       ├── Core
│       ├── GameFormats
│       ├── Interface
│       ├── ScriptEngines
│       └── Shared
├── LICENSE
├── Readme.md
├── RemakeEngine.slnx



Push-Location ..\..\..\

# locate one of two ways to launch the remakeengine
# the exe at this level EngineNet.exe or the source code in the EngineNet/ folder, dotnet run -c Debug --project .\EngineNet\
if (Test-Path ".\EngineNet.exe") {
    .\EngineNet.exe
} elseif (Test-Path ".\EngineNet\") {
    dotnet run -c Debug --project .\EngineNet\
} else {
    Write-Host "Remake Engine not found."
}

# after exit, return to the original location
Pop-Location

#>


[CmdletBinding()]
param (
    [string]$Configuration = "Debug",
    [switch]$Release
)

if ($Release) { $Configuration = "Release" }

# 1. Resolve module directory and module name
$moduleDir = $PSScriptRoot
$moduleName = Split-Path -Path $moduleDir -Leaf

# 2. Check expected parent directory hierarchy
$gamesDir      = Split-Path -Path $moduleDir -Parent
$engineAppsDir = Split-Path -Path $gamesDir -Parent
$engineRootDir = Split-Path -Path $engineAppsDir -Parent

$gamesDirName      = Split-Path -Path $gamesDir -Leaf
$engineAppsDirName = Split-Path -Path $engineAppsDir -Leaf

$isPathStructureValid = ($gamesDirName -eq "Games") -and ($engineAppsDirName -eq "EngineApps")

# Check if parent structure is invalid or root doesn't exist
if (-not $isPathStructureValid -or -not (Test-Path -LiteralPath $engineRootDir)) {
    Write-Host "[ERROR] Orphan Module Detected!" -ForegroundColor Red
    Write-Host "This module ('$moduleName') appears to have been cloned or extracted outside of the Remake Engine directory structure." -ForegroundColor Yellow
    Write-Host "Expected location: <RemakeEngineRoot>\EngineApps\Games\$moduleName" -ForegroundColor DarkGray
    Write-Host "Current location:  $moduleDir" -ForegroundColor DarkGray
    exit 1
}

# 3. Detect Environment (Source vs Published/Release)
$engineProjDir = Join-Path -Path $engineRootDir -ChildPath "EngineNet"
$engineExe     = Join-Path -Path $engineRootDir -ChildPath "EngineNet.exe"

Push-Location -LiteralPath $engineRootDir
try {
    # CASE A: Source Tree (Detected by EngineNet/ directory)
    if (Test-Path -LiteralPath $engineProjDir -PathType Container) {
        Write-Host "[$moduleName] Environment: Source Tree detected at '$engineRootDir'." -ForegroundColor Cyan
        Write-Host "[$moduleName] Launching via dotnet run (-c $Configuration)..." -ForegroundColor Green

        dotnet run -c $Configuration --project "$engineProjDir"
    }
    # CASE B: Published / Release Tree (Detected by EngineNet.exe in root)
    elseif (Test-Path -LiteralPath $engineExe -PathType Leaf) {
        Write-Host "[$moduleName] Environment: Published/Binary package detected at '$engineRootDir'." -ForegroundColor Cyan
        Write-Host "[$moduleName] Launching EngineNet.exe..." -ForegroundColor Green

        & "$engineExe"
    }
    # CASE C: Cloned inside a folder called EngineApps/Games, but the engine core is missing
    else {
        Write-Host "[ERROR] Remake Engine core missing!" -ForegroundColor Red
        Write-Host "Located parent structure '<Root>\EngineApps\Games', but neither the source ('EngineNet\') nor the binary ('EngineNet.exe') was found at:" -ForegroundColor Yellow
        Write-Host "  $engineRootDir" -ForegroundColor DarkGray
        Write-Host "`nMake sure your Remake Engine repository is built or properly cloned." -ForegroundColor Yellow
        exit 1
    }
}
finally {
    Pop-Location
}