$wsh = New-Object -ComObject WScript.Shell
$desktop = [System.Environment]::GetFolderPath('Desktop')
$appDir = $PSScriptRoot
$targetBat = Join-Path $appDir "run_app.bat"
$iconPath = Join-Path $appDir "static\assets\app_icon.ico"

$shortcuts = @(
    @{ Name = "Kalshi AiTrader.lnk"; Desc = "Kalshi AiTrader & BTC 15M Confluence Engine" },
    @{ Name = "BTC 15M Kalshi AI Trader.lnk"; Desc = "BTC 15M Kalshi AI Trader & Confluence Pattern Engine" },
    @{ Name = "Bitcoin 15M Pattern Analyzer.lnk"; Desc = "Bitcoin 15-Minute Pattern Analyzer & Direction Predictor" }
)

foreach ($item in $shortcuts) {
    $scPath = Join-Path $desktop $item.Name
    $sc = $wsh.CreateShortcut($scPath)
    $sc.TargetPath = $targetBat
    $sc.WorkingDirectory = $appDir
    if (Test-Path $iconPath) {
        $sc.IconLocation = "$iconPath,0"
    }
    $sc.Description = $item.Desc
    $sc.Save()
    Write-Host "Updated shortcut: $scPath"
}

