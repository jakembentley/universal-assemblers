@echo off
cd /d "%~dp0"
echo Installing dependencies...
%USERPROFILE%\anaconda3\python.exe -m pip install -r requirements.txt --quiet
echo Validating imports...
%USERPROFILE%\anaconda3\python.exe -c "from src.gui.app import App" 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo [build] IMPORT CHECK FAILED -- fix Python errors before building.
    exit /b 1
)
echo Import check OK.
echo Building UniversalAssemblers...
%USERPROFILE%\anaconda3\Scripts\pyinstaller.exe UniversalAssemblers.spec --noconfirm
set BUILD_RESULT=%ERRORLEVEL%
if %BUILD_RESULT% == 0 (
    echo.
    echo Build successful! Executable is in dist\UniversalAssemblers.exe
) else (
    echo.
    echo Build failed. Check output above for errors.
)
exit /b %BUILD_RESULT%
