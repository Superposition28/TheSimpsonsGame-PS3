
$ErrorActionPreference = "Stop"

$ProjectRoot = "A:\RemakeEngine\Main"
$ModuleRoot = Join-Path $ProjectRoot "EngineApps\Games\TheSimpsonsGame-PS3"
$ConfigPath = Join-Path $ModuleRoot "config.toml"

Set-Location $ProjectRoot

function Invoke-InitTest {
    param(
        [Parameter(Mandatory)] [string] $Platform,
        [Parameter(Mandatory)] [string] $Region,
        [Parameter(Mandatory)] [string] $SourcePath
    )

    Remove-Item $ConfigPath -Force -ErrorAction Stop
    $LuaArguments = @("--platform", $Platform, "--region", $Region, "--path", $SourcePath, "--action", "use") | ConvertTo-Json -Compress

    dotnet run -c Debug --project .\EngineNet\ -- `
        --game TheSimpsonsGame-PS3 `
        --run_op 0 `
        --args $LuaArguments

    # run all ops needed to generate all files normalised
    dotnet run -c Debug --project .\EngineNet\ -- --game TheSimpsonsGame-PS3 --run_op 1; dotnet run -c Debug --project .\EngineNet\ -- --game TheSimpsonsGame-PS3 --run_op 2; dotnet run -c Debug --project .\EngineNet\ -- --game TheSimpsonsGame-PS3 --run_op 4; dotnet run -c Debug --project .\EngineNet\ -- --game TheSimpsonsGame-PS3 --run_op 5; dotnet run -c Debug --project .\EngineNet\ -- --game TheSimpsonsGame-PS3 --run_op 6

}



Invoke-InitTest -Platform "xbox360" -Region "EU" -SourcePath "$ModuleRoot\Source\XBOX360\EU\1\TSG"
Invoke-InitTest -Platform "xbox360" -Region "US" -SourcePath "$ModuleRoot\Source\XBOX360\US\1\extractedFiles"



Invoke-InitTest -Platform "ps3" -Region "EU" -SourcePath "$ModuleRoot\Source\PS3\EU\1\PS3_GAME"
Invoke-InitTest -Platform "ps3" -Region "US" -SourcePath "$ModuleRoot\Source\PS3\US\1\PS3_GAME"

