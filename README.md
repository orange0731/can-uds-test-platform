# CAN/UDS 诊断自动化测试平台
![UDS自动化测试](https://github.com/orange0731/can-uds-test-platform/actions/workflows/ci.yml/badge.svg)
基于 python-can 与虚拟 CAN 总线搭建的 UDS（ISO 14229）诊断自动化测试平台。

## 项目状态
🚧 开发中 - Day 1：环境搭建与基础通信 Demo
✅ Day 7：自动化测试体系完成
✅ Day 8：CI/CD 流水线已上线——每次 push 自动运行 82 条测试

## 测试结果
- ✅ 自动化用例：**82 条全部通过**（pytest + parametrize 参数化）
- 📊 代码覆盖率：语句覆盖率 __%，分支覆盖率 __%（pytest-cov）
- 📄 测试报告：`reports/uds_test_report.html`（pytest-html 自动生成）
- 🎯 覆盖服务：0x10 会话控制 / 0x22 读数据 / 0x27 安全访问 / 0x2E 写数据

## 技术栈
- Python + python-can（CAN 总线通信）
- pytest + pytest-html（自动化测试与报告）
- cantools（DBC 信号解析）

## 目录结构
- `src/ecu/` —— 虚拟 ECU（被测对象）
- `src/tester/` —— 诊断测试引擎
- `tests/` —— pytest 自动化测试用例
- `docs/` —— UDS 协议学习笔记
- `reports/` —— 测试报告输出