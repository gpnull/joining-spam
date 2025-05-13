@echo off
REM Script to build the Python project "joining-spam" into a Windows executable.
REM This script assumes it is located in a 'scripts' subdirectory
REM AND IS BEING RUN FROM THE PROJECT ROOT DIRECTORY (e.g., D:\my_project\joining-spam).

REM --- Configuration ---
SET APP_NAME=joining_spam
SET MAIN_PYTHON_FILE=main.py
REM SET ICON_FILE_PATH=imgs\logo.png << Đã loại bỏ cấu hình icon
SET VENV_DIR=venv
REM ---------------------

REM Bỏ qua di chuyển thư mục, vì script được chạy từ thư mục gốc dự án
echo Current directory: %CD%
echo.

REM Check if the main Python script exists
IF NOT EXIST "%MAIN_PYTHON_FILE%" (
    echo ERROR: Main Python script "%MAIN_PYTHON_FILE%" not found in %CD%.
    echo Please ensure the script is in the project root AND you are running this build script from the project root.
    pause
    exit /b 1
)
echo Main script "%MAIN_PYTHON_FILE%" found.
echo.

REM Đã loại bỏ phần kiểm tra file icon

REM Check if virtual environment activation script exists
REM Paths for venv activation should be relative to the project root, which is now %CD%
IF NOT EXIST "%VENV_DIR%\Scripts\activate.bat" (
    echo WARNING: Virtual environment activation script not found at "%CD%\%VENV_DIR%\Scripts\activate.bat".
    echo Attempting to build using global Python environment or an already active venv.
    echo It is recommended to create and use a virtual environment for consistent builds.
    echo To create: python -m venv %VENV_DIR% (in project root)
    echo Then activate it before running this build script, or ensure this script can activate it.
    echo.
) ELSE (
    echo Activating virtual environment from "%CD%\%VENV_DIR%"...
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
REM echo Icon: %ICON_FILE_PATH% << Đã loại bỏ thông báo icon
echo.

REM Loại bỏ tùy chọn --icon khỏi lệnh PyInstaller
pyinstaller --onefile --windowed --name="%APP_NAME%" "%MAIN_PYTHON_FILE%"

echo.
IF %ERRORLEVEL% NEQ 0 (
    echo *******************************************************************
    echo * BUILD FAILED                                                   *
    echo *******************************************************************
    echo Please check the output above for PyInstaller errors.
) ELSE (
    echo *******************************************************************
    echo * BUILD SUCCESSFUL                                                 *
    echo *******************************************************************
    echo Executable created at: %CD%\dist\%APP_NAME%.exe
    echo You can find related build files in the "dist" and "build" directories.
)
echo.

echo Build script finished.
pause