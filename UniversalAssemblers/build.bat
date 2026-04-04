@echo off
cd /d "%~dp0"
echo Installing dependencies...
%USERPROFILE%\anaconda3\python.exe -m pip install -r requirements.txt --quiet
echo Validating imports...
%USERPROFILE%\anaconda3\python.exe -c "from src.gui.app import App; from launcher import _check_for_update" 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo [build] IMPORT CHECK FAILED -- fix Python errors before building.
    exit /b 1
)
echo Import check OK.
for /f "delims=" %%v in ('%USERPROFILE%\anaconda3\python.exe -c "from src.version import VERSION; print(VERSION)"') do set VERSION=%%v
echo Building UniversalAssemblers v%VERSION%...
%USERPROFILE%\anaconda3\Scripts\pyinstaller.exe UniversalAssemblers.spec --noconfirm
set BUILD_RESULT=%ERRORLEVEL%
if %BUILD_RESULT% == 0 (
    echo.
    echo Build successful! dist\UniversalAssemblers.exe  [v%VERSION%]
    echo Tag this commit and attach the EXE as a release asset on GitHub
    echo to enable auto-update for end users.
) else (
    echo.
    echo Build failed. Check output above for errors.
)
exit /b %BUILD_RESULT%
