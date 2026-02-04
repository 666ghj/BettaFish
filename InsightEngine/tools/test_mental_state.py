"""
心态分析功能测试文件
专门测试新增的焦虑/迷茫/希望/绝望/躺平分类功能
"""

import sys
import os
import time

# 添加路径，确保能导入原文件
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入你修改后的情感分析器
from sentiment_analyzer import WeiboMultilingualSentimentAnalyzer


def test_mental_state_analysis():
    """
    测试心态分析功能
    """
    print("=" * 60)
    print("心态分析功能测试")
    print("=" * 60)
    
    # 1. 创建分析器实例
    print("\n1. 初始化分析器...")
    analyzer = WeiboMultilingualSentimentAnalyzer()
    
    # 2. 初始化模型（如果还没有初始化）
    if not analyzer.is_initialized:
        print("正在加载情感分析模型...")
        analyzer.initialize()
    
    # 3. 准备测试数据 - 每种心态一个例子
    test_cases = [
        {
            "text": "明天就要考试了，我一道题都不会做，这下完蛋了",
            "expected_state": "焦虑",
            "description": "考试焦虑场景"
        },
        {
            "text": "大学毕业了，不知道该考研还是找工作，感觉每条路都不确定",
            "expected_state": "迷茫",
            "description": "人生选择迷茫"
        },
        {
            "text": "虽然现在很困难，但我相信只要坚持努力，未来一定会变好",
            "expected_state": "希望",
            "description": "积极乐观"
        },
        {
            "text": "尝试了所有方法都没有用，一切努力都是白费，我放弃了",
            "expected_state": "绝望",
            "description": "彻底失望"
        },
        {
            "text": "随便吧，公司怎样就怎样，我也不想争取什么了",
            "expected_state": "躺平",
            "description": "消极接受"
        },
        {
            "text": "今天中午吃了牛肉面，味道还不错",
            "expected_state": "中性",  # 这个应该不属于任何特定心态
            "description": "中性日常"
        }
    ]
    
    print(f"\n2. 准备测试{len(test_cases)}个案例...")
    
    # 4. 逐个测试
    print("\n3. 开始测试心态分析功能：")
    print("-" * 60)
    
    for i, test_case in enumerate(test_cases, 1):
        text = test_case["text"]
        expected = test_case["expected_state"]
        desc = test_case["description"]
        
        print(f"\n测试案例 {i}: {desc}")
        print(f"输入文本: \"{text[:50]}...\"")
        
        # 记录开始时间
        start_time = time.time()
        
        # 调用你新增的心态分析方法
        result = analyzer.analyze_mental_state(text)
        
        # 计算耗时
        elapsed_time = time.time() - start_time
        
        # 显示结果
        print(f"分析耗时: {elapsed_time:.2f}秒")
        print(f"分析结果: {result.get('mental_state', '未知')}")
        print(f"分析成功: {'✓' if result.get('success', False) else '✗'}")
        
        if result.get('success', False):
            actual_state = result.get('mental_state', '未知')
            if actual_state == expected:
                print(f"状态: ✅ 通过 (期望: '{expected}', 实际: '{actual_state}')")
            else:
                print(f"状态: ❌ 不符 (期望: '{expected}', 实际: '{actual_state}')")
        else:
            print(f"状态: ⚠️ 失败 (原因: {result.get('reason', '未知错误')})")
        
        print(f"详细信息: {result}")
    
    # 5. 测试批量分析功能
    print("\n" + "=" * 60)
    print("4. 测试批量分析功能：")
    print("-" * 60)
    
    # 提取所有测试文本
    batch_texts = [case["text"] for case in test_cases]
    
    print(f"批量分析 {len(batch_texts)} 条文本...")
    batch_start_time = time.time()
    
    batch_results = analyzer.analyze_mental_state_batch(batch_texts)
    
    batch_elapsed_time = time.time() - batch_start_time
    
    print(f"批量分析总耗时: {batch_elapsed_time:.2f}秒")
    print(f"平均每条耗时: {batch_elapsed_time/len(batch_texts):.2f}秒")
    
    # 统计结果
    success_count = sum(1 for r in batch_results if r.get('success', False))
    print(f"\n批量分析结果统计:")
    print(f"  成功分析: {success_count}/{len(batch_results)}")
    print(f"  成功率: {success_count/len(batch_results)*100:.1f}%")
    
    # 显示心态分布
    print(f"\n心态分布:")
    state_counts = {}
    for result in batch_results:
        if result.get('success', False):
            state = result.get('mental_state', '未知')
            state_counts[state] = state_counts.get(state, 0) + 1
    
    for state, count in state_counts.items():
        print(f"  {state}: {count}条")
    
    # 6. 测试整合功能（调用原系统的analyze_query_results）
    print("\n" + "=" * 60)
    print("5. 测试整合到原系统：")
    print("-" * 60)
    
    # 模拟原系统的查询结果格式
    mock_query_results = [
        {"content": "工作压力好大，天天加班到深夜，快撑不住了"},
        {"content": "不知道自己喜欢什么工作，感觉做什么都不合适"},
        {"content": "新项目虽然难，但团队氛围很好，我觉得能成功"},
        {"content": "投了100份简历都没回复，可能我真的不行"},
        {"content": "晋升又没我，算了，就这样混日子吧"}
    ]
    
    print(f"模拟原系统查询数据: {len(mock_query_results)}条记录")
    
    # 调用原系统的方法（会自动调用你新增的心态分析）
    integrated_result = analyzer.analyze_query_results(
        mock_query_results,
        text_field="content",
        min_confidence=0.5
    )
    
    # 检查结果中是否包含心态分析
    sentiment_analysis = integrated_result.get("sentiment_analysis", {})
    
    if "mental_state_analysis" in sentiment_analysis:
        print("✅ 心态分析已成功整合到原系统！")
        mental_analysis = sentiment_analysis["mental_state_analysis"]
        print(f"   分析数量: {mental_analysis.get('total_analyzed', 0)}")
        print(f"   成功数量: {mental_analysis.get('success_count', 0)}")
        print(f"   心态分布: {mental_analysis.get('mental_state_distribution', {})}")
    else:
        print("❌ 心态分析未成功整合，请检查代码修改")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    
    return batch_results


def check_api_configuration():
    """
    检查API配置
    """
    print("\n" + "=" * 60)
    print("API配置检查")
    print("=" * 60)
    
    analyzer = WeiboMultilingualSentimentAnalyzer()
    
    # 检查配置是否存在
    if hasattr(analyzer, 'mental_state_config'):
        config = analyzer.mental_state_config
        print("✅ 找到心态分析配置")
        
        # 检查关键配置项
        api_key = config.get("api_key", "")
        base_url = config.get("base_url", "")
        model_name = config.get("model_name", "")
        
        print(f"   API地址: {base_url}")
        print(f"   模型名称: {model_name}")
        
        if api_key and not api_key.startswith("sk-xxxxxxxx"):
            print("   API密钥: ✅ 已配置（非默认值）")
        else:
            print("   API密钥: ❌ 需要配置！")
            print("\n   💡 请修改 sentiment_analyzer.py 文件：")
            print("   1. 在 __init__ 方法中找到 mental_state_config")
            print("   2. 将 api_key 替换为你的真实API密钥")
            print("   3. 根据你的AI服务商调整 base_url 和 model_name")
    else:
        print("❌ 未找到心态分析配置，请确认修改了 __init__ 方法")


if __name__ == "__main__":
    """
    主测试程序
    """
    
    print("心态分析功能独立测试")
    print("此测试不会影响主程序运行")
    print()
    
    # 检查配置
    check_api_configuration()
    
    # 询问是否继续测试
    response = input("\n是否开始测试心态分析功能？(y/n): ")
    
    if response.lower() == 'y':
        try:
            # 运行测试
            results = test_mental_state_analysis()
            
            # 保存测试结果到文件
            output_file = "mental_state_test_results.txt"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("心态分析测试结果\n")
                f.write("=" * 50 + "\n\n")
                for i, result in enumerate(results, 1):
                    f.write(f"测试案例 {i}:\n")
                    f.write(f"  文本: {result.get('text', '')}\n")
                    f.write(f"  心态: {result.get('mental_state', '未知')}\n")
                    f.write(f"  成功: {result.get('success', False)}\n")
                    if not result.get('success', False):
                        f.write(f"  原因: {result.get('reason', '未知')}\n")
                    f.write("\n")
            
            print(f"\n📄 测试结果已保存到: {output_file}")
            
        except Exception as e:
            print(f"\n❌ 测试过程中发生错误: {e}")
            print("\n可能的原因:")
            print("1. 未正确修改 sentiment_analyzer.py 文件")
            print("2. API配置错误或网络问题")
            print("3. 缺少必要的Python库（如requests）")
            print("\n💡 解决方法:")
            print("1. 确保已按照步骤修改了三个位置")
            print("2. 检查API密钥是否正确")
            print("3. 安装requests库: pip install requests")
    else:
        print("\n测试已取消")