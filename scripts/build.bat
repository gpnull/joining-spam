@echo off
REM Script to build the Python project "joining-spam" into a Windows executable.
REM This script assumes it is located in a 'scripts' subdirectory of the project root.

REM --- Configuration ---
SET APP_NAME=joining_spam
SET MAIN_PYTHON_FILE=main.py
SET ICON_FILE_PATH=imgs\logo.png
SET VENV_DIR=venv
REM ---------------------

echo Navigating to project root directory...
cd ..
echo Current directory: %CD%
echo.

REM Check if the main Python script exists
IF NOT EXIST "%MAIN_PYTHON_FILE%" (
    echo ERROR: Main Python script "%MAIN_PYTHON_FILE%" not found in %CD%.
    echo Please ensure the script is in the project root.
    pause
    exit /b 1
)
echo Main script "%MAIN_PYTHON_FILE%" found.
echo.

REM Check if the icon file exists
IF NOT EXIST "%ICON_FILE_PATH%" (
    echo WARNING: Icon file "%ICON_FILE_PATH%" not found in %CD%.
    echo The build will proceed, but PyInstaller might use a default icon or show an error.
) ELSE (
    echo Icon file "%ICON_FILE_PATH%" found.
)
echo.

REM Check if virtual environment activation script exists
IF NOT EXIST "%VENV_DIR%\Scripts\activate.bat" (
    echo WARNING: Virtual environment activation script not found at "%VENV_DIR%\Scripts\activate.bat".
    echo Attempting to build using global Python environment or an already active venv.
    echo It is recommended to create and use a virtual environment for consistent builds.
    echo To create: python -m venv %VENV_DIR% (in project root)
    echo Then activate it before running this build script, or ensure this script can activate it.
    echo.
    REM If venv activate is not found, we proceed hoping PyInstaller is globally available or venv is already active
) ELSE (
    echo Activating virtual environment from "%VENV_DIR%"...
    CALL "%VENV_DIR%\Scripts\activate.bat"
    IF ERRORLEVEL 1 (
        echo ERROR: Failed to activate virtual environment. Please check the path and venv integrity.
        pause
        exit /b 1
    )
    echo Virtual environment activated.
    echo.
)

echo Ensuring PyInstaller and pynput are installed/updated...
pip install --upgrade pyinstaller pynput
IF ERRORLEVEL 1 (
    echo ERROR: Failed to install/update PyInstaller or pynput. Check your pip and internet connection.
    pause
    exit /b 1
)
echo Dependencies checked/installed.
echo.

echo Starting the PyInstaller build process...
echo   App Name: %APP_NAME%.exe
echo   Main Script: %MAIN_PYTHON_FILE%
echo   Icon: %ICON_FILE_PATH%
echo.

pyinstaller --onefile --windowed --icon="%ICON_FILE_PATH%" --name="%APP_NAME%" "%MAIN_PYTHON_FILE%"

echo.
IF %ERRORLEVEL% NEQ 0 (
    echo *******************************************************************
    echo * BUILD FAILED                           *
    echo *******************************************************************
    echo Please check the output above for PyInstaller errors.
) ELSE (
    echo *******************************************************************
    echo * BUILD SUCCESSFUL                         *
    echo *******************************************************************
    echo Executable created at: %CD%\dist\%APP_NAME%.exe
    echo You can find related build files in the "dist" and "build" directories.
)
echo.

REM The virtual environment deactivates automatically when the script/CMD session ends
REM if it was activated by this script using CALL.
REM If you activated it manually before running the script, you'd manually deactivate.

echo Build script finished.
pause