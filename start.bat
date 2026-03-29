@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title 盐城港Agent

echo ========================================
echo   盐城港Agent 启动中...
echo ========================================

cd /d "%~dp0"

:: 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未安装Python，请先安装Python 3.8+
    echo.
    echo 按任意键退出...
    pause >nul
    exit /b 1
)

echo [INFO] Python 已找到

:: 设置虚拟环境路径（便携版：支持backend\venv和venv两种位置）
set "VENV_DIR="
if exist "backend\venv\Scripts\python.exe" (
    set "VENV_DIR=backend\venv"
) else if exist "venv\Scripts\python.exe" (
    set "VENV_DIR=venv"
)

set "PYTHON="
set "PIP="

if defined VENV_DIR (
    set "PYTHON=%VENV_DIR%\Scripts\python.exe"
    set "PIP=%VENV_DIR%\Scripts\pip.exe"
    echo [INFO] 使用已有虚拟环境: %VENV_DIR%
) else (
    :: 创建新虚拟环境
    echo [INFO] 首次运行，正在创建虚拟环境...
    echo [INFO] 这可能需要几分钟...
    if exist "backend" (
        python -m venv backend\venv
        if exist "backend\venv\Scripts\python.exe" (
            set "VENV_DIR=backend\venv"
        )
    ) else (
        python -m venv venv
        if exist "venv\Scripts\python.exe" (
            set "VENV_DIR=venv"
        )
    )
)

if not defined VENV_DIR (
    echo [错误] 创建虚拟环境失败
    pause
    exit /b 1
)

set "PYTHON=%VENV_DIR%\Scripts\python.exe"
set "PIP=%VENV_DIR%\Scripts\pip.exe"

:: 检查依赖
echo [INFO] 检查依赖...
"%PIP%" show fastapi >nul 2>&1
if errorlevel 1 (
    echo [INFO] 安装依赖中...
    if exist "backend\requirements.txt" (
        "%PIP%" install -r backend\requirements.txt
    ) else (
        "%PIP%" install fastapi uvicorn vue-element-plus pinia
    )
    if errorlevel 1 (
        echo [错误] 安装依赖失败
        pause
        exit /b 1
    )
)

:: 启动后端
echo.
echo [INFO] 启动服务...
echo.
"%PYTHON%" backend\main.py

:: 如果后端退出，显示错误
if errorlevel 1 (
    echo.
    echo [错误] 服务启动失败
)

echo.
echo 按任意键退出...
pause >nul
