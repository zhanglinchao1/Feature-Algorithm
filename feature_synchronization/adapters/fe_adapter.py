"""
3.1 Feature-Encryption 模块适配器

该适配器解决以下问题：
1. 命名空间冲突：feature_synchronization和feature-encryption都使用src目录
2. 接口适配：将3.1的register/authenticate接口适配为3.3需要的derive_keys接口
3. 参数转换：转换不同模块间的数据格式

使用方式：
    from adapters.fe_adapter import FeatureEncryptionAdapter

    adapter = FeatureEncryptionAdapter()
    S, L, K, Ks, digest = adapter.derive_keys_for_device(...)
"""

import sys
import os
from pathlib import Path
from typing import Tuple, Optional
import numpy as np


class FeatureEncryptionAdapter:
    """
    3.1模块适配器

    负责安全地导入并调用feature-encryption模块的接口
    """

    def __init__(self, config=None, deterministic_for_testing: bool = False):
        """
        初始化适配器

        Args:
            config: 特征加密配置（可选），如果为None则使用默认配置
            deterministic_for_testing: 是否启用确定性测试模式
        """
        self._fe = None
        self._FEContext = None
        self._FEKeyOutput = None
        self._config = config
        self._deterministic_mode = deterministic_for_testing

        # 延迟导入（避免初始化时的命名空间污染）
        self._import_fe_module()

    def _import_fe_module(self):
        """
        安全地导入3.1模块

        使用独立的命名空间避免与feature_synchronization的src目录冲突
        """
        # 保存当前的src模块状态
        saved_src_modules = {}
        for modname in list(sys.modules.keys()):
            if modname == 'src' or modname.startswith('src.'):
                saved_src_modules[modname] = sys.modules.pop(modname)

        try:
            # 添加3.1模块路径
            fe_root = Path(__file__).parent.parent.parent / 'feature-encryption'
            if not fe_root.exists():
                raise FileNotFoundError(f"feature-encryption directory not found at {fe_root}")

            if str(fe_root) not in sys.path:
                sys.path.insert(0, str(fe_root))

            # 导入3.1模块的类
            from src.feature_encryption import FeatureEncryption, Context, KeyOutput
            from src.config import FeatureEncryptionConfig

            # 保存引用
            self._FEClass = FeatureEncryption
            self._FEContext = Context
            self._FEKeyOutput = KeyOutput
            self._FEConfig = FeatureEncryptionConfig

            # 初始化FeatureEncryption实例
            if self._config is None:
                self._config = FeatureEncryptionConfig()

            self._fe = FeatureEncryption(
                config=self._config,
                deterministic_for_testing=self._deterministic_mode
            )

        finally:
            # 清除3.1的src模块，恢复原始状态
            for modname in list(sys.modules.keys()):
                if modname == 'src' or modname.startswith('src.'):
                    sys.modules.pop(modname, None)

            # 恢复feature_synchronization的src模块
            for modname, mod in saved_src_modules.items():
                sys.modules[modname] = mod

    def derive_keys_for_device(
        self,
        device_mac: bytes,
        validator_mac: bytes,
        feature_vector: np.ndarray,
        epoch: int,
        nonce: bytes,
        hash_chain_counter: int,
        domain: bytes = b'DefaultDomain',
        version: int = 1
    ) -> Tuple[bytes, bytes, bytes, bytes, bytes]:
        """
        为设备派生密钥材料（注册阶段）

        该方法将3.3模块需要的参数转换为3.1模块的register()接口

        Args:
            device_mac: 设备MAC地址（6字节）
            validator_mac: 验证节点MAC地址（6字节）
            feature_vector: 特征向量，shape (M, D) - M帧D维特征
            epoch: epoch编号
            nonce: 随机数（16字节）
            hash_chain_counter: 哈希链计数器（Ci）
            domain: 域标识
            version: 版本号

        Returns:
            tuple: (S, L, K, Ks, digest)
                - S: 稳定特征串（32字节）
                - L: 随机扰动值（32字节）
                - K: 特征密钥（32字节）
                - Ks: 会话密钥（32字节）
                - digest: 一致性摘要（8字节）

        Raises:
            ValueError: 如果参数格式不正确
            RuntimeError: 如果密钥派生失败
        """
        # 参数验证
        if len(device_mac) != 6:
            raise ValueError(f"device_mac must be 6 bytes, got {len(device_mac)}")
        if len(validator_mac) != 6:
            raise ValueError(f"validator_mac must be 6 bytes, got {len(validator_mac)}")
        if len(nonce) != 16:
            raise ValueError(f"nonce must be 16 bytes, got {len(nonce)}")
        if feature_vector is None or len(feature_vector.shape) != 2:
            raise ValueError("feature_vector must be 2D array with shape (M, D)")

        # 构造上下文
        context = self._FEContext(
            srcMAC=device_mac,
            dstMAC=validator_mac,
            dom=domain,
            ver=version,
            epoch=epoch,
            Ci=hash_chain_counter,
            nonce=nonce
        )

        # 调用3.1的register接口
        device_id = device_mac.hex()

        try:
            key_output, metadata = self._fe.register(device_id, feature_vector, context)
        except Exception as e:
            raise RuntimeError(f"Failed to derive keys: {e}") from e

        # 返回密钥材料
        return (
            key_output.S,
            key_output.L,
            key_output.K,
            key_output.Ks,
            key_output.digest
        )

    def authenticate_device(
        self,
        device_mac: bytes,
        validator_mac: bytes,
        feature_vector: np.ndarray,
        epoch: int,
        nonce: bytes,
        hash_chain_counter: int,
        domain: bytes = b'DefaultDomain',
        version: int = 1
    ) -> Tuple[bool, Optional[bytes], Optional[bytes], Optional[bytes], Optional[bytes], Optional[bytes]]:
        """
        认证设备并恢复密钥材料

        该方法将3.3模块需要的参数转换为3.1模块的authenticate()接口

        Args:
            device_mac: 设备MAC地址（6字节）
            validator_mac: 验证节点MAC地址（6字节）
            feature_vector: 特征向量，shape (M, D)
            epoch: epoch编号
            nonce: 随机数（16字节）
            hash_chain_counter: 哈希链计数器
            domain: 域标识
            version: 版本号

        Returns:
            tuple: (success, S, L, K, Ks, digest)
                - success: 认证是否成功
                - S, L, K, Ks, digest: 如果成功则返回密钥材料，否则为None

        Raises:
            ValueError: 如果参数格式不正确
        """
        # 参数验证
        if len(device_mac) != 6:
            raise ValueError(f"device_mac must be 6 bytes, got {len(device_mac)}")
        if len(validator_mac) != 6:
            raise ValueError(f"validator_mac must be 6 bytes, got {len(validator_mac)}")
        if len(nonce) != 16:
            raise ValueError(f"nonce must be 16 bytes, got {len(nonce)}")
        if feature_vector is None or len(feature_vector.shape) != 2:
            raise ValueError("feature_vector must be 2D array with shape (M, D)")

        # 构造上下文
        context = self._FEContext(
            srcMAC=device_mac,
            dstMAC=validator_mac,
            dom=domain,
            ver=version,
            epoch=epoch,
            Ci=hash_chain_counter,
            nonce=nonce
        )

        # 调用3.1的authenticate接口
        device_id = device_mac.hex()

        try:
            key_output, success = self._fe.authenticate(device_id, feature_vector, context)
        except Exception as e:
            # 认证过程中的异常视为认证失败
            return False, None, None, None, None, None

        if success and key_output is not None:
            return (
                True,
                key_output.S,
                key_output.L,
                key_output.K,
                key_output.Ks,
                key_output.digest
            )
        else:
            return False, None, None, None, None, None

    def get_config(self):
        """获取当前配置"""
        return self._config

    def is_deterministic_mode(self) -> bool:
        """检查是否为确定性测试模式"""
        return self._deterministic_mode


# 便捷函数
def create_adapter(deterministic_for_testing: bool = False):
    """
    创建适配器实例的便捷函数

    Args:
        deterministic_for_testing: 是否启用确定性测试模式

    Returns:
        FeatureEncryptionAdapter: 适配器实例
    """
    return FeatureEncryptionAdapter(deterministic_for_testing=deterministic_for_testing)
