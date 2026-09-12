# CAN/UDS 诊断自动化测试平台

基于 python-can 与虚拟 CAN 总线搭建的 UDS（ISO 14229）诊断自动化测试平台。

## 项目状态
🚧 开发中 - Day 1：环境搭建与基础通信 Demo

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