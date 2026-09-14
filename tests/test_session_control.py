# -*- coding: utf-8 -*-
"""0x10会话控制服务的自动化测试"""
import pytest


class TestSessionControl:
    """会话控制：合法切换 + 各类异常分支"""

    @pytest.mark.parametrize("sub", [0x01, 0x03])  # 两个合法子功能 → 自动跑2条用例
    def test_valid_session_switch(self, ecu_and_tester, sub):
        """合法会话切换 → 正响应0x50 + 子功能回显"""
        _, tester = ecu_and_tester               # 取出诊断仪（ECU由夹具托管）
        resp = tester.request([0x02, 0x10, sub])  # 发送会话切换请求
        assert resp is not None                   # 必须有响应
        assert resp[1] == 0x50                    # 正响应SID = 0x10+0x40
        assert resp[2] == sub                     # 子功能字节回显一致

    @pytest.mark.parametrize("sub", [0x00, 0x02, 0x04, 0x05, 0x7F, 0xFF])  # 6个非法子功能
    def test_invalid_subfunction_nrc12(self, ecu_and_tester, sub):
        """非法子功能 → NRC 0x12（子功能不支持）"""
        _, tester = ecu_and_tester
        resp = tester.request([0x02, 0x10, sub])
        assert resp[1:4] == [0x7F, 0x10, 0x12]    # 负响应三要素：0x7F+SID+NRC

    @pytest.mark.parametrize("length", [0x01, 0x03, 0x04, 0x07])  # 4种错误长度
    def test_wrong_length_nrc13(self, ecu_and_tester, length):
        """长度≠2 → NRC 0x13（报文长度错误）"""
        _, tester = ecu_and_tester
        resp = tester.request([length, 0x10, 0x03, 0, 0, 0, 0, 0])
        assert resp[1:4] == [0x7F, 0x10, 0x13]

    def test_default_session_relocks_security(self, unlocked_tester):
        """解锁后切回默认会话 → 安全锁应自动重置（安全设计关键！）"""
        unlocked_tester.request([0x02, 0x10, 0x01])            # 切回默认会话
        resp = unlocked_tester.request(
            [0x07, 0x2E, 0xF1, 0x90, 0xAA, 0xBB, 0xCC, 0xDD])  # 再尝试写数据
        assert resp[1:4] == [0x7F, 0x2E, 0x7F]                 # 应被拒绝（权限已失效）