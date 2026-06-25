@echo off
copy /y "%~dp0x64\Release\SampleV2CredentialProvider.dll" "C:\Windows\System32\"
regedit.exe /s "%~dp0Register.reg"
reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\PasswordLess\Device" /v DevicePasswordLessBuildVersion /t REG_DWORD /d 0 /f
echo Installation complete.
