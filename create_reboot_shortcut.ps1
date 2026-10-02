# Creates/refreshes the "Reboot AI Trader" desktop shortcut so it always points at
# reboot_and_verify.bat in this folder, with the app's own icon. Safe to run any number
# of times - it just overwrites the same shortcut.
$appDir = $PSScriptRoot
$desktop = [Environment]::GetFolderPath('Desktop')
$target = Join-Path $appDir 'reboot_and_verify.bat'
$icon = Join-Path $appDir 'static\assets\app_icon.ico'
$lnkPath = Join-Path $desktop 'Reboot AI Trader.lnk'

$wsh = New-Object -ComObject WScript.Shell
$sc = $wsh.CreateShortcut($lnkPath)
$sc.TargetPath = $target
$sc.WorkingDirectory = $appDir
$sc.Description = 'Reboot the Kalshi AI Trader server, worker and ngrok tunnel, and verify moneyprinter.ngrok.app is live'
if (Test-Path $icon) {
    $sc.IconLocation = "$icon,0"
}
$sc.Save()
Write-Host "Shortcut ready: $lnkPath"
