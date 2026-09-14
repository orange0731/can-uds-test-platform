# -*- coding: utf-8 -*-
"""
状态机验证脚本：模拟真实诊断仪的完整工作流程
默认会话 → 切扩展会话 → 安全解锁 → 写数据 → 回读验证 → 切回默认会话
共11个检查点，覆盖状态机的每个分支
"""
import threading  # 线程库：ECU主循环需后台运行
import time       # 启动延时
import can        # python-can库

from src.ecu.virtual_ecu import VirtualECU

TESTER_ID = 0x7E0  # 诊断仪请求CAN ID

# 统计通过/失败数量，最后出总结
_pass_count = 0
_fail_count = 0


def ask(tester_bus, request_data, expected_head, case_name):
    """发送诊断请求并校验响应前N字节，返回响应帧（供提取种子等数据用）"""
    global _pass_count, _fail_count
    req = can.Message(arbitration_id=TESTER_ID,
                      data=request_data, is_extended_id=False)
    tester_bus.send(req)                        # 发送请求
    resp = tester_bus.recv(timeout=1.0)         # 等待响应
    if resp is None:
        print(f"{case_name}: ❌ 超时无响应")
        _fail_count += 1
        return None
    actual = list(resp.data[:len(expected_head)])  # 截取前N字节比较
    if actual == expected_head:
        print(f"{case_name}: ✅ 通过")
        _pass_count += 1
    else:
        print(f"{case_name}: ❌ 失败  期望={expected_head} 实际={actual}")
        _fail_count += 1
    return resp  # 返回完整响应帧，调用方可进一步提取数据


def main():
    # ---------- 启动ECU（后台线程） ----------
    ecu = VirtualECU(channel='vcan0')
    ecu_thread = threading.Thread(target=ecu.start, daemon=True)
    ecu_thread.start()
    time.sleep(0.2)

    # ---------- 诊断仪接入总线 ----------
    tester_bus = can.interface.Bus(
        interface='virtual', channel='vcan0', receive_own_messages=False
    )

    print("=" * 50)
    print("阶段A：默认会话下的写保护")
    print("=" * 50)
    # 检查点1：默认会话下直接写VIN → 应被拒绝 NRC 0x7F（当前会话不支持）
    ask(tester_bus, [0x07, 0x2E, 0xF1, 0x90, 0xAA, 0xBB, 0xCC, 0xDD],
        [0x03, 0x7F, 0x2E, 0x7F], "检查点1 默认会话写数据-NRC0x7F")

    print("=" * 50)
    print("阶段B：切换扩展会话，但未解锁")
    print("=" * 50)
    # 检查点2：切换到扩展会话 → 正响应 0x50 0x03
    ask(tester_bus, [0x02, 0x10, 0x03, 0, 0, 0, 0, 0],
        [0x06, 0x50, 0x03], "检查点2 切扩展会话-正响应")

    # 检查点3：扩展会话但未解锁就写数据 → 经典场景 NRC 0x33！
    ask(tester_bus, [0x07, 0x2E, 0xF1, 0x90, 0xAA, 0xBB, 0xCC, 0xDD],
        [0x03, 0x7F, 0x2E, 0x33], "检查点3 未解锁写数据-NRC0x33")

    print("=" * 50)
    print("阶段C：安全访问（种子&密钥挑战）")
    print("=" * 50)
    # 检查点4：请求种子 → 正响应 0x67 0x01 + 种子
    resp = ask(tester_bus, [0x02, 0x27, 0x01, 0, 0, 0, 0, 0],
               [0x04, 0x67, 0x01], "检查点4 请求种子-正响应")
    # 从响应中提取种子：帧格式 [长度,0x67,0x01,种子高字节,种子低字节,...]
    seed = (resp.data[3] << 8) | resp.data[4]
    print(f"       >>> 提取到种子: 0x{seed:04X}")

    # 检查点5：故意发送错误密钥 → NRC 0x35（密钥错误）
    ask(tester_bus, [0x04, 0x27, 0x02, 0x00, 0x00, 0, 0, 0],
        [0x03, 0x7F, 0x27, 0x35], "检查点5 错误密钥-NRC0x35")

    # 检查点6：按约定算法计算正确密钥 = 种子 XOR 0xFFFF，发送 → 解锁成功
    key = seed ^ 0xFFFF
    print(f"       >>> 计算出密钥: 0x{key:04X}")
    ask(tester_bus, [0x04, 0x27, 0x02, (key >> 8) & 0xFF, key & 0xFF, 0, 0, 0],
        [0x02, 0x67, 0x02], "检查点6 正确密钥-解锁成功")

    print("=" * 50)
    print("阶段D：解锁后的写读闭环")
    print("=" * 50)
    # 检查点7：解锁后写入新VIN数据"WP02"(0x57 0x50 0x30 0x32) → 正响应 0x6E
    ask(tester_bus, [0x07, 0x2E, 0xF1, 0x90, 0x57, 0x50, 0x30, 0x32],
        [0x03, 0x6E, 0xF1, 0x90], "检查点7 解锁后写VIN-正响应")

    # 检查点8：回读VIN → 应读到刚写入的新数据（证明写入真正生效！）
    ask(tester_bus, [0x03, 0x22, 0xF1, 0x90, 0, 0, 0, 0],
        [0x07, 0x62, 0xF1, 0x90, 0x57, 0x50, 0x30, 0x32],
        "检查点8 回读新数据-验证写入")

    # 检查点9：尝试改写只读DID 0xF187(软件版本) → NRC 0x31（不可写）
    ask(tester_bus, [0x07, 0x2E, 0xF1, 0x87, 0x01, 0x02, 0x03, 0x04],
        [0x03, 0x7F, 0x2E, 0x31], "检查点9 写只读DID-NRC0x31")

    print("=" * 50)
    print("阶段E：切回默认会话，权限应失效")
    print("=" * 50)
    # 检查点10：切回默认会话 → 正响应 0x50 0x01
    ask(tester_bus, [0x02, 0x10, 0x01, 0, 0, 0, 0, 0],
        [0x06, 0x50, 0x01], "检查点10 切回默认会话")

    # 检查点11：默认会话下再写 → 又被拒绝 NRC 0x7F（证明安全锁已自动重置）
    ask(tester_bus, [0x07, 0x2E, 0xF1, 0x90, 0x11, 0x22, 0x33, 0x44],
        [0x03, 0x7F, 0x2E, 0x7F], "检查点11 切回后写数据-权限失效")

    # ---------- 测试总结 ----------
    print("=" * 50)
    print(f"测试完成: {_pass_count} 通过, {_fail_count} 失败")
    print("=" * 50)

    # ---------- 优雅关闭 ----------
    ecu.stop()
    ecu_thread.join(timeout=1.0)
    ecu.shutdown()
    tester_bus.shutdown()


if __name__ == '__main__':
    main()