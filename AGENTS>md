# 项目：AI 对话机器人 (FastAPI + DeepSeek)

## 技术栈
- Python 3.9+
- FastAPI
- SQLite（本地开发）
- DeepSeek API

## 代码风格
- 使用 4 空格缩进
- 函数命名：snake_case
- 类命名：PascalCase
- 常量命名：UPPER_SNAKE_CASE

## 架构约束
- 所有 API 路由必须定义在 `main.py`
- 数据库操作统一放在 `db.py`（如果后续拆分）
- 环境变量通过 `os.getenv` 读取，禁止硬编码

## 测试要求
- 核心函数（如 `save_message`, `get_history`）必须有单元测试
- 测试文件放在 `tests/` 目录

## Git 提交规范
- 格式：`<type>: <subject>`
- type 可选：feat, fix, docs, style, refactor, test, chore

## AI 辅助规则
- 生成代码时必须包含类型注解
- 复杂逻辑需要添加注释说明
- 禁止生成未使用的导入
