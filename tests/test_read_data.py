# -*- coding: utf-8 -*-
"""0x22读数据服务的自动化测试"""
import pytest

# DID期望值表（与虚拟ECU内部数据保持一致）：键=DID，值=数据
DID_TABLE = {
    0xF190: [0x4C, 0x53, 0x56, 0x31],  # VIN片段
    0xF18C: [0x20, 0x24, 0x01, 0x01],  # 序列号
    0xF187: [0x01, 0x00, 0x02, 0x0A],  # 软件版本
}


class TestReadDataPositive:
    """正向：读取存在的DID（3条）"""

    @pytest.mark.parametrize("did, expected", DID_TABLE.items())  # 直接喂整个字典
    def test_read_existing_did(self, ecu_and_tester, did, expected):
        _, tester = ecu_and_tester
        resp = tester.request([0x03, 0x22, did >> 8, did & 0xFF])  # DID拆成高低字节
        assert resp[1] == 0x62                          # 正响应SID
        assert (resp[2] << 8) | resp[3] == did          # DID回显一致
        assert resp[4:4 + len(expected)] == expected    # 数据内容逐字节一致


class TestReadDataNegative:
    """负向：各种非法读请求（13条）"""

    @pytest.mark.parametrize("did", [0x0000, 0x0001, 0x1234, 0x9999,
                                     0xF189, 0xF191, 0xFFFF])  # 7个不存在的DID（含边界值）
    def test_nonexistent_did_nrc31(self, ecu_and_tester, did):
        """DID不存在 → NRC 0x31"""
        _, tester = ecu_and_tester
        resp = tester.request([0x03, 0x22, did >> 8, did & 0xFF])
        assert resp[1:4] == [0x7F, 0x22, 0x31]

    @pytest.mark.parametrize("length", [0x01, 0x02, 0x04, 0x05, 0x06, 0x07])  # 6种错误长度
    def test_wrong_length_nrc13(self, ecu_and_tester, length):
        """长度≠3 → NRC 0x13"""
        _, tester = ecu_and_tester
        resp = tester.request([length, 0x22, 0xF1, 0x90, 0, 0, 0, 0])
        assert resp[1:4] == [0x7F, 0x22, 0x13]