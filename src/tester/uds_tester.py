# -*- coding: utf-8 -*-
"""
UDS诊断仪封装模块（测试引擎层核心）
把"发请求-等响应-解数据"的重复劳动收敛成简洁API，
让测试用例只关心"发什么、期望什么"
"""
import time  # 用于响应时间测量
import can   # python-can库


class UdsTester:
    """UDS诊断仪：扮演测试中的"诊断仪"角色，与虚拟ECU通信"""

    def __init__(self, channel='vcan0', request_id=0x7E0, timeout=1.0):
        """初始化诊断仪总线连接
        channel:    虚拟总线通道名（必须与ECU在同一通道）
        request_id: 发送请求用的CAN ID
        timeout:    等待响应的超时时间（秒）
        """
        self.request_id = request_id
        self.timeout = timeout
        # 创建总线对象；不接收自己发出的报文
        self.bus = can.interface.Bus(
            interface='virtual', channel=channel, receive_own_messages=False
        )

    def send_request(self, data, can_id=None):
        """发送一帧UDS请求（自动补0x00到8字节）
        data:   有效数据列表，如 [0x03, 0x22, 0xF1, 0x90]
        can_id: 可选，指定其他CAN ID（用于"错误ID"健壮性测试）
        """
        target_id = can_id if can_id is not None else self.request_id  # 默认用请求ID
        padded = list(data) + [0x00] * (8 - len(data))                 # 补满8字节
        msg = can.Message(arbitration_id=target_id,
                          data=padded, is_extended_id=False)
        self.bus.send(msg)

    def recv_response(self):
        """接收一帧响应；超时返回None，否则返回数据列表"""
        msg = self.bus.recv(timeout=self.timeout)
        if msg is None:
            return None
        return list(msg.data)  # 转成list方便切片断言

    def request(self, data, can_id=None):
        """最常用的"一问一答"：发请求并返回响应数据（超时为None）"""
        self.send_request(data, can_id=can_id)
        return self.recv_response()

    def request_timed(self, data):
        """一问一答 + 测量响应耗时；返回 (响应数据, 耗时毫秒)"""
        start = time.perf_counter()          # 高精度计时起点
        self.send_request(data)
        resp = self.recv_response()
        elapsed_ms = (time.perf_counter() - start) * 1000  # 换算成毫秒
        return resp, elapsed_ms

    def close(self):
        """关闭总线，释放资源"""
        self.bus.shutdown()