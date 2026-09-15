Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)

PythonwExe = ScriptDir & "\.venv\Scripts\pythonw.exe"
If Not FSO.FileExists(PythonwExe) Then
    PythonwExe = "pythonw.exe"
End If

WatchdogScript = ScriptDir & "\server_watchdog.py"

WshShell.CurrentDirectory = ScriptDir
WshShell.Run """" & PythonwExe & """ """ & WatchdogScript & """", 0, False
