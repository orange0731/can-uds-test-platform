# -*- coding: utf-8 -*-
"""
虚拟ECU模块（第2周核心组件）
模拟一个支持UDS（ISO 14229）诊断服务的真实ECU：
- 持续监听CAN总线上的诊断请求
- 根据SID（服务ID）分发到对应的处理函数
- 对非法请求回复标准负响应（格式：0x7F + SID + NRC）
"""

import can  # python-can库，负责CAN总线通信


class VirtualECU:
    """虚拟ECU：本项目的被测对象（DUT, Device Under Test）"""

    # ---------- NRC负响应码常量（ISO 14229标准定义，类属性相当于枚举） ----------
    NRC_SERVICE_NOT_SUPPORTED = 0x11   # 服务不支持
    NRC_INCORRECT_LENGTH = 0x13        # 报文长度错误
    NRC_REQUEST_OUT_OF_RANGE = 0x31    # 请求超出范围（如DID不存在）

    def __init__(self, channel='vcan0', request_id=0x7E0, response_id=0x7E8):
        """初始化ECU：建立总线连接、准备内部数据"""
        self.request_id = request_id    # 诊断请求CAN ID（只听这个ID）
        self.response_id = response_id  # 诊断响应CAN ID

        # 创建总线对象；receive_own_messages=False 表示不接收自己发出的报文
        self.bus = can.interface.Bus(
            interface='virtual', channel=channel, receive_own_messages=False
        )

        # DID数据库（模拟ECU内部存储区）：键=DID编号，值=数据字节列表
        # 注意：单帧最多装"2字节DID + 4字节数据"，更长的数据需要ISO-TP多帧（后续阶段实现）
        self.did_table = {
            0xF190: [0x4C, 0x53, 0x56, 0x31],  # VIN码片段"LSV1"（真实VIN为17字节，此处简化）
            0xF18C: [0x20, 0x24, 0x01, 0x01],  # ECU序列号
            0xF187: [0x01, 0x00, 0x02, 0x0A],  # 软件版本号 1.0.2.10
        }

        # 服务分发表：SID → 处理函数（新增服务时只需在此注册一行）
        self.service_handlers = {
            0x22: self._handle_read_data_by_identifier,  # 读数据服务
        }

        self._running = False  # 主循环运行标志（用于优雅退出）

    # ==================== 主循环 ====================
    def start(self):
        """启动ECU：持续监听总线（阻塞循环，需在独立线程中运行）"""
        self._running = True
        print("[ECU] 已启动，开始监听总线...")
        while self._running:
            # 从总线读一帧，最多等0.1秒（超时是为了能定期检查退出标志）
            msg = self.bus.recv(timeout=0.1)
            if msg is None:
                continue                          # 超时无报文，继续下一轮
            if msg.arbitration_id != self.request_id:
                continue                          # 不是发给我的诊断请求，忽略
            self._handle_request(msg)             # 交给分发器处理

    def stop(self):
        """通知主循环退出（只改标志位，循环会在0.1秒内自然结束）"""
        self._running = False

    def shutdown(self):
        """关闭总线，释放资源（应在主循环退出后调用）"""
        self.bus.shutdown()

    # ==================== 请求分发 ====================
    def _handle_request(self, msg):
        """解析请求帧，按SID分发到对应服务处理函数"""
        if len(msg.data) < 2:
            return  # 帧长度连"长度+SID"都不够，是畸形帧，直接忽略

        length = msg.data[0]  # 第0字节：有效数据长度（简化版ISO-TP单帧PCI）
        sid = msg.data[1]     # 第1字节：服务ID
        print(f"[ECU] 收到请求: SID=0x{sid:02X}")

        # 查分发表，获取该SID对应的处理函数
        handler = self.service_handlers.get(sid)
        if handler is None:
            # 不认识的服务 → 回复负响应 NRC 0x11（服务不支持）
            self._send_negative_response(sid, self.NRC_SERVICE_NOT_SUPPORTED)
            return
        handler(msg.data, length)  # 交给具体服务处理

    # ==================== 0x22 读数据服务 ====================
    def _handle_read_data_by_identifier(self, data, length):
        """处理 ReadDataByIdentifier 服务：按DID读取ECU内部数据"""
        # 校验1：请求长度必须是3（1字节SID + 2字节DID）
        if length != 0x03:
            self._send_negative_response(0x22, self.NRC_INCORRECT_LENGTH)
            return

        # 拼接出16位DID：第2字节左移8位（高字节）| 第3字节（低字节）
        did = (data[2] << 8) | data[3]

        # 校验2：DID必须存在于数据库中
        if did not in self.did_table:
            self._send_negative_response(0x22, self.NRC_REQUEST_OUT_OF_RANGE)
            return

        # 构造正响应负载：DID回显（2字节）+ 数据内容
        payload = [data[2], data[3]] + self.did_table[did]
        self._send_positive_response(0x22, payload)

    # ==================== 响应发送 ====================
    def _send_positive_response(self, sid, payload):
        """发送正响应：响应SID = 请求SID + 0x40（ISO 14229铁律）"""
        resp_sid = sid + 0x40
        # 组帧：[长度, 响应SID, 负载...]，不足8字节补0x00
        frame = [1 + len(payload), resp_sid] + payload
        frame = frame + [0x00] * (8 - len(frame))
        msg = can.Message(arbitration_id=self.response_id,
                          data=frame, is_extended_id=False)
        self.bus.send(msg)
        print(f"[ECU] 发送正响应: SID=0x{resp_sid:02X}")

    def _send_negative_response(self, sid, nrc):
        """发送负响应：固定格式 0x7F + 原SID + NRC"""
        frame = [0x03, 0x7F, sid, nrc, 0x00, 0x00, 0x00, 0x00]
        msg = can.Message(arbitration_id=self.response_id,
                          data=frame, is_extended_id=False)
        self.bus.send(msg)
        print(f"[ECU] 发送负响应: SID=0x{sid:02X}, NRC=0x{nrc:02X}")