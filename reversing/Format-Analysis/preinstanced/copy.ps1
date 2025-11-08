param (
    [Parameter(Mandatory = $true)]
    [string]$SourceDir,

    [Parameter(Mandatory = $true)]
    [string]$DestDir,

    [Parameter(Mandatory = $true)]
    [string[]]$FilePattern
)

# Collect all matching files for all patterns
$allFiles = @()
foreach ($pattern in $FilePattern) {
    $allFiles += Get-ChildItem -Path $SourceDir -Recurse -Filter $pattern
}

$total = $allFiles.Count
$index = 0

foreach ($file in $allFiles) {
    $index++

    # Calculate progress
    $percent = [math]::Round(($index / $total) * 100, 2)
    Write-Progress -Activity "Copying files..." -Status "$index of $total ($percent%)" -PercentComplete $percent

    # Build target path
    $relativePath = $file.FullName.Substring($SourceDir.Length).TrimStart('\')
    $target = Join-Path $DestDir $relativePath

    # Ensure target dir exists
    $targetDir = Split-Path $target
    if (-not (Test-Path $targetDir)) {
        New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    }

    # Copy file
    Copy-Item $file.FullName -Destination $target -Force
}

Write-Host "✅ Done! Copied $total files." -ForegroundColor Green
