# -*- coding: utf-8 -*-
"""健壮性测试：畸形报文、错误CAN ID、连续压力（模糊测试雏形）"""
import can  # 需要直接构造原始CAN帧
import pytest


class TestRobustness:

    def test_malformed_short_frame_ignored(self, ecu_and_tester):
        """数据场不足2字节的畸形帧（连SID都没有）应被ECU忽略，无响应"""
        _, tester = ecu_and_tester
        # 绕过tester的自动补齐，直接发只有1字节数据的原始帧
        msg = can.Message(arbitration_id=0x7E0, data=[0x05],
                          is_extended_id=False)
        tester.bus.send(msg)
        resp = tester.recv_response()
        assert resp is None  # ECU应沉默，而不是崩溃或乱回

    def test_wrong_can_id_ignored(self, ecu_and_tester):
        """发往其他CAN ID的诊断请求不应触发任何响应"""
        _, tester = ecu_and_tester
        resp = tester.request([0x03, 0x22, 0xF1, 0x90], can_id=0x700)  # 错误ID
        assert resp is None

    def test_consecutive_requests_stable(self, ecu_and_tester):
        """连续轰炸20个请求，每个都应得到正确响应（队列稳定性/压力测试）"""
        _, tester = ecu_and_tester
        for i in range(20):
            resp = tester.request([0x03, 0x22, 0xF1, 0x90])
            assert resp is not None and resp[1] == 0x62, \
                f"第{i + 1}个请求响应异常"

    def test_state_isolation_after_write(self, ecu_and_tester, unlocked_tester):
        """本用例中解锁并写入数据（配合下一条用例验证夹具隔离性）"""
        resp = unlocked_tester.request(
            [0x07, 0x2E, 0xF1, 0x90, 0x99, 0x99, 0x99, 0x99])
        assert resp[1] == 0x6E  # 写入应成功

    def test_fresh_ecu_state_reset(self, ecu_and_tester):
        """全新ECU的VIN必须是出厂值（证明上一条用例的写入没有泄漏过来）"""
        _, tester = ecu_and_tester
        resp = tester.request([0x03, 0x22, 0xF1, 0x90])
        assert resp[4:8] == [0x4C, 0x53, 0x56, 0x31]  # 出厂"LSV1"，不是0x99