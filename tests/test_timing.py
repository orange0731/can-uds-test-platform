# -*- coding: utf-8 -*-
"""时序性能测试：验证ECU响应时间满足P2要求"""
import pytest

P2_LIMIT_MS = 100  # P2响应上限（ISO默认50ms，软件仿真环境放宽到100ms）


class TestResponseTiming:
    """响应超时即判ECU性能不合格（5条）"""

    @pytest.mark.parametrize("name, req", [
        ("0x10会话控制", [0x02, 0x10, 0x01]),
        ("0x22读取VIN",  [0x03, 0x22, 0xF1, 0x90]),
        ("0x22读取序列号", [0x03, 0x22, 0xF1, 0x8C]),
        ("0x22读取版本号", [0x03, 0x22, 0xF1, 0x87]),
    ])
    def test_response_within_p2(self, ecu_and_tester, name, req):
        """各服务响应时间必须 < P2上限"""
        _, tester = ecu_and_tester
        resp, elapsed = tester.request_timed(req)        # 发送并计时
        assert resp is not None, f"{name} 完全无响应"
        assert elapsed < P2_LIMIT_MS, \
            f"{name} 响应耗时 {elapsed:.1f}ms 超过P2上限 {P2_LIMIT_MS}ms"

    def test_full_unlock_sequence_timing(self, ecu_and_tester):
        """完整解锁流程（切会话+要种子+送密钥）每步都应满足P2"""
        _, tester = ecu_and_tester
        _, t1 = tester.request_timed([0x02, 0x10, 0x03])            # 切会话耗时
        resp, t2 = tester.request_timed([0x02, 0x27, 0x01])         # 要种子耗时
        key = ((resp[3] << 8) | resp[4]) ^ 0xFFFF
        _, t3 = tester.request_timed([0x04, 0x27, 0x02,
                                      key >> 8, key & 0xFF])        # 送密钥耗时
        assert t1 < P2_LIMIT_MS and t2 < P2_LIMIT_MS and t3 < P2_LIMIT_MS
        print(f"\n解锁流程耗时: 切会话{t1:.1f}ms + 要种子{t2:.1f}ms + 送密钥{t3:.1f}ms")