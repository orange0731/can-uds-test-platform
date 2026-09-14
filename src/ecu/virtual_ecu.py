
# -*- coding: utf-8 -*-

"""
虚拟ECU模块（第2周核心组件）
模拟一个支持UDS（ISO 14229）诊断服务的真实ECU：
- 持续监听CAN总线上的诊断请求
- 根据SID（服务ID）分发到对应的处理函数
- 对非法请求回复标准负响应（格式：0x7F + SID + NRC）
"""
'''
import logging  # 标准日志模块：输出可分级、可静默

import can

logger = logging.getLogger(__name__)  # 当前模块日志器  # python-can库，负责CAN总线通信


class VirtualECU:
    """虚拟ECU：本项目的被测对象（DUT, Device Under Test）"""

    # ---------- NRC负响应码常量（ISO 14229标准定义，类属性相当于枚举） ----------
    NRC_SERVICE_NOT_SUPPORTED = 0x11   # 服务不支持
    NRC_INCORRECT_LENGTH = 0x13        # 报文长度错误
    NRC_REQUEST_OUT_OF_RANGE = 0x31    # 请求超出范围（如DID不存在）

    def __init__(self, channel: str = 'vcan0', request_id: int = 0x7E0, response_id: int = 0x7E8) -> None:
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
    def start(self) -> None:
        """启动ECU：持续监听总线（阻塞循环，需在独立线程中运行）"""
        self._running = True
        logger.info("[ECU] 已启动，开始监听总线...")
        while self._running:
            # 从总线读一帧，最多等0.1秒（超时是为了能定期检查退出标志）
            msg = self.bus.recv(timeout=0.1)
            if msg is None:
                continue                          # 超时无报文，继续下一轮
            if msg.arbitration_id != self.request_id:
                continue                          # 不是发给我的诊断请求，忽略
            self._handle_request(msg)             # 交给分发器处理

    def stop(self) -> None:
        """通知主循环退出（只改标志位，循环会在0.1秒内自然结束）"""
        self._running = False

    def shutdown(self) -> None:
        """关闭总线，释放资源（应在主循环退出后调用）"""
        self.bus.shutdown()

    # ==================== 请求分发 ====================
    def _handle_request(self, msg: can.Message) -> None:
        """解析请求帧，按SID分发到对应服务处理函数"""
        if len(msg.data) < 2:
            return  # 帧长度连"长度+SID"都不够，是畸形帧，直接忽略

        length = msg.data[0]  # 第0字节：有效数据长度（简化版ISO-TP单帧PCI）
        sid = msg.data[1]     # 第1字节：服务ID
        logger.info(f"[ECU] 收到请求: SID=0x{sid:02X}")

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
        logger.info(f"[ECU] 发送正响应: SID=0x{resp_sid:02X}")

    def _send_negative_response(self, sid, nrc):
        """发送负响应：固定格式 0x7F + 原SID + NRC"""
        frame = [0x03, 0x7F, sid, nrc, 0x00, 0x00, 0x00, 0x00]
        msg = can.Message(arbitration_id=self.response_id,
                          data=frame, is_extended_id=False)
        self.bus.send(msg)
        logger.info(f"[ECU] 发送负响应: SID=0x{sid:02X}, NRC=0x{nrc:02X}")
'''
# -*- coding: utf-8 -*-
"""
虚拟ECU模块 v2（Day3：加入状态机）
相比Day2新增：
- 0x10 会话控制：默认会话 / 扩展会话
- 0x27 安全访问：种子&密钥解锁机制
- 0x2E 写数据服务：受会话和安全状态双重保护
- ECU从"无状态"变为"有状态"，同类请求在不同状态下响应不同
"""
import logging
import logging  # 标准日志模块：输出可分级、可静默

import can

logger = logging.getLogger(__name__)  # 当前模块日志器  # python-can库，负责CAN总线通信
logger = logging.getLogger(__name__)

class VirtualECU:
    """虚拟ECU：本项目的被测对象（DUT, Device Under Test）"""

    # ---------- NRC负响应码常量（ISO 14229标准定义） ----------
    NRC_SERVICE_NOT_SUPPORTED = 0x11          # 服务不支持
    NRC_SUB_FUNCTION_NOT_SUPPORTED = 0x12     # 子功能不支持
    NRC_INCORRECT_LENGTH = 0x13               # 报文长度错误
    NRC_REQUEST_OUT_OF_RANGE = 0x31           # 请求超出范围
    NRC_SECURITY_ACCESS_DENIED = 0x33         # 安全访问被拒绝（未解锁）
    NRC_INVALID_KEY = 0x35                    # 密钥错误
    NRC_NOT_SUPPORTED_IN_SESSION = 0x7F       # 当前会话下不支持该服务

    # ---------- 会话类型常量 ----------
    SESSION_DEFAULT = 0x01    # 默认会话（上电初始状态）
    SESSION_EXTENDED = 0x03   # 扩展会话（诊断操作的主战场）

    # ---------- 种子&密钥算法常量（教学用） ----------
    SEED_FIXED = 0xA5B6       # 固定种子（真实ECU用随机数，固定值便于自动化测试）
    KEY_MASK = 0xFFFF         # 密钥算法：密钥 = 种子 XOR 0xFFFF

    def __init__(self, channel: str = 'vcan0', request_id: int = 0x7E0, response_id: int = 0x7E8) -> None:
        """初始化ECU：建立总线连接、准备内部数据和状态"""
        self.request_id = request_id    # 诊断请求CAN ID
        self.response_id = response_id  # 诊断响应CAN ID

        # 创建总线对象；receive_own_messages=False 表示不接收自己发出的报文
        self.bus = can.interface.Bus(
            interface='virtual', channel=channel, receive_own_messages=False
        )

        # DID数据库（模拟ECU内部存储区）：键=DID编号，值=数据字节列表
        self.did_table = {
            0xF190: [0x4C, 0x53, 0x56, 0x31],  # VIN码片段"LSV1"
            0xF18C: [0x20, 0x24, 0x01, 0x01],  # ECU序列号
            0xF187: [0x01, 0x00, 0x02, 0x0A],  # 软件版本号（只读）
        }

        # 可写DID白名单：不在此列表的DID一律只读（软件版本号不允许改写）
        self.writable_dids = {0xF190, 0xF18C}

        # ===== Day3新增：ECU状态变量（状态机的核心） =====
        self.session = self.SESSION_DEFAULT  # 当前会话：上电后处于默认会话
        self.security_unlocked = False       # 安全状态：上电后处于锁定状态

        # 服务分发表：SID → 处理函数（Day3注册了两个新服务）
        self.service_handlers = {
            0x10: self._handle_session_control,            # 会话控制
            0x22: self._handle_read_data_by_identifier,    # 读数据
            0x27: self._handle_security_access,            # 安全访问
            0x2E: self._handle_write_data_by_identifier,   # 写数据
        }

        self._running = False  # 主循环运行标志

    # ==================== 主循环（与Day2相同） ====================
    def start(self) -> None:
        """启动ECU：持续监听总线（阻塞循环，需在独立线程中运行）"""
        self._running = True
        logger.info("[ECU] 已启动，开始监听总线...")
        while self._running:
            msg = self.bus.recv(timeout=0.1)   # 读一帧，最多等0.1秒
            if msg is None:
                continue                       # 超时无报文，继续
            if msg.arbitration_id != self.request_id:
                continue                       # 不是发给我的请求，忽略
            self._handle_request(msg)          # 交给分发器

    def stop(self) -> None:
        """通知主循环退出"""
        self._running = False

    def shutdown(self) -> None:
        """关闭总线，释放资源"""
        self.bus.shutdown()

    # ==================== 请求分发（与Day2相同） ====================
    def _handle_request(self, msg: can.Message) -> None:
        """解析请求帧，按SID分发到对应服务处理函数"""
        if len(msg.data) < 2:
            return  # 畸形帧，直接忽略

        length = msg.data[0]  # 有效数据长度（简化版单帧PCI）
        sid = msg.data[1]     # 服务ID
        logger.info(f"[ECU] 收到请求: SID=0x{sid:02X}")

        handler = self.service_handlers.get(sid)  # 查分发表
        if handler is None:
            self._send_negative_response(sid, self.NRC_SERVICE_NOT_SUPPORTED)
            return
        handler(msg.data, length)

    # ==================== 0x10 会话控制（Day3新增） ====================
    def _handle_session_control(self, data, length):
        """处理 DiagnosticSessionControl：切换诊断会话"""
        # 校验1：长度必须是2（SID + 子功能）
        if length != 0x02:
            self._send_negative_response(0x10, self.NRC_INCORRECT_LENGTH)
            return

        sub = data[2]  # 子功能字节：目标会话类型

        # 校验2：只支持 0x01(默认) 和 0x03(扩展)
        if sub not in (self.SESSION_DEFAULT, self.SESSION_EXTENDED):
            self._send_negative_response(0x10, self.NRC_SUB_FUNCTION_NOT_SUPPORTED)
            return

        # 关键安全逻辑：切回默认会话时，安全锁必须重置！
        # （防止"解锁后永久保持权限"的安全漏洞，真实ECU都这样做）
        old_session = self.session
        self.session = sub
        if sub == self.SESSION_DEFAULT:
            self.security_unlocked = False
        logger.info(f"[ECU] 会话切换: 0x{old_session:02X} -> 0x{sub:02X}, 安全锁={'解锁' if self.security_unlocked else '锁定'}")

        # 正响应：0x50 + 子功能回显 + 会话时间参数(P2/P2*，此处给标准固定值)
        payload = [sub, 0x00, 0x32, 0x01, 0xF4]
        self._send_positive_response(0x10, payload)

    # ==================== 0x22 读数据服务（与Day2相同） ====================
    def _handle_read_data_by_identifier(self, data, length):
        """处理 ReadDataByIdentifier：按DID读取ECU内部数据（任何会话下都允许）"""
        if length != 0x03:                       # 长度校验
            self._send_negative_response(0x22, self.NRC_INCORRECT_LENGTH)
            return
        did = (data[2] << 8) | data[3]           # 拼接16位DID
        if did not in self.did_table:            # DID存在性校验
            self._send_negative_response(0x22, self.NRC_REQUEST_OUT_OF_RANGE)
            return
        payload = [data[2], data[3]] + self.did_table[did]  # DID回显 + 数据
        self._send_positive_response(0x22, payload)

    # ==================== 0x27 安全访问（Day3新增） ====================
    def _handle_security_access(self, data, length):
        """处理 SecurityAccess：种子&密钥挑战，通过后解锁"""
        # 校验1：安全访问必须在扩展会话下进行（默认会话直接拒绝）
        if self.session != self.SESSION_EXTENDED:
            self._send_negative_response(0x27, self.NRC_NOT_SUPPORTED_IN_SESSION)
            return

        sub = data[2]  # 子功能：0x01=请求种子，0x02=发送密钥

        if sub == 0x01:
            # ---- 请求种子 ----
            if length != 0x02:
                self._send_negative_response(0x27, self.NRC_INCORRECT_LENGTH)
                return
            # 发送种子：0x67 + 子功能 + 2字节种子
            payload = [sub, (self.SEED_FIXED >> 8) & 0xFF, self.SEED_FIXED & 0xFF]
            self._send_positive_response(0x27, payload)

        elif sub == 0x02:
            # ---- 发送密钥 ----
            if length != 0x04:                   # 长度=SID+子功能+2字节密钥
                self._send_negative_response(0x27, self.NRC_INCORRECT_LENGTH)
                return
            key = (data[3] << 8) | data[4]       # 拼接16位密钥
            expected_key = self.SEED_FIXED ^ self.KEY_MASK  # 按约定算法计算期望密钥
            if key != expected_key:
                # 密钥错误 → NRC 0x35，且保持锁定
                self._send_negative_response(0x27, self.NRC_INVALID_KEY)
                return
            # 密钥正确 → 解锁！
            self.security_unlocked = True
            logger.info("[ECU] 密钥正确，安全解锁成功 🔓")
            self._send_positive_response(0x27, [sub])

        else:
            # 其他子功能不支持
            self._send_negative_response(0x27, self.NRC_SUB_FUNCTION_NOT_SUPPORTED)

    # ==================== 0x2E 写数据服务（Day3新增） ====================
    def _handle_write_data_by_identifier(self, data, length):
        """处理 WriteDataByIdentifier：修改ECU内部数据（受双重保护）"""
        # NRC检查优先级（ISO 14229推荐顺序）：长度 → 会话 → 安全 → DID范围
        # 校验1：长度=SID(1)+DID(2)+数据(4)=7
        if length != 0x07:
            self._send_negative_response(0x2E, self.NRC_INCORRECT_LENGTH)
            return
        # 校验2：必须在扩展会话下
        if self.session != self.SESSION_EXTENDED:
            self._send_negative_response(0x2E, self.NRC_NOT_SUPPORTED_IN_SESSION)
            return
        # 校验3：必须已通过安全解锁（这就是经典的 NRC 0x33 场景！）
        if not self.security_unlocked:
            self._send_negative_response(0x2E, self.NRC_SECURITY_ACCESS_DENIED)
            return
        # 校验4：DID必须存在且在可写白名单中
        did = (data[2] << 8) | data[3]
        if did not in self.writable_dids:
            self._send_negative_response(0x2E, self.NRC_REQUEST_OUT_OF_RANGE)
            return

        # 全部通过 → 真正执行写入（修改内部状态！）
        self.did_table[did] = [data[4], data[5], data[6], data[7]]
        logger.info(f"[ECU] DID 0x{did:04X} 已写入新数据: {[hex(b) for b in self.did_table[did]]}")
        # 正响应：0x6E + DID回显
        self._send_positive_response(0x2E, [data[2], data[3]])

    # ==================== 响应发送（与Day2相同） ====================
    def _send_positive_response(self, sid, payload):
        """发送正响应：响应SID = 请求SID + 0x40"""
        resp_sid = sid + 0x40
        frame = [1 + len(payload), resp_sid] + payload        # 组帧
        frame = frame + [0x00] * (8 - len(frame))             # 补满8字节
        msg = can.Message(arbitration_id=self.response_id,
                          data=frame, is_extended_id=False)
        self.bus.send(msg)
        logger.info(f"[ECU] 发送正响应: SID=0x{resp_sid:02X}")

    def _send_negative_response(self, sid, nrc):
        """发送负响应：固定格式 0x7F + 原SID + NRC"""
        frame = [0x03, 0x7F, sid, nrc, 0x00, 0x00, 0x00, 0x00]
        msg = can.Message(arbitration_id=self.response_id,
                          data=frame, is_extended_id=False)
        self.bus.send(msg)
        logger.info(f"[ECU] 发送负响应: SID=0x{sid:02X}, NRC=0x{nrc:02X}")