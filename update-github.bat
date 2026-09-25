@echo off
rem Double-click this file to upload any changed cheat files to GitHub.
cd /d "%~dp0"
set "PATH=%LOCALAPPDATA%\Programs\MinGit\cmd;%LOCALAPPDATA%\Programs\gh\bin;%PATH%"

echo Uploading the cheat to GitHub...
git add -A >nul 2>&1
git diff --cached --quiet >nul 2>&1
if %errorlevel% equ 0 (
    echo Nothing changed since the last upload.
) else (
    git commit -q -m "update %DATE% %TIME%"
    if errorlevel 1 (
        echo COMMIT FAILED - check the window above.
    ) else (
        git push
        if errorlevel 1 (
            echo PUSH FAILED - check internet or sign in to GitHub again.
        ) else (
            echo Uploaded to GitHub OK.
        )
    )
)
echo.
pause
