# 测试设计说明书

## 1. 测试目标

本项目面向汽车电子 UDS（ISO 14229）诊断测试场景，在无真实 ECU、无 CAN 接口卡的条件下，基于 python-can virtual 总线构建纯软件仿真测试环境。

测试目标：

- 验证 VirtualECU 对核心 UDS 服务的响应正确性；
- 验证会话控制与安全访问状态机行为；
- 验证 DID 读写、负响应和异常输入处理；
- 验证 P2 响应时序、通信健壮性和测试状态隔离；
- 使用语句覆盖率与分支覆盖率量化测试充分性。

## 2. 被测对象

被测对象为 src/ecu/virtual_ecu.py 中的 VirtualECU 类。

VirtualECU 模拟一个 UDS 诊断 ECU，具备以下能力：

- 接收 CAN ID 0x7E0 的诊断请求；
- 发送 CAN ID 0x7E8 的诊断响应；
- 支持会话控制、安全访问、DID 读取与 DID 写入；
- 支持 UDS 正响应与标准负响应；
- 支持会话状态、安全锁状态和 DID 数据库。

## 3. 测试环境

| 项目 | 配置 |
|---|---|
| 操作系统 | Windows / Linux / macOS |
| Python | Python 3.10+ |
| CAN 仿真 | python-can virtual interface |
| 测试框架 | pytest |
| 报告工具 | pytest-html |
| 覆盖率工具 | pytest-cov + coverage.py |
| CI | GitHub Actions |
| 物理硬件 | 无需硬件 |

VirtualECU 在后台线程中持续监听 virtual CAN 总线，UdsTester 在测试线程中发送请求并接收响应。

## 4. 测试范围

| 服务 / 类别 | 名称 | 测试重点 |
|---|---|---|
| 0x10 | DiagnosticSessionControl | 默认会话、扩展会话、非法子功能、长度异常、回切默认会话后的安全锁重置 |
| 0x22 | ReadDataByIdentifier | 合法 DID、不存在 DID、DID 边界、请求长度异常、DID 回显与数据一致性 |
| 0x27 | SecurityAccess | 会话门槛、请求种子、正确密钥、错误密钥、密钥边界、长度异常 |
| 0x2E | WriteDataByIdentifier | 会话保护、安全保护、可写 DID、只读 DID、不存在 DID、写后回读 |
| 未支持服务 | ServiceNotSupported | 未实现 SID 的 NRC 0x11 负响应 |
| P2 时序 | Response Timing | 单服务响应时间、完整安全解锁流程耗时 |
| 健壮性 | Robustness | 畸形帧、错误 CAN ID、连续请求、状态隔离 |

## 5. 测试设计方法

### 5.1 等价类划分

输入按合法与非法类别划分：

- 合法 DID 与不存在 DID；
- 可写 DID 与只读 DID；
- 合法 SID 与未支持 SID；
- 合法子功能与非法子功能；
- 正确密钥与错误密钥；
- 合法长度与非法长度。

### 5.2 边界值分析

重点覆盖以下边界：

- DID：0x0000、0x0001、0xFFFF；
- 正确密钥邻近值：0x5A48、0x5A49、0x5A4A；
- 请求长度字段的合法值及相邻错误值；
- 空帧、短帧和异常长度帧；
- 连续 20 次请求的稳定性场景。

### 5.3 状态迁移测试

    默认会话
        │
        │ 0x10 03
        ▼
    扩展会话 / 安全锁定
        │
        │ 0x27 请求种子 + 发送正确密钥
        ▼
    扩展会话 / 安全解锁
        │
        │ 0x10 01
        ▼
    默认会话 / 安全锁定

状态迁移覆盖：

1. 默认会话下读取 DID；
2. 默认会话下写 DID 被拒绝；
3. 扩展会话但未解锁时写 DID 被拒绝；
4. 错误密钥导致安全访问失败；
5. 正确密钥完成安全解锁；
6. 解锁后写 DID 成功；
7. 写后回读验证数据；
8. 切回默认会话后权限失效。

### 5.4 错误猜测法

覆盖以下常见异常输入：

- CAN 数据场不足 SID 长度；
- 发送到错误 CAN ID；
- 未支持 SID；
- 不存在 DID；
- 只读 DID 写入；
- 错误密钥；
- 会话未切换直接写入；
- 连续高频请求；
- DID 数据状态泄漏。

## 6. 测试矩阵

| 测试文件 | 用例数 | 测试内容 |
|---|:---:|---|
| test_session_control.py | 13 | 0x10 会话控制、非法子功能、长度错误、回切重锁 |
| test_read_data.py | 16 | 0x22 DID 读取、非法 DID、边界 DID、长度错误 |
| test_security_access.py | 17 | 0x27 会话门槛、种子、密钥、边界密钥、长度错误 |
| test_write_data.py | 10 | 0x2E 会话保护、安全保护、只读 DID、写读闭环 |
| test_unsupported_service.py | 19 | 未支持 SID 的 NRC 0x11 负响应 |
| test_timing.py | 5 | P2 时序与完整安全解锁流程时序 |
| test_robustness.py | 5 | 畸形帧、错误 ID、连续请求、状态隔离 |
| **合计** | **85** | **UDS 服务、异常响应、时序与健壮性测试** |

## 7. NRC 覆盖矩阵

| NRC | 含义 | 覆盖场景 |
|---|---|---|
| 0x11 | ServiceNotSupported | 请求未实现 SID |
| 0x12 | SubFunctionNotSupported | 非法会话控制或安全访问子功能 |
| 0x13 | IncorrectMessageLength | 请求、种子请求或密钥请求长度异常 |
| 0x31 | RequestOutOfRange | DID 不存在或写入只读 DID |
| 0x33 | SecurityAccessDenied | 未解锁执行写数据服务 |
| 0x35 | InvalidKey | 发送错误安全密钥 |
| 0x7F | ServiceNotSupportedInActiveSession | 默认会话下执行受保护服务 |

## 8. 测试隔离策略

pytest fixture 为每个测试用例创建独立环境：

    创建全新 VirtualECU
        ↓
    启动 ECU 后台线程
        ↓
    创建 UdsTester 诊断仪
        ↓
    执行测试用例
        ↓
    停止 ECU 主循环
        ↓
    等待线程退出
        ↓
    关闭 ECU 总线与诊断仪总线

通过“写入脏数据 → 新测试用例验证出厂 DID 数据”的组合用例，验证 fixture 隔离机制有效，避免会话状态、安全状态和 DID 数据泄漏。

## 9. 覆盖率策略

覆盖率统计范围为 src 下的生产代码：

- src/ecu/virtual_ecu.py；
- src/tester/uds_tester.py。

.coveragerc 中启用：

    [run]
    source = src
    concurrency = thread
    branch = true

concurrency = thread 用于追踪 ECU 后台线程代码。若缺失该配置，线程执行路径可能出现覆盖率假阴性。

| 文件 | 语句覆盖率 | 分支覆盖率 |
|---|:---:|:---:|
| virtual_ecu.py | 100% | 100% |
| uds_tester.py | 100% | 100% |
| **合计** | **100%** | **100%** |

## 10. 覆盖率闭环记录

覆盖率报告曾发现 virtual_ecu.py 中“请求种子时长度错误”的分支未覆盖。

    覆盖率报告定位未覆盖行
        ↓
    分析对应逻辑：0x27 请求种子长度校验
        ↓
    新增长度错误负向测试
        ↓
    断言返回 NRC 0x13
        ↓
    重新执行完整测试
        ↓
    语句覆盖率与分支覆盖率达到 100%

## 11. 已知测试边界

以下内容暂不属于当前测试范围：

1. ISO-TP 多帧传输；
2. 17 字节完整 VIN 的多帧读写；
3. Bus-off、ACK 错误、位错误和波特率失配；
4. 真实 CAN 接口卡与实体 ECU；
5. Flash、NVM 和 EEPROM 持久化行为；
6. 多诊断仪并发访问；
7. 长时间稳定性与资源泄漏测试；
8. 真实 ECU 随机种子与安全算法。