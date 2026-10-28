param([switch]$NoClaude, [switch]$NoClaudeApi)
$ErrorActionPreference = 'Stop'
$source = Split-Path -Parent $MyInvocation.MyCommand.Path
$plugin = Join-Path $env:APPDATA 'Elgato\StreamDeck\Plugins\com.local.aiusage.sdPlugin'
$data = Join-Path $env:LOCALAPPDATA 'AIUsageStreamDeck'
$python = (Get-Command python.exe -ErrorAction Stop).Source
$codex = (Get-Command codex.exe -ErrorAction SilentlyContinue).Source
$claudeSettings = Join-Path $env:USERPROFILE '.claude\settings.json'

New-Item -ItemType Directory -Force $plugin,$data | Out-Null
Copy-Item (Join-Path $source 'collector.py') (Join-Path $plugin 'collector.py') -Force
Copy-Item (Join-Path $source 'com.local.aiusage.sdPlugin\*') $plugin -Recurse -Force
@{python=$python;codex=$codex;claudeApi=(-not $NoClaudeApi)} | ConvertTo-Json | Set-Content (Join-Path $plugin 'config.json') -Encoding utf8

if (-not $NoClaude -and (Test-Path $claudeSettings)) {
    & $python (Join-Path $source 'configure_claude.py')
    if ($LASTEXITCODE -ne 0) { throw 'Claude statusline configuration failed' }
}
Write-Host '설치 완료. Stream Deck을 다시 시작한 뒤 AI Usage의 Codex/Claude 버튼을 추가하세요.'
