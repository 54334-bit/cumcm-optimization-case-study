param(
    [Parameter(Mandatory = $true)][string]$SessionRoot,
    [Parameter(Mandatory = $true)][string]$OutputJson
)

$ErrorActionPreference = 'Stop'

function Normalize-LoggedText([string]$Text) {
    if ($null -eq $Text) { return '' }
    return $Text.Replace('\\', '\')
}

function Get-CumcmPaths([string]$Text) {
    $normalized = Normalize-LoggedText $Text
    $rootPattern = '[A-Za-z]:[^"''`\r\n|;]*?' + [regex]::Escape('\cumcm\')
    $pattern = '(?i)(?:' + $rootPattern + ')?(?<relative>[^"''`\r\n|;]+?\.(?:md|txt|tex|py|ps1|json|jsonl|csv|ya?ml|toml|xlsx|xls|pdf|png|jpe?g|svg|docx))'
    $seen = @{}
    foreach ($match in [regex]::Matches($normalized, $pattern)) {
        $relative = $match.Groups['relative'].Value.Trim().TrimStart('\')
        if ($relative -and -not $seen.ContainsKey($relative)) {
            $seen[$relative] = $true
            $relative
        }
    }
}

function Get-HereStringWrite([string]$Text) {
    $normalized = Normalize-LoggedText $Text
    $contentMatch = [regex]::Match($normalized, '(?s)\$(?:text|content)\s*=\s*@''\r?\n(?<content>.*?)\r?\n''@')
    if (-not $contentMatch.Success) { return $null }

    $pathMatch = [regex]::Match($normalized, '(?i)\$p\s*=\s*''(?<path>[^'']+\.(?:md|txt|tex|py|ps1|json|jsonl|csv|ya?ml|toml))''')
    if (-not $pathMatch.Success) {
        $pathMatch = [regex]::Match($normalized, '(?i)WriteAllText\(\s*''(?<path>[^'']+\.(?:md|txt|tex|py|ps1|json|jsonl|csv|ya?ml|toml))''')
    }
    if (-not $pathMatch.Success) { return $null }

    [pscustomobject]@{
        path = $pathMatch.Groups['path'].Value.TrimStart('.\')
        content = $contentMatch.Groups['content'].Value
    }
}

function Read-SharedLines([string]$Path) {
    $stream = [IO.FileStream]::new($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    $reader = [IO.StreamReader]::new($stream, [Text.UTF8Encoding]::new($false), $true)
    try {
        while (-not $reader.EndOfStream) { $reader.ReadLine() }
    } finally {
        $reader.Dispose()
        $stream.Dispose()
    }
}

$events = [System.Collections.Generic.List[object]]::new()
$matchedPaths = @(& rg -l -F 'ChatGPT\\cumcm' $SessionRoot)
$sessionFiles = @($matchedPaths | Where-Object { $_ -like '*.jsonl' } | ForEach-Object { Get-Item -LiteralPath $_ } | Sort-Object FullName)
foreach ($session in $sessionFiles) {
    $lineNumber = 0
    foreach ($line in Read-SharedLines $session.FullName) {
        $lineNumber++
        try { $record = $line | ConvertFrom-Json -Depth 100 } catch { continue }
        $payload = $record.payload
        if ($null -eq $payload) { continue }
        $isCanonicalExec = $record.type -eq 'response_item' -and $payload.type -eq 'custom_tool_call' -and $payload.name -eq 'exec'

        $texts = [System.Collections.Generic.List[string]]::new()
        if ($payload.PSObject.Properties.Name -contains 'input' -and $payload.input -is [string]) { $texts.Add($payload.input) }
        if ($payload.PSObject.Properties.Name -contains 'output' -and $payload.output -is [string]) { $texts.Add($payload.output) }
        if ($payload.PSObject.Properties.Name -contains 'message' -and $payload.message -is [string]) { $texts.Add($payload.message) }
        if ($payload.PSObject.Properties.Name -contains 'item') {
            if ($payload.item.PSObject.Properties.Name -contains 'command') {
                $texts.Add(($payload.item.command -join "`n"))
            }
            if ($payload.item.PSObject.Properties.Name -contains 'arguments') {
                $texts.Add(($payload.item.arguments | ConvertTo-Json -Depth 20 -Compress))
            }
            if ($payload.item.PSObject.Properties.Name -contains 'content') {
                foreach ($contentPart in $payload.item.content) {
                    if ($contentPart.PSObject.Properties.Name -contains 'text') { $texts.Add([string]$contentPart.text) }
                }
            }
        }

        foreach ($text in $texts) {
            $paths = @(Get-CumcmPaths $text)
            if ($paths.Count -eq 0) { continue }
            $write = if ($isCanonicalExec) { Get-HereStringWrite $text } else { $null }
            $events.Add([pscustomobject]@{
                timestamp = $record.timestamp
                session = $session.FullName
                line = $lineNumber
                ordinal = $record.ordinal
                record_type = $record.type
                paths = $paths
                full_write_path = if ($write) { $write.path } else { $null }
                full_write_content = if ($write) { $write.content } else { $null }
                has_apply_patch = $text.Contains('*** Begin Patch')
                has_read_all_text = $text.Contains('ReadAllText') -or $text.Contains('Get-Content -Raw')
                is_canonical_exec = $isCanonicalExec
            })
        }
    }
}

$parent = Split-Path -Parent $OutputJson
if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
$events | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $OutputJson -Encoding utf8NoBOM
Write-Output "SESSION_FILES=$($sessionFiles.Count)"
Write-Output "EVIDENCE_EVENTS=$($events.Count)"
Write-Output "FULL_WRITES=$(($events | Where-Object full_write_content).Count)"
