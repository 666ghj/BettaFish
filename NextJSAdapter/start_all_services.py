"""
Next.js 适配层 - 启动脚本
同时启动 QueryEngine (8503) 和 ReportEngine (8502) 服务
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def start_query_engine():
    """启动 QueryEngine 服务"""
    print("启动 QueryEngine 服务 (端口 8503)...")
    
    script_path = Path(__file__).parent / 'query_engine_server.py'
    
    if sys.platform == 'win32':
        # Windows 使用 start 命令在新窗口打开
        cmd = f'start "QueryEngine Service" cmd /k python "{script_path}"'
        subprocess.Popen(cmd, shell=True)
    else:
        # Linux/Mac 使用 gnome-terminal 或 xterm
        subprocess.Popen(['python', str(script_path)])
    
    time.sleep(2)
    print("✓ QueryEngine 服务已启动")


def start_report_engine():
    """启动 ReportEngine 服务"""
    print("启动 ReportEngine 服务 (端口 8502)...")
    
    script_path = Path(__file__).parent / 'report_engine_server.py'
    
    if sys.platform == 'win32':
        # Windows 使用 start 命令在新窗口打开
        cmd = f'start "ReportEngine Service" cmd /k python "{script_path}"'
        subprocess.Popen(cmd, shell=True)
    else:
        # Linux/Mac
        subprocess.Popen(['python', str(script_path)])
    
    time.sleep(2)
    print("✓ ReportEngine 服务已启动")


def start_streamlit_query():
    """启动 QueryEngine Streamlit 界面"""
    print("启动 QueryEngine Streamlit 界面 (端口 8504)...")
    
    script_path = Path(__file__).parent / 'start_streamlit_query.py'
    
    if sys.platform == 'win32':
        # Windows 使用 start 命令在新窗口打开
        cmd = f'start "QueryEngine Streamlit" cmd /k python "{script_path}"'
        subprocess.Popen(cmd, shell=True)
    else:
        # Linux/Mac
        subprocess.Popen(['python', str(script_path)])
    
    time.sleep(3)
    print("✓ QueryEngine Streamlit 界面已启动")


def main():
    print("=" * 60)
    print("BettaFish Agent 服务启动器")
    print("=" * 60)
    print()
    
    # 启动 QueryEngine Flask API
    start_query_engine()
    
    # 启动 QueryEngine Streamlit 界面
    start_streamlit_query()
    
    # 启动 ReportEngine
    start_report_engine()
    
    print()
    print("=" * 60)
    print("所有服务已启动!")
    print("=" * 60)
    print()
    print("服务信息:")
    print("  • QueryEngine API:       http://localhost:8503")
    print("  • QueryEngine Streamlit: http://localhost:8504")
    print("  • ReportEngine:          http://localhost:8502")
    print()
    print("验证服务:")
    print("  • QueryEngine API:  http://localhost:8503/api/status")
    print("  • QueryEngine UI:   http://localhost:8504")
    print("  • ReportEngine:     http://localhost:8502/api/report/status")
    print()
    print("提示: 服务已在新窗口中启动，请不要关闭它们")
    print()
    input("按 Enter 键退出...")


if __name__ == '__main__':
    main()
