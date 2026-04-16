"""
天气查询 Skill
符合 Harness Engineering 的标准化工具封装规范
"""

import os
import requests
from typing import Dict, Any

# Skill 元数据（供 AI 发现和调用）
SKILL_NAME = "get_weather"
SKILL_DESCRIPTION = "获取指定城市的当前天气和温度"
SKILL_PARAMETERS = {
    "type": "object",
    "properties": {
        "city_name": {
            "type": "string",
            "description": "城市名，例如：北京、上海、London"
        }
    },
    "required": ["city_name"]
}


def execute(city_name: str) -> str:
    """
    执行天气查询

    Args:
        city_name: 城市名称（支持中文或英文）

    Returns:
        格式化的天气信息字符串
    """
    # 注意：需要设置环境变量 OPENWEATHER_API_KEY
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        return "错误：未设置 OPENWEATHER_API_KEY 环境变量"

    url = f"http://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={api_key}&units=metric&lang=zh_cn"

    try:
        response = requests.get(url, timeout=10)
        data = response.json()

        if response.status_code == 200:
            temp = data['main']['temp']
            weather = data['weather'][0]['description']
            return f"{city_name}，温度 {temp}°C，天气 {weather}"
        else:
            return f"查询失败：{data.get('message', '未知错误')}"
    except Exception as e:
        return f"网络错误：{str(e)}"


def get_skill_definition() -> Dict[str, Any]:
    """返回 Skill 的 OpenAI/DeepSeek 函数调用格式定义"""
    return {
        "name": SKILL_NAME,
        "description": SKILL_DESCRIPTION,
        "parameters": SKILL_PARAMETERS
    }