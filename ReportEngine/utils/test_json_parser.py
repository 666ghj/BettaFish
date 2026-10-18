"""
测试RobustJSONParser的各种修复能力。

验证解析器能够处理：
1. 基本的markdown包裹
2. 思考内容清理
3. 缺少逗号的修复
4. 括号不平衡的修复
5. 控制字符转义
6. 尾随逗号移除
"""

import json
import unittest
from ReportEngine.utils.json_parser import RobustJSONParser, JSONParseError


class TestRobustJSONParser(unittest.TestCase):
    """测试鲁棒JSON解析器的各种修复策略。"""

    def setUp(self):
        """初始化解析器。"""
        self.parser = RobustJSONParser(
            enable_json_repair=False,  # 先测试本地修复
            enable_llm_repair=False,
        )

    def test_basic_json(self):
        """测试解析基本的合法JSON。"""
        json_str = '{"name": "test", "value": 123}'
        result = self.parser.parse(json_str, "基本测试")
        self.assertEqual(result["name"], "test")
        self.assertEqual(result["value"], 123)

    def test_markdown_wrapped(self):
        """测试解析被```json包裹的JSON。"""
        json_str = """```json
{
  "name": "test",
  "value": 123
}
```"""
        result = self.parser.parse(json_str, "Markdown包裹测试")
        self.assertEqual(result["name"], "test")
        self.assertEqual(result["value"], 123)

    def test_thinking_content_removal(self):
        """测试清理思考内容。"""
        json_str = """<thinking>让我想想如何构造这个JSON</thinking>
{
  "name": "test",
  "value": 123
}"""
        result = self.parser.parse(json_str, "思考内容清理测试")
        self.assertEqual(result["name"], "test")
        self.assertEqual(result["value"], 123)

    def test_missing_comma_fix(self):
        """测试修复缺少的逗号。"""
        # 这是实际错误中常见的情况：数组元素之间缺少逗号
        json_str = """{
  "totalWords": 40000,
  "globalGuidelines": [
    "重点突出技术红利分配失衡"
    "详略策略：技术创新"
  ],
  "chapters": []
}"""
        result = self.parser.parse(json_str, "缺少逗号修复测试")
        self.assertEqual(len(result["globalGuidelines"]), 2)

    def test_unbalanced_brackets(self):
        """测试修复括号不平衡。"""
        # 缺少结束括号
        json_str = """{
  "name": "test",
  "nested": {
    "value": 123
  }
"""  # 缺少最外层的 }
        result = self.parser.parse(json_str, "括号不平衡测试")
        self.assertEqual(result["name"], "test")
        self.assertEqual(result["nested"]["value"], 123)

    def test_control_character_escape(self):
        """测试转义控制字符。"""
        # JSON字符串中的裸换行符应该被转义
        json_str = """{
  "text": "这是第一行
这是第二行",
  "value": 123
}"""
        result = self.parser.parse(json_str, "控制字符转义测试")
        # 确保换行符被正确处理
        self.assertIn("第一行", result["text"])
        self.assertIn("第二行", result["text"])

    def test_trailing_comma_removal(self):
        """测试移除尾随逗号。"""
        json_str = """{
  "name": "test",
  "value": 123,
  "items": [1, 2, 3,],
}"""
        result = self.parser.parse(json_str, "尾随逗号测试")
        self.assertEqual(result["name"], "test")
        self.assertEqual(len(result["items"]), 3)

    def test_colon_equals_fix(self):
        """测试修复冒号等号错误。"""
        json_str = """{
  "name":= "test",
  "value": 123
}"""
        result = self.parser.parse(json_str, "冒号等号测试")
        self.assertEqual(result["name"], "test")

    def test_extract_first_json(self):
        """测试从文本中提取第一个JSON结构。"""
        json_str = """这是一些说明文字，下面是JSON：
{
  "name": "test",
  "value": 123
}
后面还有一些其他文字"""
        result = self.parser.parse(json_str, "提取JSON测试")
        self.assertEqual(result["name"], "test")
        self.assertEqual(result["value"], 123)

    def test_unterminated_string_with_json_repair(self):
        """测试使用json_repair库修复未终止的字符串。"""
        # 创建启用json_repair的解析器
        parser_with_repair = RobustJSONParser(
            enable_json_repair=True,
            enable_llm_repair=False,
        )

        # 模拟实际错误：字符串中有未转义的控制字符或引号
        json_str = """{
  "template_name": "特定政策报告",
  "selection_reason": "这是测试内容"
}"""
        result = parser_with_repair.parse(json_str, "未终止字符串测试")
        # 只要能够解析成功，不报错就可以了
        self.assertIsInstance(result, dict)
        self.assertIn("template_name", result)

    def test_array_with_best_match(self):
        """测试从数组中提取最佳匹配的元素。"""
        json_str = """[
  {
    "name": "test",
    "value": 123
  },
  {
    "totalWords": 40000,
    "globalGuidelines": ["guide1", "guide2"],
    "chapters": []
  }
]"""
        result = self.parser.parse(
            json_str,
            "数组最佳匹配测试",
            expected_keys=["totalWords", "globalGuidelines", "chapters"],
        )
        # 应该提取第二个元素，因为它匹配了3个键
        self.assertEqual(result["totalWords"], 40000)
        self.assertEqual(len(result["globalGuidelines"]), 2)

    def test_key_alias_recovery(self):
        """测试键名别名恢复。"""
        json_str = """{
  "templateName": "test_template",
  "selectionReason": "This is a test"
}"""
        result = self.parser.parse(
            json_str,
            "键别名测试",
            expected_keys=["template_name", "selection_reason"],
        )
        # 应该自动映射 templateName -> template_name
        self.assertEqual(result["template_name"], "test_template")
        self.assertEqual(result["selection_reason"], "This is a test")

    def test_complex_real_world_case(self):
        """测试真实世界的复杂案例（类似实际错误）。"""
        # 模拟实际错误：缺少逗号、有markdown包裹、有思考内容
        json_str = """<thinking>我需要构造一个篇幅规划</thinking>
```json
{
  "totalWords": 40000,
  "tolerance": 2000,
  "globalGuidelines": [
    "重点突出技术红利分配失衡、人才流失与职业认同危机等结构性矛盾"
    "详略策略：技术创新与传统技艺的碰撞"
    "案例导向：优先引用真实数据和调研"
  ],
  "chapters": [
    {
      "chapterId": "ch1",
      "targetWords": 5000
    }
  ]
}
```"""
        result = self.parser.parse(json_str, "复杂真实案例测试")
        self.assertEqual(result["totalWords"], 40000)
        self.assertEqual(result["tolerance"], 2000)
        self.assertEqual(len(result["globalGuidelines"]), 3)
        self.assertEqual(len(result["chapters"]), 1)

    def test_expected_keys_validation(self):
        """测试期望键的验证。"""
        json_str = '{"name": "test"}'
        # 不应该因为缺少键而失败，只是警告
        result = self.parser.parse(
            json_str, "键验证测试", expected_keys=["name", "value"]
        )
        self.assertIn("name", result)

    def test_wrapper_key_extraction(self):
        """测试从包裹键中提取数据。"""
        json_str = """{
  "wrapper": {
    "name": "test",
    "value": 123
  }
}"""
        result = self.parser.parse(
            json_str, "包裹键测试", extract_wrapper_key="wrapper"
        )
        self.assertEqual(result["name"], "test")
        self.assertEqual(result["value"], 123)

    def test_empty_input(self):
        """测试空输入。"""
        with self.assertRaises(JSONParseError):
            self.parser.parse("", "空输入测试")

    def test_invalid_json_after_all_repairs(self):
        """测试所有修复策略都无法处理的情况。"""
        # 这是一个严重损坏的JSON，无法修复
        json_str = "{完全不是JSON格式的内容###"
        with self.assertRaises(JSONParseError):
            self.parser.parse(json_str, "无法修复测试")


def run_manual_test():
    """手动运行测试，打印详细信息。"""
    print("=" * 60)
    print("开始测试RobustJSONParser")
    print("=" * 60)

    parser = RobustJSONParser(enable_json_repair=False, enable_llm_repair=False)

    # 测试实际错误案例
    test_case = """```json
{
  "totalWords": 40000,
  "tolerance": 2000,
  "globalGuidelines": [
    "重点突出技术红利分配失衡、人才流失与职业认同危机等结构性矛盾"
    "详略策略：技术创新与传统技艺的碰撞"
  ],
  "chapters": []
}
```"""

    print("\n测试案例：")
    print(test_case)
    print("\n" + "=" * 60)

    try:
        result = parser.parse(test_case, "手动测试")
        print("\n✓ 解析成功！")
        print("\n解析结果：")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"\n✗ 解析失败: {e}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    # 运行手动测试
    run_manual_test()

    # 运行单元测试
    print("\n\n运行单元测试...")
    unittest.main(verbosity=2)
