param(
    [string] $AssetsSourcePath,
    [string] $MainSourcePath,
    [string] $PreBuiltPath
)

$ErrorActionPreference = 'Stop'
$gameRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

# Read the module's placeholders when source paths are not supplied explicitly.
function Get-PlaceholderValue {
    param(
        [string] $Name,
        [string] $ConfigContent
    )

    $pattern = '(?m)^\s*{0}\s*=\s*"([^"]*)"\s*(?:#.*)?$' -f [regex]::Escape($Name)
    $match = [regex]::Match($ConfigContent, $pattern)
    if (-not $match.Success) {
        throw "Could not find the '$Name' string in config.toml."
    }

    return $match.Groups[1].Value.Replace('\\', '\')
}

if (-not $AssetsSourcePath -or -not $MainSourcePath) {
    $configPath = Join-Path $gameRoot 'config.toml'
    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
        throw "Game config was not found: $configPath"
    }
    $configContent = Get-Content -LiteralPath $configPath -Raw

    if (-not $AssetsSourcePath) {
        $platform = Get-PlaceholderValue -Name 'Platform' -ConfigContent $configContent
        $region = Get-PlaceholderValue -Name 'Region' -ConfigContent $configContent
        $type = Get-PlaceholderValue -Name 'Type' -ConfigContent $configContent
        $audioState = Get-PlaceholderValue -Name 'audio_state' -ConfigContent $configContent
        $isRenamed = Get-PlaceholderValue -Name 'isRenamed' -ConfigContent $configContent
        $assetSetName = '{0}-{1}-{2}-{3}-{4}' -f $platform, $region, $type, $audioState, $isRenamed
        $AssetsSourcePath = Join-Path $gameRoot (Join-Path 'GameFiles' $assetSetName)
    }

    if (-not $MainSourcePath) {
        $MainSourcePath = Get-PlaceholderValue -Name 'MainSourcePath' -ConfigContent $configContent
    }
}

if (-not $PreBuiltPath) {
    $PreBuiltPath = Join-Path $gameRoot 'Godot\GodotGame\PreBuilt'
}

$AssetsSourcePath = [System.IO.Path]::GetFullPath($AssetsSourcePath)
$MainSourcePath = [System.IO.Path]::GetFullPath($MainSourcePath)
$PreBuiltPath = [System.IO.Path]::GetFullPath($PreBuiltPath)

if (-not (Test-Path -LiteralPath $AssetsSourcePath -PathType Container)) {
    throw "Flattened asset source directory was not found: $AssetsSourcePath"
}

$assetsDestination = Join-Path $PreBuiltPath 'assets'
$logosDestination = Join-Path $PreBuiltPath 'logos'
$null = New-Item -ItemType Directory -Path $assetsDestination, $logosDestination -Force

# Populate the main asset tree only once, preserving its folder structure and supported file types.
$assetExtensions = @('.png', '.glb', '.ogv', '.graph', '.fnt', '.json')
$existingAssets = @(Get-ChildItem -LiteralPath $assetsDestination -Force)
if ($existingAssets.Count -eq 0) {
    $assetFiles = @(Get-ChildItem -LiteralPath $AssetsSourcePath -File -Recurse |
        Where-Object { $_.Extension -in $assetExtensions })
    foreach ($assetFile in $assetFiles) {
        $relativePath = [System.IO.Path]::GetRelativePath($AssetsSourcePath, $assetFile.FullName)
        $destinationFile = Join-Path $assetsDestination $relativePath
        $destinationDirectory = Split-Path -Parent $destinationFile
        $null = New-Item -ItemType Directory -Path $destinationDirectory -Force
        Copy-Item -LiteralPath $assetFile.FullName -Destination $destinationFile -Force
    }
    Write-Host "Copied $($assetFiles.Count) supported asset file(s) into '$assetsDestination'."
} else {
    Write-Host "Leaving '$assetsDestination' unchanged because it is not empty."
}

# Scene refresh must use maps from the same dataset as these assets. Never replace
# an existing project's maps with maps from a potentially different platform/region.
$destinationMaps = @(Get-ChildItem -LiteralPath $assetsDestination -File |
    Where-Object { $_.Name -eq 'normalized_map.json' -or $_.Name -like 'map_*.json' })
if ($destinationMaps.Count -eq 0) {
    Write-Warning "No normalization maps found in '$assetsDestination'. refreshTSCNpaths.py requires normalized_map.json or map_*.json copied with the matching asset dataset."
}

# Add source icons only when missing; invalidate Godot's import cache for each new file.
$copiedLogos = 0
$iconSourceDirectory = Split-Path -Parent $MainSourcePath
if (Test-Path -LiteralPath $iconSourceDirectory -PathType Container) {
    $iconFiles = @(Get-ChildItem -LiteralPath $iconSourceDirectory -File |
        Where-Object { $_.Extension -in @('.png', '.dat') })
    foreach ($iconFile in $iconFiles) {
        $destinationFile = Join-Path $logosDestination $iconFile.Name
        if (-not (Test-Path -LiteralPath $destinationFile)) {
            Copy-Item -LiteralPath $iconFile.FullName -Destination $destinationFile
            Remove-Item -LiteralPath "$destinationFile.import" -Force -ErrorAction SilentlyContinue
            $copiedLogos++
        }
    }
}
Write-Host "Copied $copiedLogos missing logo file(s)."
