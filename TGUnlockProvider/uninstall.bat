@echo off
regedit.exe /s "%~dp0Unregister.reg"
del /f /q "C:\Windows\System32\SampleV2CredentialProvider.dll"
echo Uninstallation complete.
