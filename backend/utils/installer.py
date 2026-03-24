"""
OpenCode 安装检查工具
"""
import subprocess
import sys
import os
import platform
import shutil
import socket
import time
import asyncio
from typing import Optional, List
from pathlib import Path
from loguru import logger

import httpx


_opencode_server_process: Optional[subprocess.Popen] = None


def _collect_opencode_commands() -> List[List[str]]:
    commands: List[List[str]] = []
    seen = set()

    def _append_path(p: Path):
        key = str(p).strip().lower()
        if not key or key in seen:
            return
        if p.exists():
            seen.add(key)
            commands.append([str(p)])

    configured_path = os.environ.get("CODEBOT_OPENCODE_PATH", "").strip()
    if configured_path:
        configured = Path(configured_path)
        candidates = [configured]
        if configured.is_dir():
            candidates.extend([
                configured / "opencode.exe",
                configured / "opencode",
            ])
        for p in candidates:
            _append_path(p)

    # 1. Check for a bundled binary shipped alongside the packaged app.
    #    Electron sets CODEBOT_RESOURCES_DIR to process.resourcesPath.
    resources_dir = os.environ.get("CODEBOT_RESOURCES_DIR", "").strip()
    if resources_dir:
        candidates = [
            Path(resources_dir) / "opencode" / "opencode.exe",
            Path(resources_dir) / "opencode" / "opencode",
        ]
        for p in candidates:
            _append_path(p)

    repo_root = Path(__file__).resolve().parents[2]
    dev_candidates = [
        repo_root / "electron" / "vendor" / "opencode" / "opencode.exe",
        repo_root / "electron" / "vendor" / "opencode" / "opencode",
        repo_root / "vendor" / "opencode" / "opencode.exe",
        repo_root / "vendor" / "opencode" / "opencode",
    ]
    for p in dev_candidates:
        _append_path(p)

    # 2. Fall back to system PATH
    for name in ["opencode", "opencode-ai"]:
        path_found = shutil.which(name)
        if path_found:
            _append_path(Path(path_found))

    return commands


def _find_opencode_command() -> Optional[List[str]]:
    commands = _collect_opencode_commands()
    return commands[0] if commands else None


def _is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except Exception:
        return False


async def _is_opencode_http_ready(base_url: str) -> bool:
    # OpenCode >= 1.x 服务端仅支持 HTTP/2，先用 http2=True 检测
    for http2 in (True, False):
        try:
            async with httpx.AsyncClient(timeout=3, http2=http2) as client:
                response = await client.get(f"{base_url}/global/health")
                response.raise_for_status()
                data = response.json()
                return bool(data.get("healthy"))
        except Exception:
            continue
    return False


async def check_opencode_installed() -> bool:
    """检查 OpenCode 是否已安装"""
    commands = _collect_opencode_commands()
    if not commands:
        return False
    for command in commands:
        try:
            result = subprocess.run(
                [*command, "--version"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info(f"OpenCode 已安装：{result.stdout.strip()} ({command[0]})")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
    return False


async def install_opencode() -> bool:
    """安装 OpenCode"""
    system = platform.system()
    logger.info(f"检测到操作系统：{system}")
    
    try:
        if system == "Windows":
            # 尝试使用 scoop
            try:
                logger.info("尝试使用 Scoop 安装 OpenCode...")
                result = subprocess.run(
                    ["scoop", "install", "opencode"],
                    stdin=subprocess.DEVNULL,
                    check=True,
                    capture_output=True,
                    text=True
                )
                logger.info("Scoop 安装成功")
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                # 回退到 npm
                logger.info("Scoop 不可用，使用 npm 安装...")
                result = subprocess.run(
                    ["npm", "install", "-g", "opencode-ai"],
                    stdin=subprocess.DEVNULL,
                    check=True,
                    capture_output=True,
                    text=True
                )
                logger.info("npm 安装成功")
                return True
                
        elif system == "Darwin":
            # macOS - 使用 Homebrew
            logger.info("使用 Homebrew 安装 OpenCode...")
            result = subprocess.run(
                ["brew", "install", "anomalyco/tap/opencode"],
                stdin=subprocess.DEVNULL,
                check=True,
                capture_output=True,
                text=True
            )
            logger.info("Homebrew 安装成功")
            return True
            
        else:
            # Linux - 使用安装脚本
            logger.info("使用官方脚本安装 OpenCode...")
            script = "curl -fsSL https://opencode.ai/install | bash"
            result = subprocess.run(
                script,
                shell=True,
                stdin=subprocess.DEVNULL,
                check=True,
                capture_output=True,
                text=True
            )
            logger.info("安装成功")
            return True
            
    except subprocess.CalledProcessError as e:
        logger.error(f"安装失败：{e.stderr}")
        return False
    except Exception as e:
        logger.error(f"安装失败：{e}")
        return False


async def check_and_install_opencode() -> bool:
    """检查并安装 OpenCode"""
    # 检查是否已安装
    if await check_opencode_installed():
        return True
    
    # 未安装，执行安装
    logger.info("OpenCode 未安装，开始安装...")
    return await install_opencode()


async def start_opencode_server(port: int = 1120) -> int:
    """启动 OpenCode Server，返回实际监听的端口号（失败返回 0）。"""
    try:
        global _opencode_server_process

        # 1. 先检查指定端口是否已有正常运行的 OpenCode 服务
        base_url = f"http://127.0.0.1:{port}"
        if await _is_opencode_http_ready(base_url):
            logger.info(f"OpenCode Server 已在运行 ({base_url})")
            return port

        # 2. 若指定端口被其他进程占用，直接返回失败，由上层决定下一候选端口
        if _is_port_open("127.0.0.1", port):
            logger.warning(f"端口 {port} 已被非 OpenCode 进程占用，跳过该端口")
            return 0

        commands = _collect_opencode_commands()
        if not commands:
            logger.error("未找到 OpenCode 可执行文件（已检查打包目录和系统 PATH）")
            return 0

        try:
            from config import settings
            settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
            stdout_path = settings.LOGS_DIR / "opencode_server.stdout.log"
            stderr_path = settings.LOGS_DIR / "opencode_server.stderr.log"
        except Exception:
            stdout_path = Path.cwd() / "opencode_server.stdout.log"
            stderr_path = Path.cwd() / "opencode_server.stderr.log"
            stdout_path.parent.mkdir(parents=True, exist_ok=True)

        stdout_file = open(stdout_path, "a", encoding="utf-8")
        stderr_file = open(stderr_path, "a", encoding="utf-8")
        for command in commands:
            try:
                base_url = f"http://127.0.0.1:{port}"
                proc = subprocess.Popen(
                    [*command, "serve", "--port", str(port), "--hostname", "127.0.0.1"],
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    cwd=str(Path.home())
                )
                for _ in range(30):
                    if await _is_opencode_http_ready(base_url):
                        _opencode_server_process = proc
                        logger.info(f"OpenCode Server 已启动 ({base_url})，命令：{command[0]}")
                        return port
                    if proc.poll() is not None:
                        break
                    await asyncio.sleep(0.5)
                if proc.poll() is None:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                logger.warning(f"OpenCode 命令未就绪，尝试下一个候选：{command[0]}")
            except Exception as cmd_err:
                logger.warning(f"OpenCode 命令启动失败，尝试下一个候选：{command[0]} ({cmd_err})")

        logger.error(f"OpenCode Server 启动失败，所有候选命令均未就绪 ({base_url})")
        return 0
    except Exception as e:
        logger.error(f"启动 OpenCode Server 失败：{e}")
        return 0


def stop_opencode_server():
    global _opencode_server_process
    proc = _opencode_server_process
    _opencode_server_process = None
    if not proc:
        return
    try:
        proc.terminate()
    except Exception:
        pass


if __name__ == "__main__":
    import asyncio
    
    async def main():
        installed = await check_and_install_opencode()
        if installed:
            print("✅ OpenCode 已就绪")
        else:
            print("❌ OpenCode 安装失败")
    
    asyncio.run(main())
