# -*- coding: utf-8 -*-
"""UDS 诊断仪封装模块（测试引擎层）。

将"请求发送-响应接收-耗时测量"封装为统一 API，
使测试用例仅关注输入与预期，与底层总线细节解耦。
"""
import time
from typing import Optional

import can


class UdsTester:
    """UDS 诊断仪模拟器，作为测试中的请求方与虚拟 ECU 通信。"""

    def __init__(self, channel: str = 'vcan0', request_id: int = 0x7E0,
                 timeout: float = 1.0) -> None:
        """初始化诊断仪总线连接。

        Args:
            channel: 虚拟总线通道名，须与被测 ECU 一致。
            request_id: 诊断请求使用的 CAN ID。
            timeout: 响应等待超时时间，单位秒。
        """
        self.request_id = request_id
        self.timeout = timeout
        self.bus = can.interface.Bus(
            interface='virtual', channel=channel, receive_own_messages=False
        )

    def send_request(self, data: list, can_id: Optional[int] = None) -> None:
        """发送一帧 UDS 请求，数据不足 8 字节时自动补 0x00。

        Args:
            data: 有效数据字节列表，如 [0x03, 0x22, 0xF1, 0x90]。
            can_id: 可选的目标 CAN ID，用于"错误 ID 不响应"类健壮性测试。
        """
        target_id = can_id if can_id is not None else self.request_id
        padded = list(data) + [0x00] * (8 - len(data))
        msg = can.Message(arbitration_id=target_id,
                          data=padded, is_extended_id=False)
        self.bus.send(msg)

    def recv_response(self) -> Optional[list]:
        """接收一帧响应；超时未收到返回 None。"""
        msg = self.bus.recv(timeout=self.timeout)
        return list(msg.data) if msg is not None else None

    def request(self, data: list, can_id: Optional[int] = None) -> Optional[list]:
        """执行一次"请求-响应"交互。"""
        self.send_request(data, can_id=can_id)
        return self.recv_response()

    def request_timed(self, data: list) -> tuple:
        """执行一次交互并测量响应耗时，返回 (响应数据, 耗时毫秒数)。"""
        start = time.perf_counter()
        self.send_request(data)
        resp = self.recv_response()
        elapsed_ms = (time.perf_counter() - start) * 1000
        return resp, elapsed_ms

    def close(self) -> None:
        """关闭总线并释放资源。"""
        self.bus.shutdown()