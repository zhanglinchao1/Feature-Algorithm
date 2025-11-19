"""
测试密钥轮换
"""
import pytest
import secrets
from feature_synchronization.core.epoch_state import EpochState
from feature_synchronization.sync.key_rotation import KeyRotationManager


class TestKeyRotation:
    """测试密钥轮换管理器"""

    def test_key_material_generation(self):
        """测试密钥材料生成"""
        epoch_state = EpochState(
            current_epoch=1,
            epoch_start_time=1000000,
            epoch_duration=30000
        )

        manager = KeyRotationManager(epoch_state)

        device_mac = b'\x00\x00\x00\x00\x00\x01'
        validator_mac = b'\x00\x00\x00\x00\x00\x02'
        epoch = 1
        nonce = secrets.token_bytes(16)

        key_material = manager.generate_key_material(
            device_mac, validator_mac, epoch, None, nonce
        )

        assert key_material.epoch == epoch
        assert len(key_material.feature_key) == 32
        assert len(key_material.session_key) == 32
        assert len(key_material.pseudonym) == 12
        assert key_material.hash_chain_counter == epoch

    def test_pseudonym_derivation(self):
        """测试伪名派生"""
        from feature_synchronization.core.key_material import KeyMaterial

        feature_key = secrets.token_bytes(32)
        epoch = 5
        counter = 5

        pseudonym1 = KeyMaterial.derive_pseudonym(feature_key, epoch, counter)
        pseudonym2 = KeyMaterial.derive_pseudonym(feature_key, epoch, counter)

        # 相同输入应产生相同伪名
        assert pseudonym1 == pseudonym2
        assert len(pseudonym1) == 12

        # 不同epoch应产生不同伪名
        pseudonym3 = KeyMaterial.derive_pseudonym(feature_key, epoch + 1, counter)
        assert pseudonym3 != pseudonym1

    def test_key_rotation_on_epoch_change(self):
        """测试epoch切换时的密钥轮换"""
        epoch_state = EpochState(
            current_epoch=1,
            epoch_start_time=1000000,
            epoch_duration=30000
        )

        manager = KeyRotationManager(epoch_state)

        device_mac = b'\x00\x00\x00\x00\x00\x01'
        validator_mac = b'\x00\x00\x00\x00\x00\x02'

        # 生成epoch 1的密钥
        key1 = manager.rotate_keys_on_epoch_change(device_mac, validator_mac, 1)
        assert key1.epoch == 1

        # 推进到epoch 2
        epoch_state.update_epoch(2, 1030000, 30000)
        key2 = manager.rotate_keys_on_epoch_change(device_mac, validator_mac, 2)
        assert key2.epoch == 2

        # 伪名应该不同
        assert key1.pseudonym != key2.pseudonym

        # 应该能获取两个epoch的密钥
        assert manager.get_key_material(device_mac, 1) is not None
        assert manager.get_key_material(device_mac, 2) is not None
