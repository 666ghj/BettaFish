"""
Utility helpers for coordinating host/container port selection.
"""
from __future__ import annotations

import socket
import sys
from pathlib import Path
from typing import Iterable, Optional, Union

from loguru import logger


def _iter_hosts_for_port_check(host: Optional[str]) -> Iterable[str]:
    """
    Yield candidate hostnames or IPs to probe when checking port availability.

    When binding to all interfaces (0.0.0.0 / ::) we verify against the loopback
    address to detect conflicts on the local machine.
    """
    if host in ("0.0.0.0", "", None):
        yield "127.0.0.1"
    elif host in ("::", "::0"):
        yield "::1"
    else:
        yield host


def is_port_in_use(host: str, port: int) -> bool:
    """
    Check whether the given TCP port is already occupied on the specified host.
    """
    for candidate in _iter_hosts_for_port_check(host):
        try:
            addr_info_list = socket.getaddrinfo(candidate, port, type=socket.SOCK_STREAM)
        except socket.gaierror:
            logger.warning(f"无法解析主机地址 {candidate}，跳过端口检查")
            continue

        for family, socktype, proto, _, sockaddr in addr_info_list:
            with socket.socket(family, socktype, proto) as sock:
                sock.settimeout(0.5)
                if sock.connect_ex(sockaddr) == 0:
                    return True
    return False


def prompt_for_available_port(host: str, initial_port: int) -> int:
    """
    Prompt for the next available port when the requested port is already taken.

    The prompt text is written to stderr so that callers can safely capture stdout
    without hiding the interactive question (useful for shell scripts).
    """
    port = initial_port
    while True:
        if not is_port_in_use(host, port):
            if port != initial_port:
                logger.warning(f"端口 {initial_port} 已被占用，改为使用端口 {port}")
            return port

        logger.warning(f"端口 {port} 已被占用")

        if not sys.stdin.isatty():
            logger.error("当前环境不可交互确认端口切换，操作已取消")
            raise SystemExit(1)

        while True:
            prompt = f"端口 {port} 已被占用，是否尝试使用端口 {port + 1}? [y/n]: "
            print(prompt, end="", flush=True, file=sys.stderr)
            try:
                choice = input().strip().lower()
            except (EOFError, KeyboardInterrupt):
                logger.error("未能获取用户输入，操作已取消")
                raise SystemExit(1)

            if choice == 'y':
                port += 1
                break
            if choice == 'n':
                logger.error("用户拒绝更换端口，操作已取消")
                raise SystemExit(1)

            print("请输入 'y' 或 'n'", file=sys.stderr)


def _resolve_env_path(env_path: Union[None, str, Path]) -> Path:
    if env_path is not None:
        return Path(env_path).expanduser()
    from config import ENV_FILE  # Imported lazily to avoid circular imports.
    return Path(ENV_FILE)


def update_env_port(port: int, env_path: Union[None, str, Path] = None) -> bool:
    """
    Ensure the PORT entry inside the .env file matches the requested value.

    Returns:
        bool: True if the file was updated, False if no change was required.
    """
    path = _resolve_env_path(env_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    key = "PORT"
    new_assignment = f"{key}={port}"

    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    updated = False
    for idx, line in enumerate(lines):
        stripped = line.strip()

        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        existing_key, _ = stripped.split("=", 1)
        if existing_key.strip() == key:
            if line.strip() == new_assignment:
                return False
            lines[idx] = new_assignment
            updated = True
            break

    if not updated:
        lines.append(new_assignment)
        updated = True

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info(f".env 中的 {key} 已更新为 {port}")
    return True


def main() -> None:
    """
    CLI helper used by scripts/build_and_run_docker.sh.

    Writes the resolved host, port, and a flag indicating whether the .env file
    was changed to stdout (one per line) for easy parsing by shell scripts.
    """
    from config import settings

    host = settings.HOST
    initial_port = settings.PORT

    port = prompt_for_available_port(host, initial_port)
    changed = update_env_port(port)

    print(host)
    print(port)
    print("1" if changed else "0")


if __name__ == "__main__":
    main()
