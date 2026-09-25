@echo off
rem Double-click this file to upload changed cheat files to GitHub and refresh
rem the release exe. No admin needed; window stays open so you can see results.
cd /d "%~dp0"
set "PATH=%LOCALAPPDATA%\Programs\MinGit\cmd;%LOCALAPPDATA%\Programs\gh\bin;%PATH%"
set "MSBUILD=C:\Program Files\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe"

echo [1/3] Uploading changed files to GitHub...
git add -A >nul 2>&1
git diff --cached --quiet >nul 2>&1
if %errorlevel% equ 0 (
    echo       Nothing changed - source already up to date.
) else (
    git commit -q -m "update %DATE% %TIME%"
    git push
    if errorlevel 1 echo       PUSH FAILED - check internet or GitHub sign-in.
    if not errorlevel 1 echo       Source uploaded.
)

tasklist /fi "imagename eq cs2-wallhack.exe" 2>nul | find /i "cs2-wallhack.exe" >nul
if %errorlevel% equ 0 (
    echo [2/3] Cheat is running - close it first, then run this again to refresh the release exe.
    goto :done
)

echo [2/3] Building Release x64...
"%MSBUILD%" cs2-wallhack.sln /p:Configuration=Release /p:Platform=x64 /v:minimal /nologo > build_out.txt 2>&1
if errorlevel 1 (
    echo       BUILD FAILED - see build_out.txt. Release exe not changed.
    goto :done
)
echo       Build OK.
echo [3/3] Updating the release exe...
gh release upload v1.0 "bin\Release\cs2-wallhack.exe" --clobber
if errorlevel 1 echo       Release upload FAILED.
if not errorlevel 1 echo       Release exe updated.

:done
echo.
pause
