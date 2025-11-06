"""
简单的测试运行脚本

可以直接运行此脚本来执行测试
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from test_monitor import TestLogMonitor


def main():
    """运行所有测试"""
    print("=" * 60)
    print("ForumEngine 日志解析测试")
    print("=" * 60)
    print()
    
    test_instance = TestLogMonitor()
    test_instance.setup_method()
    
    # 获取所有测试方法
    test_methods = [method for method in dir(test_instance) if method.startswith('test_')]
    
    passed = 0
    failed = 0
    
    for test_method_name in test_methods:
        test_method = getattr(test_instance, test_method_name)
        print(f"运行测试: {test_method_name}...", end=" ")
        
        try:
            test_method()
            print("✓ 通过")
            passed += 1
        except AssertionError as e:
            print(f"✗ 失败: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ 错误: {e}")
            failed += 1
    
    print()
    print("=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()

