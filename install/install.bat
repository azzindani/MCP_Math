@echo off
REM install.bat — Install math-mcp-server to %USERPROFILE%\.mcp_servers\math-mcp-server
setlocal enabledelayedexpansion

set "INSTALL_DIR=%USERPROFILE%\.mcp_servers\math-mcp-server"
set "REPO_URL=https://github.com/azzindani/mcp_math.git"

echo === math-mcp-server installer ===

REM Check git
where git >nul 2>&1
if errorlevel 1 (
    echo ERROR: git is required. Install Git for Windows and retry.
    exit /b 1
)

REM Check uv
where uv >nul 2>&1
if errorlevel 1 (
    echo Installing uv...
    powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
)

REM Clone or update
if exist "%INSTALL_DIR%\.git" (
    echo Updating existing installation...
    git -C "%INSTALL_DIR%" fetch origin
    git -C "%INSTALL_DIR%" reset --hard FETCH_HEAD
) else (
    echo Cloning repository...
    if not exist "%USERPROFILE%\.mcp_servers" mkdir "%USERPROFILE%\.mcp_servers"
    git clone "%REPO_URL%" "%INSTALL_DIR%"
)

cd /d "%INSTALL_DIR%"

REM Install dependencies
echo Installing Python dependencies...
uv sync --no-dev

echo.
echo Installation complete: %INSTALL_DIR%
echo.
echo Add the following to your mcp.json:
echo {
echo   "math-mcp-server": {
echo     "command": "powershell",
echo     "args": ["-Command", "cd '%INSTALL_DIR%'; uv run python server.py --transport stdio"],
echo     "timeout": 600000
echo   }
echo }
