# -*- coding: utf-8 -*-
"""0x27安全访问服务的自动化测试"""
import pytest


def _goto_extended(tester):
    """辅助函数：切到扩展会话（安全访问的前置条件）"""
    tester.request([0x02, 0x10, 0x03])


class TestSecurityAccess:
    """安全访问：会话门槛 + 种子密钥挑战全流程（16条）"""

    def test_denied_in_default_session(self, ecu_and_tester):
        """默认会话下请求种子 → NRC 0x7F"""
        _, tester = ecu_and_tester
        resp = tester.request([0x02, 0x27, 0x01])
        assert resp[1:4] == [0x7F, 0x27, 0x7F]

    def test_request_seed_positive(self, ecu_and_tester):
        """扩展会话下请求种子 → 0x67 0x01 + 2字节合法种子"""
        _, tester = ecu_and_tester
        _goto_extended(tester)
        resp = tester.request([0x02, 0x27, 0x01])
        assert resp[1:3] == [0x67, 0x01]                 # 正响应 + 子功能回显
        seed = (resp[3] << 8) | resp[4]                  # 提取种子
        assert 0x0000 <= seed <= 0xFFFF                  # 种子必须是合法16位数

    # 注意0x5A48和0x5A4A：正确密钥0x5A49的"左右邻居"，经典边界值测试！
    @pytest.mark.parametrize("wrong_key", [0x0000, 0x0001, 0x1234,
                                           0x5A48, 0x5A4A, 0xFFFF])
    def test_wrong_key_nrc35(self, ecu_and_tester, wrong_key):
        """错误密钥 → NRC 0x35（6条，含边界值±1）"""
        _, tester = ecu_and_tester
        _goto_extended(tester)
        resp = tester.request([0x02, 0x27, 0x01])        # 先要种子
        seed = (resp[3] << 8) | resp[4]
        assert wrong_key != (seed ^ 0xFFFF)              # 确保真的是错误密钥
        resp = tester.request([0x04, 0x27, 0x02,
                               wrong_key >> 8, wrong_key & 0xFF])  # 送错误密钥
        assert resp[1:4] == [0x7F, 0x27, 0x35]

    def test_correct_key_unlock(self, ecu_and_tester):
        """正确密钥 → 0x67 0x02，解锁成功"""
        _, tester = ecu_and_tester
        _goto_extended(tester)
        resp = tester.request([0x02, 0x27, 0x01])
        key = ((resp[3] << 8) | resp[4]) ^ 0xFFFF        # 种子算密钥
        resp = tester.request([0x04, 0x27, 0x02, key >> 8, key & 0xFF])
        assert resp[1:3] == [0x67, 0x02]

    @pytest.mark.parametrize("sub", [0x00, 0x03, 0x05, 0xFF])  # 4个非法子功能
    def test_invalid_subfunction_nrc12(self, ecu_and_tester, sub):
        """非法子功能 → NRC 0x12"""
        _, tester = ecu_and_tester
        _goto_extended(tester)
        resp = tester.request([0x02, 0x27, sub])
        assert resp[1:4] == [0x7F, 0x27, 0x12]

    @pytest.mark.parametrize("length", [0x02, 0x03, 0x05])  # 送密钥时的3种错误长度
    def test_key_wrong_length_nrc13(self, ecu_and_tester, length):
        """密钥长度≠4 → NRC 0x13"""
        _, tester = ecu_and_tester
        _goto_extended(tester)
        tester.request([0x02, 0x27, 0x01])
        resp = tester.request([length, 0x27, 0x02, 0x5A, 0x49, 0, 0, 0])
        assert resp[1:4] == [0x7F, 0x27, 0x13]