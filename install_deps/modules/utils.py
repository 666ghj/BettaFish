import sys
import os
import platform
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Tuple


def get_system_info() -> Dict[str, str]:
    return {
        "platform": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "architecture": platform.architecture()[0]
    }


def run_command(command: List[str], check: bool = True, capture_output: bool = True) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            command,
            check=check,
            capture_output=capture_output,
            text=True,
            timeout=300  # 5分钟超时
        )
        return result
    except subprocess.TimeoutExpired:
        raise subprocess.TimeoutExpired(f"命令执行超时: {' '.join(command)}", 300)
    except subprocess.CalledProcessError as e:
        raise subprocess.CalledProcessError(e.returncode, command, e.stdout, f"命令执行失败: {' '.join(command)}\n错误信息: {e.stderr}")


def check_command_exists(command: str) -> bool:
    try:
        result = run_command(["which" if platform.system() != "Windows" else "where", command], check=False)
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return False


def _build_prompt_text(prompt: str, default: Optional[str], choices: Optional[List[str]]) -> str:
    """构建提示文本"""
    if choices:
        choice_str = "/".join(choices)
        if default:
            return f"{prompt} (默认: {default}) ({choice_str}): "
        else:
            return f"{prompt} ({choice_str}): "
    else:
        if default:
            return f"{prompt} (默认: {default}): "
        else:
            return f"{prompt}: "


def _validate_input(user_input: str, default: Optional[str], choices: Optional[List[str]]) -> Optional[str]:
    """验证用户输入，返回有效输入或None"""
    # 使用默认值
    if not user_input and default:
        return default

    # 验证选择
    if choices and user_input and user_input not in choices:
        print(f"请选择以下选项之一: {', '.join(choices)}")
        return None

    return user_input


def get_user_input(prompt: str, default: Optional[str] = None, choices: Optional[List[str]] = None) -> str:
    while True:
        prompt_text = _build_prompt_text(prompt, default, choices)
        user_input = input(prompt_text).strip()

        validated_input = _validate_input(user_input, default, choices)
        if validated_input is not None:
            return validated_input


def confirm(message: str, default: bool = True) -> bool:
    default_str = "Y/n" if default else "y/N"
    while True:
        user_input = input(f"{message} ({default_str}): ").strip().lower()

        if not user_input:
            return default

        if user_input in ["y", "yes", "是", "true", "1"]:
            return True
        elif user_input in ["n", "no", "否", "false", "0"]:
            return False
        else:
            print("请输入 y/yes/是 或 n/no/否")


def format_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)

    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1

    return f"{size:.1f}{size_names[i]}"


def get_free_space(path: str = ".") -> int:
    try:
        if platform.system() == "Windows":
            import shutil
            _, _, free_bytes = shutil.disk_usage(path)
            return free_bytes
        else:
            stat = os.statvfs(path)
            return stat.f_bavail * stat.f_frsize
    except (OSError, AttributeError, ImportError):
        return 0


def validate_python_version(min_version: str = "3.9") -> Tuple[bool, str]:
    current_version = sys.version_info
    min_version_tuple = tuple(map(int, min_version.split(".")))

    if current_version >= min_version_tuple:
        return True, f"Python版本 {sys.version.split()[0]} 符合要求 (≥ {min_version})"
    else:
        return False, f"Python版本过低: {sys.version.split()[0]}，需要 ≥ {min_version}"