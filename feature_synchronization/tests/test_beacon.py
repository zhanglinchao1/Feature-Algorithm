"""
测试SyncBeacon
"""
import pytest
import secrets
from feature_synchronization.core.beacon import SyncBeacon
from feature_synchronization.core.feature_config import FeatureConfig


class TestSyncBeacon:
    """测试同步信标"""

    def test_beacon_creation(self):
        """测试信标创建"""
        config = FeatureConfig.create_default()

        beacon = SyncBeacon(
            epoch=1,
            timestamp=1000000,
            delta_t=30000,
            cluster_head_id=b'\x00' * 6,
            beacon_seq=0,
            feature_config=config,
            signature=b'\x00' * 32
        )

        assert beacon.epoch == 1
        assert beacon.timestamp == 1000000
        assert beacon.delta_t == 30000
        assert len(beacon.cluster_head_id) == 6
        assert beacon.beacon_seq == 0

    def test_beacon_serialization(self):
        """测试信标序列化"""
        config = FeatureConfig.create_default()

        original = SyncBeacon(
            epoch=1,
            timestamp=1000000,
            delta_t=30000,
            cluster_head_id=b'\x00\x00\x00\x00\x00\x01',
            beacon_seq=5,
            feature_config=config,
            signature=b'\x00' * 32
        )

        # 序列化
        data = original.pack()
        assert len(data) > 0

        # 反序列化
        restored = SyncBeacon.unpack(data)

        assert restored.epoch == original.epoch
        assert restored.timestamp == original.timestamp
        assert restored.delta_t == original.delta_t
        assert restored.cluster_head_id == original.cluster_head_id
        assert restored.beacon_seq == original.beacon_seq
        assert restored.signature == original.signature

    def test_beacon_signature(self):
        """测试信标签名"""
        config = FeatureConfig.create_default()
        signing_key = secrets.token_bytes(32)

        beacon = SyncBeacon(
            epoch=1,
            timestamp=1000000,
            delta_t=30000,
            cluster_head_id=b'\x00\x00\x00\x00\x00\x01',
            beacon_seq=0,
            feature_config=config,
            signature=b''
        )

        # 签名
        beacon.sign(signing_key)
        assert len(beacon.signature) == 32

        # 验证
        assert beacon.verify(signing_key) is True

        # 错误的密钥应该验证失败
        wrong_key = secrets.token_bytes(32)
        assert beacon.verify(wrong_key) is False
