# -*- coding: utf-8 -*-
"""0x2E写数据服务的自动化测试"""
import pytest

NEW_VIN = [0x57, 0x50, 0x30, 0x32]  # 待写入的新VIN片段"WP02"


class TestWriteDataProtection:
    """写保护：条件不满足时必须拒绝（8条）"""

    def test_write_in_default_session_nrc7f(self, ecu_and_tester):
        """默认会话写数据 → NRC 0x7F"""
        _, tester = ecu_and_tester
        resp = tester.request([0x07, 0x2E, 0xF1, 0x90] + NEW_VIN)
        assert resp[1:4] == [0x7F, 0x2E, 0x7F]

    def test_write_without_unlock_nrc33(self, ecu_and_tester):
        """扩展会话但未解锁 → NRC 0x33（全场最经典的用例）"""
        _, tester = ecu_and_tester
        tester.request([0x02, 0x10, 0x03])               # 只切会话，故意不解锁
        resp = tester.request([0x07, 0x2E, 0xF1, 0x90] + NEW_VIN)
        assert resp[1:4] == [0x7F, 0x2E, 0x33]

    def test_write_readonly_did_nrc31(self, unlocked_tester):
        """已解锁但写只读DID(版本号0xF187) → NRC 0x31"""
        resp = unlocked_tester.request(
            [0x07, 0x2E, 0xF1, 0x87, 0x01, 0x02, 0x03, 0x04])
        assert resp[1:4] == [0x7F, 0x2E, 0x31]

    def test_write_nonexistent_did_nrc31(self, unlocked_tester):
        """已解锁但写不存在的DID → NRC 0x31"""
        resp = unlocked_tester.request(
            [0x07, 0x2E, 0x99, 0x99, 0x01, 0x02, 0x03, 0x04])
        assert resp[1:4] == [0x7F, 0x2E, 0x31]

    @pytest.mark.parametrize("length", [0x03, 0x04, 0x05, 0x06])  # 4种错误长度
    def test_write_wrong_length_nrc13(self, unlocked_tester, length):
        """写长度≠7 → NRC 0x13"""
        resp = unlocked_tester.request(
            [length, 0x2E, 0xF1, 0x90, 0x01, 0x02, 0x03, 0x04])
        assert resp[1:4] == [0x7F, 0x2E, 0x13]


class TestWriteDataPositive:
    """正向：写读闭环（2条）"""

    @pytest.mark.parametrize("did", [0xF190, 0xF18C])  # 两个可写DID各测一遍
    def test_write_then_readback(self, unlocked_tester, did):
        """写入→正响应→回读验证（证明写入真正生效，而非假响应）"""
        new_data = [0x11, 0x22, 0x33, 0x44]
        resp = unlocked_tester.request([0x07, 0x2E, did >> 8, did & 0xFF] + new_data)
        assert resp[1:4] == [0x6E, did >> 8, did & 0xFF]  # 写正响应+DID回显
        resp = unlocked_tester.request([0x03, 0x22, did >> 8, did & 0xFF])  # 回读
        assert resp[4:8] == new_data                       # 读回的必须是新数据