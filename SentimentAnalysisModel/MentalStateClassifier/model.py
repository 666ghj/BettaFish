# 伪代码示例：使用LLM进行零样本分类的简单思路
import requests
import json

class MentalStateClassifier:
    def __init__(self, api_key, base_url):
        self.api_key = api_key
        self.base_url = base_url
        
    def predict(self, text):
        # 1. 构建一个清晰的提示词(Prompt)
        prompt = f"""
        请分析以下文本所反映的主要社会心态，并从以下五个选项中选出最匹配的一项：焦虑、迷茫、希望、绝望、躺平。
        文本："{text}"
        只输出心态类别，不要有其他解释。
        """
        
        # 2. 调用你配置好的LLM API（确保在.env文件中已配置）
        # 这里假设使用与InsightEngine相同的Kimi等模型
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        data = {
            "model": "kimi-k2", # 替换成你的模型名
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1 # 低随机性，保证输出稳定
        }
        response = requests.post(f"{self.base_url}/chat/completions", json=data, headers=headers)
        result = response.json()
        
        # 3. 解析返回结果
        predicted_state = result["choices"][0]["message"]["content"].strip()
        return predicted_state