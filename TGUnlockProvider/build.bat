call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
"C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\devenv.com" SampleV2CredentialProvider.sln /upgrade
msbuild SampleV2CredentialProvider.sln /p:Configuration=Release /p:Platform=x64
