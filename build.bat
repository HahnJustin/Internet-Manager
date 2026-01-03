@echo off
setlocal ENABLEEXTENSIONS

set "ROOT=%~dp0"
set "DIST=%ROOT%dist"

set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
set "INNO_SCRIPT=%ROOT%InstallerScript.iss"

echo Installing GUI requirements...
python -m pip install -r "%ROOT%src\requirements\requirements-gui.txt"

echo Installing Server requirements...
python -m pip install -r "%ROOT%src\requirements\requirements-server.txt"

echo Installing Utility requirements...
python -m pip install -r "%ROOT%src\requirements\requirements-util.txt"

echo.
echo === Building executables ===

pyinstaller "%ROOT%src\server.spec" --clean
pyinstaller "%ROOT%src\internet_manager.spec" --clean
pyinstaller "%ROOT%src\internet_manager_utility.spec" --clean

echo.
echo === Verifying build outputs ===

if not exist "%DIST%\internet_manager_server.exe" (
    echo ERROR: server build missing
    goto :error
)

if not exist "%DIST%\internet_manager.exe" (
    echo ERROR: internet_manager build missing
    goto :error
)

if not exist "%DIST%\internet_manager_utility.exe" (
    echo ERROR: utility build missing
    goto :error
)

echo All executables verified.

echo.
echo === Running Inno Setup ===

if not exist "%ISCC%" (
    echo ERROR: Inno Setup Compiler not found
    goto :error
)

if not exist "%INNO_SCRIPT%" (
    echo ERROR: Inno script not found
    goto :error
)

"%ISCC%" "%INNO_SCRIPT%"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Inno Setup failed
    goto :error
)

echo.
echo === BUILD + INSTALLER COMPLETED SUCCESSFULLY ===
pause
exit /b 0

:error
echo.
echo === BUILD FAILED ===
pause
exit /b 1
