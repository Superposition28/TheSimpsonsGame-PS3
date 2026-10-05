
cd A:\RemakeEngine\Main\;

# if exists A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\config.toml delete
if (Test-Path "A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\config.toml") {
    Remove-Item "A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\config.toml"
};

dotnet run -c Debug --project .\EngineNet\ -- --game TheSimpsonsGame-PS3 --run_op 0;

# run all needed operations for this test
dotnet run -c Debug --project .\EngineNet\ -- --game TheSimpsonsGame-PS3 --run_op 1; dotnet run -c Debug --project .\EngineNet\ -- --game TheSimpsonsGame-PS3 --run_op 2; dotnet run -c Debug --project .\EngineNet\ -- --game TheSimpsonsGame-PS3 --run_op 4; dotnet run -c Debug --project .\EngineNet\ -- --game TheSimpsonsGame-PS3 --run_op 5; dotnet run -c Debug --project .\EngineNet\ -- --game TheSimpsonsGame-PS3 --run_op 6

# repeat process for each region and platform to get all files in the same structure to compare

