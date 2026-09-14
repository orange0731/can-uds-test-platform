# -*- coding: utf-8 -*-
"""UDS诊断问答最小示例（读取VIN码）"""
import can  # 导入python-can库

TESTER_ID = 0x7E0  # 诊断仪请求的CAN ID（行业标准约定）
ECU_ID = 0x7E8     # ECU响应的CAN ID（= 请求ID + 8，行业标准约定）

# 诊断仪和ECU各持有一个总线对象，挂在同一虚拟通道上
bus_tester = can.interface.Bus(interface='virtual', channel='vcan0')
bus_ecu = can.interface.Bus(interface='virtual', channel='vcan0')

# ---------- 第1步：诊断仪发送请求 ----------
# 数据格式(简化版ISO-TP单帧): [长度, SID, DID高字节, DID低字节, 填充...]
# 0x03 = 后续有效字节数；0x22 = 读数据服务；0xF190 = VIN码的DID编号
request = can.Message(
    arbitration_id=TESTER_ID,
    data=[0x03, 0x22, 0xF1, 0x90, 0x00, 0x00, 0x00, 0x00],
    is_extended_id=False
)
bus_tester.send(request)  # 发送请求帧
print(f"[Tester] 发送请求: {request.data.hex()}")

# ---------- 第2步：ECU接收并解析 ----------
req = bus_ecu.recv(timeout=1.0)      # ECU阻塞等待请求，1秒超时
sid = req.data[1]                    # 取出服务ID，应为0x22
did = (req.data[2] << 8) | req.data[3]  # 拼接出16位DID，应为0xF190
print(f"[ECU] 收到请求: SID={hex(sid)}, DID={hex(did)}")

# ---------- 第3步：ECU构造并发送正响应 ----------
# 正响应SID = 0x22 + 0x40 = 0x62；后面回传DID + 数据（此处用0x41 0x42模拟VIN片段）
response = can.Message(
    arbitration_id=ECU_ID,
    data=[0x05, 0x62, 0xF1, 0x90, 0x41, 0x42, 0x00, 0x00],
    is_extended_id=False
)
bus_ecu.send(response)  # ECU发出响应帧
print(f"[ECU] 发送响应: {response.data.hex()}")

# ---------- 第4步：诊断仪接收并验证 ----------
resp = bus_tester.recv(timeout=1.0)  # 诊断仪等待响应
if resp is not None and resp.data[1] == 0x62:  # 0x62 = 0x22的正响应SID
    print(f"[Tester] ✅ 收到正响应，DID={hex(resp.data[2]<<8 | resp.data[3])}，测试通过！")
else:
    print("[Tester] ❌ 响应异常")
bus_tester.shutdown()    # 关闭发送方总线
bus_ecu.shutdown()  # 关闭接收方总线