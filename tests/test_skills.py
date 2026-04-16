mport pytest
from skills.weather import execute, get_skill_definition

def test_weather_skill_definition():
    """测试 Skill 定义是否完整"""
    definition = get_skill_definition()
    assert definition["name"] == "get_weather"
    assert "city_name" in definition["parameters"]["properties"]

def test_weather_execute_invalid_city():
    """测试查询无效城市"""
    result = execute("不存在的城市名字123456")
    # 应该返回错误信息（包含“失败”或“错误”）
    assert ("失败" in result) or ("错误" in result)