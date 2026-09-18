$ErrorActionPreference = 'Stop'
$repo = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$scratch = Join-Path $repo '_recovery_test_tmp'
if (Test-Path -LiteralPath $scratch) { Remove-Item -LiteralPath $scratch -Recurse -Force }
New-Item -ItemType Directory -Path (Join-Path $scratch 'sessions') -Force | Out-Null

$danger = Join-Path $scratch 'must-not-exist.txt'
$logged = "`$p='Q4\sample.md'; `$text=@'`n# recovered`n'@; Set-Content -LiteralPath '$danger' -Value bad; [IO.File]::WriteAllText(`$p,`$text)"
$record = [ordered]@{
    timestamp = '2026-09-18T00:00:00Z'
    ordinal = 1
    type = 'response_item'
    payload = [ordered]@{ type = 'custom_tool_call'; name = 'exec'; input = $logged; message = 'X:\workspace\cumcm\Q4\sample.md' }
}
$sessionPath = Join-Path $scratch 'sessions\sample.jsonl'
$record | ConvertTo-Json -Depth 10 -Compress | Set-Content -LiteralPath $sessionPath -Encoding utf8NoBOM

$evidence = Join-Path $scratch 'evidence.json'
$heldOpen = [IO.FileStream]::new($sessionPath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
try {
    & (Join-Path $repo 'scripts\recovery\Export-CodexSessionEvidence.ps1') -SessionRoot (Join-Path $scratch 'sessions') -OutputJson $evidence | Out-Null
} finally {
    $heldOpen.Dispose()
}
if (Test-Path -LiteralPath $danger) { throw '日志中的命令被错误执行' }
$parsed = Get-Content -Raw -LiteralPath $evidence | ConvertFrom-Json
if (-not ($parsed | Where-Object { $_.full_write_path -eq 'Q4\sample.md' })) { throw '未提取完整写入事件' }

$restored = Join-Path $scratch 'restored'
& (Join-Path $repo 'scripts\recovery\Restore-CodexTextArtifacts.ps1') -EvidenceJson $evidence -StagingRoot $restored | Out-Null
$target = Join-Path $restored 'Q4\sample.md'
if (-not (Test-Path -LiteralPath $target)) { throw '未恢复候选文件' }
if ((Get-Content -Raw -LiteralPath $target).Trim() -ne '# recovered') { throw '恢复内容不一致' }
if (Test-Path -LiteralPath $danger) { throw '恢复阶段执行了日志命令' }

Remove-Item -LiteralPath $scratch -Recurse -Force
Write-Output 'RECOVERY_SCRIPT_TESTS=PASS'
