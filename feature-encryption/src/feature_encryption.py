"""
特征加密主流程

整合所有模块，提供统一的对外接口。
"""

import numpy as np
from typing import Dict, Any, Tuple, Optional, List
from dataclasses import dataclass

from .config import FeatureEncryptionConfig
from .feature_processor import FeatureProcessor
from .quantizer import FeatureQuantizer
from .fuzzy_extractor import FuzzyExtractor
from .key_derivation import KeyDerivation


@dataclass
class Context:
    """上下文信息"""
    srcMAC: bytes  # 源MAC地址（6字节）
    dstMAC: bytes  # 目标MAC地址（6字节）
    dom: bytes  # 域标识
    ver: int  # 算法版本
    epoch: int  # 时间窗编号
    Ci: int  # 哈希链计数器
    nonce: bytes  # 随机数（16字节）


@dataclass
class KeyOutput:
    """密钥输出"""
    S: bytes  # 稳定特征串（32字节）
    L: bytes  # 随机扰动值（32字节）
    K: bytes  # 特征密钥（KEY_LENGTH字节）
    Ks: bytes  # 会话密钥（KEY_LENGTH字节）
    digest: bytes  # 一致性摘要（DIGEST_LENGTH字节）


class FeatureEncryption:
    """特征加密算法主类"""

    def __init__(self, config: FeatureEncryptionConfig = None, deterministic_for_testing: bool = False):
        """
        初始化特征加密算法

        Args:
            config: 算法配置，默认使用默认配置
            deterministic_for_testing: 是否启用测试模式（确定性随机填充），默认False
        """
        if config is None:
            config = FeatureEncryptionConfig()

        # 验证配置
        config.validate()

        self.config = config

        # 初始化各模块
        self.feature_processor = FeatureProcessor(config)
        self.quantizer = FeatureQuantizer(config, deterministic_for_testing=deterministic_for_testing)
        self.fuzzy_extractor = FuzzyExtractor(config)
        self.key_derivation = KeyDerivation(config)

        # 存储辅助数据（实际应用中应该存储在安全的数据库中）
        self._helper_data_store: Dict[str, bytes] = {}
        # 存储门限数据
        self._threshold_store: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}

    def register(
        self,
        device_id: str,
        Z_frames: np.ndarray,
        context: Context,
        **kwargs
    ) -> Tuple[KeyOutput, Dict[str, Any]]:
        """
        注册阶段：采集特征并生成辅助数据

        Args:
            device_id: 设备标识
            Z_frames: 多帧特征，shape (M, D)
            context: 上下文信息
            **kwargs: 额外参数（如mask等）

        Returns:
            key_output: 密钥输出
            metadata: 元数据（包含门限、掩码等）
        """
        # Step 1: 处理多帧特征，得到比特串
        r, theta_L, theta_H = self.quantizer.process_multi_frames(Z_frames)

        # Step 2: 生成辅助数据
        P = self.fuzzy_extractor.generate_helper_data(r)

        # 存储辅助数据和门限
        self._store_helper_data(device_id, P)
        self._store_thresholds(device_id, theta_L, theta_H)

        # Step 3: 注册阶段直接使用r作为S（无需BCH解码）
        # 根据算法规范：注册时 S = r，认证时 S = error_correction(r', P)
        S_bits = r

        # Step 4: 将比特串转换为字节串
        S_bytes = self.key_derivation.bits_to_bytes(S_bits)

        # Step 4: 密钥派生
        key_output = self._derive_keys(S_bytes, context)

        # Step 5: 生成一致性摘要
        mask_bytes = kwargs.get('mask_bytes', b'')
        theta_L_bytes = theta_L.tobytes()
        theta_H_bytes = theta_H.tobytes()

        digest = self.key_derivation.generate_digest(
            mask_bytes, theta_L_bytes, theta_H_bytes
        )

        # 更新key_output
        key_output.digest = digest

        # 准备元数据
        metadata = {
            'theta_L': theta_L,
            'theta_H': theta_H,
            'mask': kwargs.get('mask', {}),
            'helper_data_id': device_id,
            'bit_count': len(r),
        }

        return key_output, metadata

    def authenticate(
        self,
        device_id: str,
        Z_frames: np.ndarray,
        context: Context,
        **kwargs
    ) -> Tuple[Optional[KeyOutput], bool]:
        """
        认证阶段：重新采集特征并恢复密钥

        Args:
            device_id: 设备标识
            Z_frames: 多帧特征，shape (M, D)
            context: 上下文信息
            **kwargs: 额外参数

        Returns:
            key_output: 密钥输出（失败时为None）
            success: 是否成功
        """
        # Step 1: 处理多帧特征，计算新的门限并得到含噪比特串
        # 注意：这里计算新的门限，使量化能适应当前CSI测量
        r_prime, theta_L_new, theta_H_new = self.quantizer.process_multi_frames(Z_frames)

        # Step 2: 读取辅助数据
        P = self._load_helper_data(device_id)
        if P is None:
            return None, False

        # Step 3: 提取稳定特征串
        S_bits, success = self.fuzzy_extractor.extract_stable_key(r_prime, P)

        if not success:
            return None, False

        # Step 4: 转换为字节串
        S_bytes = self.key_derivation.bits_to_bytes(S_bits)

        # Step 5: 密钥派生
        key_output = self._derive_keys(S_bytes, context)

        # Step 6: 生成一致性摘要
        # 重要：这里使用注册时存储的门限，确保digest一致
        mask_bytes = kwargs.get('mask_bytes', b'')

        # 读取存储的门限用于digest计算
        stored_thresholds = self._load_thresholds(device_id)
        if stored_thresholds is not None:
            theta_L_stored, theta_H_stored = stored_thresholds
            theta_L_bytes = theta_L_stored.tobytes()
            theta_H_bytes = theta_H_stored.tobytes()
        else:
            # 如果没有存储的门限（向后兼容），使用当前计算的门限
            theta_L_bytes = theta_L_new.tobytes()
            theta_H_bytes = theta_H_new.tobytes()

        digest = self.key_derivation.generate_digest(
            mask_bytes, theta_L_bytes, theta_H_bytes
        )

        key_output.digest = digest

        return key_output, True

    def feature_key_gen(
        self,
        X: np.ndarray,
        mode: str,
        context: Context,
        is_registration: bool = False,
        device_id: str = None,
        **kwargs
    ) -> Tuple[Optional[KeyOutput], bool]:
        """
        完整的特征密钥生成流程

        Args:
            X: 原始特征数据或单帧特征
            mode: 'CSI' or 'RFF'
            context: 上下文信息
            is_registration: 是否为注册阶段
            device_id: 设备标识（认证时必需）
            **kwargs: 额外参数

        Returns:
            key_output: 密钥输出
            success: 是否成功
        """
        # Step 1: 特征预处理（如果X是原始数据）
        if len(X.shape) == 1 or (len(X.shape) == 2 and X.shape[0] == 1):
            # 单帧特征，需要采集多帧
            Z, mask = self.feature_processor.process_feature(X, mode, **kwargs)

            # 模拟采集多帧（实际应用中应该真实采集）
            Z_frames = np.tile(Z, (self.config.M_FRAMES, 1))

            # 添加噪声模拟真实采集
            noise = np.random.randn(*Z_frames.shape) * 0.1
            Z_frames = Z_frames + noise

            mask_bytes = FeatureProcessor.serialize_mask(mask)
        else:
            # 已经是多帧特征
            Z_frames = X
            mask_bytes = kwargs.get('mask_bytes', b'')

        # Step 2: 根据阶段选择流程
        if is_registration:
            if device_id is None:
                raise ValueError("device_id is required for registration")

            key_output, metadata = self.register(
                device_id, Z_frames, context, mask_bytes=mask_bytes
            )
            return key_output, True
        else:
            if device_id is None:
                raise ValueError("device_id is required for authentication")

            return self.authenticate(
                device_id, Z_frames, context, mask_bytes=mask_bytes
            )

    def _derive_keys(
        self,
        S_bytes: bytes,
        context: Context
    ) -> KeyOutput:
        """
        内部方法：派生所有密钥

        Args:
            S_bytes: 稳定特征串字节
            context: 上下文信息

        Returns:
            KeyOutput: 密钥输出
        """
        # 确保S是32字节
        if len(S_bytes) < 32:
            S_bytes = S_bytes + b'\x00' * (32 - len(S_bytes))
        S_bytes = S_bytes[:32]

        # 计算随机扰动值 L
        L = self.key_derivation.compute_L(context.epoch, context.nonce)

        # 派生特征密钥 K
        K = self.key_derivation.derive_feature_key(
            S_bytes, L,
            context.dom,
            context.srcMAC,
            context.dstMAC,
            context.ver,
            context.epoch
        )

        # 派生会话密钥 Ks
        Ks = self.key_derivation.derive_session_key(
            K, context.epoch, context.Ci
        )

        return KeyOutput(
            S=S_bytes,
            L=L,
            K=K,
            Ks=Ks,
            digest=b''  # 稍后填充
        )

    def _store_helper_data(self, device_id: str, P: bytes) -> None:
        """存储辅助数据"""
        self._helper_data_store[device_id] = P

    def _load_helper_data(self, device_id: str) -> Optional[bytes]:
        """加载辅助数据"""
        return self._helper_data_store.get(device_id)

    def _store_thresholds(
        self,
        device_id: str,
        theta_L: np.ndarray,
        theta_H: np.ndarray
    ) -> None:
        """存储量化门限"""
        self._threshold_store[device_id] = (theta_L, theta_H)

    def _load_thresholds(
        self,
        device_id: str
    ) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """加载量化门限"""
        return self._threshold_store.get(device_id)

    def verify_digest(
        self,
        digest1: bytes,
        digest2: bytes
    ) -> bool:
        """
        验证一致性摘要

        Args:
            digest1: 第一个摘要
            digest2: 第二个摘要

        Returns:
            bool: 是否一致
        """
        return digest1 == digest2


# 导出
__all__ = ['FeatureEncryption', 'Context', 'KeyOutput']
