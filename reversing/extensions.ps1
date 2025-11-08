# Set the root directory
$root = "A:\Dev\Games\TheSimpsonsGame\PAL\Modules\Extract\GameFiles\quickbms_out"

# Define the subdirectories
$subDirs = @(
	".",
    "Assets_2_Characters_Simpsons",
    "Assets_2_Frontend",
    "Map_3-00_GameHub",
    "Map_3-00_SprHub",
    "Map_3-01_LandOfChocolate",
    "Map_3-02_BartmanBegins",
    "Map_3-03_HungryHungryHomer",
    "Map_3-04_TreeHugger",
    "Map_3-05_MobRules",
    "Map_3-06_EnterTheCheatrix",
    "Map_3-07_DayOfTheDolphin",
    "Map_3-08_TheColossalDonut",
    "Map_3-09_Invasion",
    "Map_3-10_BargainBin",
    "Map_3-11_NeverQuest",
    "Map_3-12_GrandTheftScratchy",
    "Map_3-13_MedalOfHomer",
    "Map_3-14_BigSuperHappy",
    "Map_3-15_Rhymes",
    "Map_3-16_MeetThyPlayer"
)

# Construct the full paths
$pathsToSearch = $subDirs | ForEach-Object { Join-Path -Path $root -ChildPath $_ }

# Loop through each path to search
foreach ($pathToSearch in $pathsToSearch) {
    Write-Host "Processing directory: $pathToSearch" -ForegroundColor Yellow

    # Get all files recursively from the current path
    $allFiles = Get-ChildItem -Path $pathToSearch -Recurse -File -ErrorAction SilentlyContinue

    # Create hashtable to store extension chains and their counts for the current directory
    $extensionCounts = @{}

    # Go through each file in the current directory
    foreach ($file in $allFiles) {
        $nameParts = $file.Name -split '\.' # Use regex split to handle potential multiple dots correctly

        $extensionChain = "" # Initialize extensionChain

        # Check if the file has an extension
        if ($nameParts.Length -lt 2) {
            # File has no extension
            $extensionChain = "(no extension)"
        } else {
            # Get all extensions (everything after the first part)
            $extensions = $nameParts[1..($nameParts.Length - 1)]
            $extensionChain = ($extensions -join '.').ToLower()
        }

        # Count them
        if ($extensionCounts.ContainsKey($extensionChain)) {
            $extensionCounts[$extensionChain]++
        } else {
            $extensionCounts[$extensionChain] = 1
        }
    }

    # Sort and display the results for the current directory
    if ($extensionCounts.Count -gt 0) {
        $extensionCounts.GetEnumerator() |
            Sort-Object -Property Value -Descending |
            Format-Table Name, Value -AutoSize
    } else {
        Write-Host "No files with extensions found in $pathToSearch"
    }

    Write-Host "`n" # Add a newline for separation
}
