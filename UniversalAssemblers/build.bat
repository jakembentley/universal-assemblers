@echo off
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
