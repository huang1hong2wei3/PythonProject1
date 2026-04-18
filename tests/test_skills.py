import pytest
from skills.weather import get_skill_definition

def test_weather_skill_definition():
    """测试 Skill 定义是否完整（不需要 API Key）"""
    definition = get_skill_definition()
    assert definition["name"] == "get_weather"
    assert "city_name" in definition["parameters"]["properties"]