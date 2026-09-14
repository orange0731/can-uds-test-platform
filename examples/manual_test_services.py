# -*- coding: utf-8 -*-
"""
手动验证脚本：扮演诊断仪，对虚拟ECU发起4组诊断测试
覆盖：1个正响应用例 + 3个负响应用例（这就是将来pytest用例的雏形）
"""
import threading  # 线程库：ECU主循环是阻塞的，必须放到后台线程跑
import time       # 用于启动延时
import can        # python-can库

from src.ecu.virtual_ecu import VirtualECU  # 从包中导入我们的虚拟ECU类

TESTER_ID = 0x7E0  # 诊断仪请求CAN ID


def ask(tester_bus, request_data, expected_head, case_name):
    """发送一帧诊断请求，并校验响应的前几个字节是否符合预期
    request_data:  请求帧数据（8字节列表）
    expected_head: 期望响应的前N个字节（后面的填充字节不关心）
    case_name:     用例名称（用于打印）
    """
    # 构造并发送请求帧
    req = can.Message(arbitration_id=TESTER_ID,
                      data=request_data, is_extended_id=False)
    tester_bus.send(req)

    # 等待ECU响应，最多1秒
    resp = tester_bus.recv(timeout=1.0)
    if resp is None:
        print(f"{case_name}: ❌ 超时无响应")
        return

    # 只取响应的前 len(expected_head) 个字节与期望值比较
    actual = list(resp.data[:len(expected_head)])
    if actual == expected_head:
        print(f"{case_name}: ✅ 通过  响应={resp.data.hex()}")
    else:
        print(f"{case_name}: ❌ 失败  期望={expected_head} 实际={actual}")


def main():
    # ---------- 第1步：在后台线程中启动ECU ----------
    # virtual总线只在同一进程内互通，所以ECU和Tester必须共处一个进程，用线程隔离
    ecu = VirtualECU(channel='vcan0')
    ecu_thread = threading.Thread(target=ecu.start, daemon=True)  # daemon=True: 主线程退出时自动回收
    ecu_thread.start()
    time.sleep(0.2)  # 给ECU一点启动时间

    # ---------- 第2步：创建诊断仪的总线连接 ----------
    tester_bus = can.interface.Bus(
        interface='virtual', channel='vcan0', receive_own_messages=False
    )

    # ---------- 第3步：执行4组测试 ----------
    # 用例1【正响应】：读取存在的DID 0xF190（VIN），期望 0x62 + DID + "LSV1"
    ask(tester_bus,
        [0x03, 0x22, 0xF1, 0x90, 0, 0, 0, 0],
        [0x07, 0x62, 0xF1, 0x90, 0x4C, 0x53, 0x56, 0x31],
        "用例1 读取VIN-正响应")

    # 用例2【负响应】：读取不存在的DID 0x9999，期望 NRC 0x31（请求超范围）
    ask(tester_bus,
        [0x03, 0x22, 0x99, 0x99, 0, 0, 0, 0],
        [0x03, 0x7F, 0x22, 0x31],
        "用例2 DID不存在-NRC0x31")

    # 用例3【负响应】：请求不认识的服务0x99，期望 NRC 0x11（服务不支持）
    ask(tester_bus,
        [0x02, 0x99, 0x00, 0, 0, 0, 0, 0],
        [0x03, 0x7F, 0x99, 0x11],
        "用例3 非法服务-NRC0x11")

    # 用例4【负响应】：0x22服务但长度只有2，期望 NRC 0x13（长度错误）
    ask(tester_bus,
        [0x02, 0x22, 0xF1, 0, 0, 0, 0, 0],
        [0x03, 0x7F, 0x22, 0x13],
        "用例4 长度错误-NRC0x13")

    # ---------- 第4步：优雅关闭（先停循环，再关总线，顺序不能反） ----------
    ecu.stop()                      # 通知ECU主循环退出
    ecu_thread.join(timeout=1.0)    # 等待线程真正结束
    ecu.shutdown()                  # 关闭ECU总线
    tester_bus.shutdown()           # 关闭诊断仪总线
    print("测试结束，资源已释放")


if __name__ == '__main__':
    main()  # 只有直接运行本文件时才执行main()（被import时不执行）