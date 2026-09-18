param(
    [Parameter(Mandatory = $true)][string]$EvidenceJson,
    [Parameter(Mandatory = $true)][string]$StagingRoot
)

$ErrorActionPreference = 'Stop'
$events = Get-Content -Raw -LiteralPath $EvidenceJson | ConvertFrom-Json -Depth 100
$writes = $events | Where-Object { $_.full_write_path -and $null -ne $_.full_write_content } |
    Sort-Object timestamp, session, line |
    Group-Object full_write_path

$manifest = [System.Collections.Generic.List[object]]::new()
foreach ($group in $writes) {
    $event = $group.Group[-1]
    $relative = $event.full_write_path.Replace('/', '\').TrimStart('\')
    if ([IO.Path]::IsPathRooted($relative)) {
        $marker = '\cumcm\'
        $index = $relative.IndexOf($marker, [StringComparison]::OrdinalIgnoreCase)
        if ($index -lt 0) { continue }
        $relative = $relative.Substring($index + $marker.Length)
    }
    if ($relative.Contains('..')) { continue }
    $target = Join-Path $StagingRoot $relative
    $resolvedRoot = [IO.Path]::GetFullPath($StagingRoot).TrimEnd('\') + '\'
    $resolvedTarget = [IO.Path]::GetFullPath($target)
    if (-not $resolvedTarget.StartsWith($resolvedRoot, [StringComparison]::OrdinalIgnoreCase)) { continue }
    New-Item -ItemType Directory -Path (Split-Path -Parent $resolvedTarget) -Force | Out-Null
    [IO.File]::WriteAllText($resolvedTarget, [string]$event.full_write_content, [Text.UTF8Encoding]::new($false))
    $file = Get-Item -LiteralPath $resolvedTarget
    $manifest.Add([pscustomobject]@{
        original_relative_path = $relative
        recovery_status = 'exact-full-write-candidate'
        staging_path = $resolvedTarget
        source_session = $event.session
        source_line = $event.line
        timestamp = $event.timestamp
        size = $file.Length
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedTarget).Hash
    })
}

$manifestPath = Join-Path $StagingRoot '_full_write_manifest.csv'
$manifest | Export-Csv -LiteralPath $manifestPath -NoTypeInformation -Encoding utf8NoBOM
Write-Output "RESTORED_FULL_WRITE_CANDIDATES=$($manifest.Count)"
Write-Output "MANIFEST=$manifestPath"
