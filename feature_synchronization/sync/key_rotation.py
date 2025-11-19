"""
密钥轮换管理模块
"""
import time
import hashlib
import secrets
import logging
from typing import Optional, Tuple
import numpy as np

from ..core.key_material import KeyMaterial
from ..core.epoch_state import EpochState
from ..crypto.hkdf import derive_feature_key, derive_session_key, blake3_hash
from ..utils.logging_config import get_logger

# 导入3.1适配器
try:
    from ..adapters.fe_adapter import FeatureEncryptionAdapter
    FE_ADAPTER_AVAILABLE = True
except ImportError:
    FE_ADAPTER_AVAILABLE = False
    logging.warning("FeatureEncryptionAdapter not available, using mock implementation")


logger = get_logger(__name__)


class KeyRotationManager:
    """密钥轮换管理器"""

    def __init__(self, epoch_state: EpochState, domain: str = "default",
                 use_real_fe: bool = True, deterministic_for_testing: bool = False):
        """
        初始化密钥轮换管理器

        Args:
            epoch_state: epoch状态对象
            domain: 域标识
            use_real_fe: 是否使用真实的3.1接口（默认True）
            deterministic_for_testing: 是否启用确定性测试模式
        """
        self.epoch_state = epoch_state
        # 保存两个版本的domain：bytes用于3.1适配器，str用于Mock
        self.domain_str = domain if isinstance(domain, str) else domain.decode('utf-8')
        self.domain_bytes = domain.encode('utf-8') if isinstance(domain, str) else domain
        self._use_real_fe = use_real_fe and FE_ADAPTER_AVAILABLE
        self._deterministic_mode = deterministic_for_testing

        # 3.1接口适配器
        if self._use_real_fe:
            try:
                self.fe_adapter = FeatureEncryptionAdapter(
                    deterministic_for_testing=deterministic_for_testing
                )
                logger.info(f"KeyRotationManager initialized with real FE adapter: domain={self.domain_str}")
            except Exception as e:
                logger.warning(f"Failed to initialize FE adapter: {e}, falling back to mock")
                self.fe_adapter = None
                self._use_real_fe = False
        else:
            self.fe_adapter = None
            logger.info(f"KeyRotationManager initialized with mock FE: domain={domain}")

    def generate_key_material(self, device_mac: bytes, validator_mac: bytes,
                             epoch: int, feature_vector: Optional[np.ndarray],
                             nonce: bytes) -> KeyMaterial:
        """
        为指定设备和epoch生成密钥材料

        Args:
            device_mac: 设备MAC地址(6字节)
            validator_mac: 验证节点MAC地址(6字节)
            epoch: 时间窗编号
            feature_vector: 特征向量（可选，用于真实特征派生）
            nonce: 随机数(16字节)

        Returns:
            KeyMaterial对象
        """
        logger.debug(f"Generating key material: device={device_mac.hex()}, "
                    f"epoch={epoch}")

        # 获取哈希链计数器
        hash_chain_counter = self._get_hash_chain_counter(device_mac, epoch)

        # 调用3.1接口派生密钥
        if self._use_real_fe and self.fe_adapter and feature_vector is not None:
            # 真实实现：使用3.1 feature-encryption适配器
            try:
                S, L, K, Ks, digest = self.fe_adapter.derive_keys_for_device(
                    device_mac=device_mac,
                    validator_mac=validator_mac,
                    feature_vector=feature_vector,
                    epoch=epoch,
                    nonce=nonce,
                    hash_chain_counter=hash_chain_counter,
                    domain=self.domain_bytes,  # FE adapter需要bytes
                    version=1
                )
                feature_key = K
                session_key = Ks
                logger.debug(f"Used real FE adapter for key derivation: device={device_mac.hex()}")
            except Exception as e:
                logger.warning(f"FE adapter failed: {e}, falling back to mock")
                # 降级到Mock
                feature_key, session_key = self._mock_derive_keys(
                    device_mac, validator_mac, epoch, nonce, hash_chain_counter
                )
        else:
            # Mock实现（降级或无feature_vector时使用）
            feature_key, session_key = self._mock_derive_keys(
                device_mac, validator_mac, epoch, nonce, hash_chain_counter
            )
            if self._use_real_fe and feature_vector is None:
                logger.debug(f"Using mock FE: feature_vector not provided")

        # 派生伪名
        pseudonym = KeyMaterial.derive_pseudonym(feature_key, epoch, hash_chain_counter)

        # 计算有效期
        now = int(time.time() * 1000)
        epoch_duration = self.epoch_state.epoch_duration

        key_material = KeyMaterial(
            epoch=epoch,
            feature_key=feature_key,
            session_key=session_key,
            pseudonym=pseudonym,
            hash_chain_counter=hash_chain_counter,
            valid_from=now,
            valid_until=now + epoch_duration
        )

        # 存储到epoch_state
        self.epoch_state.add_key_material(device_mac, key_material)

        logger.info(f"Key material generated: device={device_mac.hex()}, "
                   f"epoch={epoch}, pseudonym={pseudonym.hex()}")

        return key_material

    def rotate_keys_on_epoch_change(self, device_mac: bytes, validator_mac: bytes,
                                    new_epoch: int, feature_vector: Optional[np.ndarray] = None):
        """
        epoch切换时轮换密钥

        Args:
            device_mac: 设备MAC地址
            validator_mac: 验证节点MAC地址
            new_epoch: 新的epoch
            feature_vector: 特征向量（可选）

        Returns:
            新的KeyMaterial
        """
        logger.info(f"Rotating keys for device {device_mac.hex()} to epoch {new_epoch}")

        # 生成新epoch的密钥材料
        nonce = secrets.token_bytes(16)
        new_key_material = self.generate_key_material(
            device_mac, validator_mac, new_epoch, feature_vector, nonce
        )

        # 保存到epoch状态
        self.epoch_state.add_key_material(device_mac, new_key_material)

        return new_key_material

    def get_key_material(self, device_mac: bytes, epoch: int) -> Optional[KeyMaterial]:
        """
        获取指定设备和epoch的密钥材料

        Args:
            device_mac: 设备MAC地址
            epoch: 时间窗编号

        Returns:
            KeyMaterial或None
        """
        return self.epoch_state.get_active_key(device_mac, epoch)

    def _get_hash_chain_counter(self, device_mac: bytes, epoch: int) -> int:
        """
        获取哈希链计数器Ci

        简单实现：每个epoch递增

        Args:
            device_mac: 设备MAC地址
            epoch: 时间窗编号

        Returns:
            计数器值
        """
        # 简化实现：直接使用epoch作为计数器
        return epoch

    def _mock_derive_keys(self, device_mac: bytes, validator_mac: bytes,
                          epoch: int, nonce: bytes, counter: int) -> Tuple[bytes, bytes]:
        """
        模拟密钥派生（待替换为3.3.1真实实现）

        Args:
            device_mac: 设备MAC地址
            validator_mac: 验证节点MAC地址
            epoch: epoch编号
            nonce: 随机数
            counter: 哈希链计数器

        Returns:
            (feature_key, session_key)元组
        """
        # 模拟特征串S（使用设备MAC作为种子）
        stable_feature = hashlib.sha256(
            b"stable_feature||" + device_mac
        ).digest()

        # 模拟随机扰动值L
        random_perturbation = blake3_hash(epoch.to_bytes(4, 'big') + nonce)

        # 派生特征密钥K
        feature_key = derive_feature_key(
            stable_feature=stable_feature,
            random_perturbation=random_perturbation,
            domain=self.domain_str,  # Mock需要str
            src_mac=device_mac,
            dst_mac=validator_mac,
            version=1
        )

        # 派生会话密钥Ks
        session_key = derive_session_key(
            feature_key=feature_key,
            epoch=epoch,
            hash_chain_counter=counter
        )

        return feature_key, session_key

    def cleanup_expired_keys(self, current_epoch: int):
        """
        清理过期的密钥

        Args:
            current_epoch: 当前epoch
        """
        self.epoch_state._cleanup_old_keys(current_epoch)
        logger.debug(f"Cleaned up keys older than epoch {current_epoch - 1}")
