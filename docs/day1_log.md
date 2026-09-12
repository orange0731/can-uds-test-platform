# Day 1 学习日志（日期：今天）

## 今天跑通了什么
- 搭建虚拟环境，安装 python-can / cantools / pytest
- 用 virtual 接口跑通 CAN 虚拟总线收发
- 实现 UDS "读VIN码"一问一答完整闭环（0x22 请求 → 0x62 正响应）

## 踩过的坑
- 【坑1：忘记 shutdown() 导致 VirtualBus 警告】
- 【坑2： PowerShell 重定向生成的 requirements.txt 编码问题】

## 学到的知识点
- 正响应 = SID + 0x40；负响应 = 0x7F + SID + NRC

## 明天计划
- 开始 Day 2：面向对象虚拟 ECU + SID 分发 + 负响应
