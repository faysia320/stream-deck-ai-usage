$ErrorActionPreference = 'Stop'
$plugin = Join-Path $env:APPDATA 'Elgato\StreamDeck\Plugins\com.local.aiusage.sdPlugin'
$settingsPath = Join-Path $env:USERPROFILE '.claude\settings.json'
$previousPath = Join-Path $env:LOCALAPPDATA 'AIUsageStreamDeck\previous-statusline.json'
if ((Test-Path $settingsPath) -and (Test-Path $previousPath)) {
    $settings = Get-Content $settingsPath -Raw | ConvertFrom-Json
    if ($settings.statusLine.command -like '*com.local.aiusage.sdPlugin*statusline_wrapper.py*') {
        $previous = Get-Content $previousPath -Raw | ConvertFrom-Json
        $backup = "$settingsPath.aiusage-uninstall-backup-$(Get-Date -Format yyyyMMdd-HHmmss)"
        Copy-Item $settingsPath $backup
        if ($previous.command) {
            $settings.statusLine.command = $previous.command
        } else {
            $settings.PSObject.Properties.Remove('statusLine')
        }
        $settings | ConvertTo-Json -Depth 100 | Set-Content $settingsPath -Encoding utf8
    }
}
if (Test-Path $plugin) { Remove-Item -LiteralPath $plugin -Recurse -Force }
Write-Host '제거 완료. Stream Deck을 다시 시작하세요.'
