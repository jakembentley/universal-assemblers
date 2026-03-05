@echo off
echo Building UniversalAssemblers...
C:\Users\Admin\anaconda3\Scripts\pyinstaller.exe UniversalAssemblers.spec --noconfirm
if %ERRORLEVEL% == 0 (
    echo.
    echo Build successful! Executable is in dist\UniversalAssemblers.exe
) else (
    echo.
    echo Build failed. Check output above for errors.
)
pause
