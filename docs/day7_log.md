# Day 7 学习日志

## 跑通了什么
- pytest-html生成单文件中文定制测试报告（82条全绿）
- pytest-cov统计语句/分支覆盖率，virtual_ecu.py达90%+
- pytest.ini配置addopts实现"一条命令全自动"

## 踩过的坑
- coverage.py默认只追踪主线程，ECU在子线程 → 必须配concurrency=thread
- demo文件拉低覆盖率 → .coveragerc中用omit排除
- 【自己补充一条】

## 学到的知识点
- 语句覆盖率 vs 分支覆盖率的区别
- 覆盖率是"测试充分性"的度量，是测试报告的核心指标
- 【自己补充一条】

## 明天计划
- Day8: GitHub Actions CI/CD流水线（或DBC信号测试）
