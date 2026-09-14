# Day 4-6 学习日志

## 跑通了什么
- Day4: 诊断仪封装UdsTester + conftest夹具（用例自动隔离）+ pytest迁移
- Day5: parametrize批量扩充到68条（含0x5A49±1边界值密钥）
- Day6: P2时序测试 + 畸形帧/错误ID/压力测试，全量82条全绿

## 学到的知识点
- fixture的Setup/Teardown机制：yield前后分别执行
- parametrize一个装饰器=N条用例，是用例量产的核心手段
- 写后回读、状态隔离组合拳等用例设计技巧
- P2时间是ISO 14229规定的ECU响应性能指标

## 下一步
- Day7: pytest-html生成专业HTML测试报告 + 覆盖率统计
