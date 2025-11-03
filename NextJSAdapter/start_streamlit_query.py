"""
启动 QueryEngine Streamlit 应用
端口: 8504
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 切换到项目根目录
os.chdir(str(project_root))

def main():
    """启动 Streamlit 应用"""
    import subprocess
    
    streamlit_app = project_root / "SingleEngineApp" / "query_engine_streamlit_app.py"
    
    if not streamlit_app.exists():
        print(f"错误: 找不到 Streamlit 应用: {streamlit_app}")
        return
    
    print("=" * 60)
    print("QueryEngine Streamlit 应用")
    print("=" * 60)
    print(f"应用路径: {streamlit_app}")
    print(f"访问地址: http://localhost:8504")
    print("=" * 60)
    
    # 启动 Streamlit
    subprocess.run([
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(streamlit_app),
        "--server.port=8504",
        "--server.address=0.0.0.0",
        "--server.headless=true",
        "--browser.gatherUsageStats=false"
    ])

if __name__ == "__main__":
    main()
