# -*- coding: utf-8 -*-
"""未支持服务的负响应测试：ECU没实现的SID，一律应回 NRC 0x11"""
import pytest

# ECU已实现0x10/0x22/0x27/0x2E；以下19个SID都应被拒绝（覆盖常见UDS服务号）
UNSUPPORTED_SIDS = [0x00, 0x01, 0x02, 0x09, 0x0A, 0x11, 0x19, 0x21, 0x28,
                    0x31, 0x34, 0x35, 0x36, 0x37, 0x3E, 0x85, 0x99, 0xA0, 0xFF]


class TestUnsupportedService:
    @pytest.mark.parametrize("sid", UNSUPPORTED_SIDS, ids=lambda s: f"SID-0x{s:02X}")
    def test_unsupported_sid_nrc11(self, ecu_and_tester, sid):
        """未实现的服务 → NRC 0x11（服务不支持）"""
        _, tester = ecu_and_tester
        resp = tester.request([0x02, sid, 0x00])
        assert resp[1:4] == [0x7F, sid, 0x11]
