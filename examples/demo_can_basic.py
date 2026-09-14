# -*- coding: utf-8 -*-
"""虚拟CAN总线基本收发示例"""
import can  # 导入python-can库，它是Python操作CAN总线的标准库

# 创建发送方总线对象：interface='virtual' 表示纯软件模拟总线，无需任何硬件
# channel='vcan0' 是虚拟通道名，同一进程内同通道的总线互相可见
bus_sender = can.interface.Bus(interface='virtual', channel='vcan0')

# 创建接收方总线对象（模拟总线上的另一个节点，即"ECU"）
bus_receiver = can.interface.Bus(interface='virtual', channel='vcan0')

# 构造一帧标准CAN报文：
# arbitration_id=0x123  -> CAN帧的ID（标准帧11位）
# data=[...]            -> 数据场，最多8字节（经典CAN）
# is_extended_id=False  -> 使用标准帧而非29位扩展帧
msg = can.Message(
    arbitration_id=0x123,
    data=[0x11, 0x22, 0x33, 0x44],
    is_extended_id=False
)

# 将报文发送到总线上
bus_sender.send(msg)
print(f"已发送: {msg}")

# 接收方从总线读取一帧报文，timeout=1.0 表示最多等1秒，超时返回None
received = bus_receiver.recv(timeout=1.0)

# 校验并打印
if received is not None:
    print(f"已接收: ID={hex(received.arbitration_id)}, 数据={received.data.hex()}")
else:
    print("接收超时！")
# 程序结束前显式关闭总线，释放资源（好习惯，正式代码中必须这样做）
bus_sender.shutdown()    # 关闭发送方总线
bus_receiver.shutdown()  # 关闭接收方总线