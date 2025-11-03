"""
服务验证脚本
快速检查 QueryEngine 和 ReportEngine 是否正常运行
"""

import requests
import json
import sys
from colorama import init, Fore, Style

# 初始化 colorama
init(autoreset=True)

def check_service(name, url):
    """检查单个服务"""
    print(f"\n检查 {name}...")
    print(f"URL: {url}")
    
    try:
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"{Fore.GREEN}✓ {name} 运行正常")
                print(f"  状态: {json.dumps(data, indent=2, ensure_ascii=False)}")
                return True
            except json.JSONDecodeError:
                print(f"{Fore.RED}✗ {name} 返回了 HTML 而不是 JSON")
                print(f"  这意味着 API 路由未正确配置")
                print(f"  响应内容: {response.text[:200]}...")
                return False
        else:
            print(f"{Fore.RED}✗ {name} 返回错误状态码: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"{Fore.RED}✗ {name} 无法连接")
        print(f"  服务可能未启动")
        return False
    except requests.exceptions.Timeout:
        print(f"{Fore.YELLOW}⚠ {name} 响应超时")
        return False
    except Exception as e:
        print(f"{Fore.RED}✗ {name} 检查失败: {str(e)}")
        return False


def main():
    print("=" * 60)
    print(f"{Fore.CYAN}Agent 服务验证工具")
    print("=" * 60)
    
    services = [
        ("QueryEngine", "http://localhost:8503/api/status"),
        ("ReportEngine", "http://localhost:8502/api/report/status")
    ]
    
    results = []
    for name, url in services:
        result = check_service(name, url)
        results.append((name, result))
    
    print("\n" + "=" * 60)
    print("验证结果:")
    print("=" * 60)
    
    all_ok = True
    for name, result in results:
        status = f"{Fore.GREEN}✓ 正常" if result else f"{Fore.RED}✗ 异常"
        print(f"  {name}: {status}")
        if not result:
            all_ok = False
    
    print()
    
    if all_ok:
        print(f"{Fore.GREEN}所有服务运行正常！")
        print(f"\n可以启动 Next.js 项目:")
        print(f"  cd d:\\myReact\\community")
        print(f"  npm run dev")
        print(f"\n然后访问: http://localhost:3000/report-generation")
        sys.exit(0)
    else:
        print(f"{Fore.RED}部分服务异常，请检查:")
        print(f"\n1. 确保服务已启动:")
        print(f"   cd d:\\myReact\\BettaFish\\NextJSAdapter")
        print(f"   python start_all_services.py")
        print(f"\n2. 检查端口占用:")
        print(f"   netstat -ano | findstr \"8503\"")
        print(f"   netstat -ano | findstr \"8502\"")
        print(f"\n3. 查看服务日志中的错误信息")
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}验证已取消")
        sys.exit(1)
