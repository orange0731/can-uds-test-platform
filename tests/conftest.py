# -*- coding: utf-8 -*-
"""
pytest公共夹具（conftest.py是pytest的约定文件名，自动加载）
为每个测试用例提供"全新的ECU + 诊断仪"，保证用例间状态完全隔离
"""
import threading  # ECU主循环需后台线程运行
import time       # 启动延时
import pytest     # pytest框架

from src.ecu.virtual_ecu import VirtualECU   # 被测对象
from src.tester.uds_tester import UdsTester  # 诊断仪


@pytest.fixture()
def ecu_and_tester():
    """基础夹具：每个用例启动一套全新ECU+诊断仪，用完后自动清理"""
    # ---- 前置准备（Setup） ----
    ecu = VirtualECU(channel='vcan0')                          # 全新ECU（默认会话+锁定）
    thread = threading.Thread(target=ecu.start, daemon=True)   # 后台线程跑主循环
    thread.start()
    time.sleep(0.1)                                            # 等ECU就绪
    tester = UdsTester(channel='vcan0')                        # 诊断仪接入同一通道

    yield ecu, tester  # 把装备交给测试用例；yield之后是用例结束后的清理代码

    # ---- 后置清理（Teardown，无论用例成败都会执行） ----
    ecu.stop()               # 通知主循环退出
    thread.join(timeout=1.0) # 等待线程结束
    ecu.shutdown()           # 关ECU总线
    tester.close()           # 关诊断仪总线


@pytest.fixture()
def unlocked_tester(ecu_and_tester):
    """进阶夹具：已完成"切扩展会话+安全解锁"的诊断仪（写数据类用例专用）"""
    _, tester = ecu_and_tester
    tester.request([0x02, 0x10, 0x03])                         # 切扩展会话
    resp = tester.request([0x02, 0x27, 0x01])                  # 请求种子
    seed = (resp[3] << 8) | resp[4]                            # 提取种子
    key = seed ^ 0xFFFF                                        # 按约定算法算密钥
    tester.request([0x04, 0x27, 0x02, key >> 8, key & 0xFF])   # 送密钥解锁
    return tester  # 返回"已解锁"状态的诊断仪