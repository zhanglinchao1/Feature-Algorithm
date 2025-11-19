"""
配置管理模块

定义所有算法参数的默认值、验证规则和加载方法。
"""

from typing import Dict, Any, Optional
import json
from dataclasses import dataclass, asdict


@dataclass
class FeatureEncryptionConfig:
    """特征加密算法配置类"""

    # ==================== 特征采集参数 ====================
    M_FRAMES: int = 6  # 采集的特征帧数
    N_SUBCARRIER_TOTAL: int = 64  # OFDM子载波总数
    N_SUBCARRIER_SELECTED: int = 32  # 选择的高SNR子载波数
    FEATURE_DIM_CSI: int = 64  # CSI特征维度
    FEATURE_DIM_RFF: int = 16  # RFF特征维度

    # ==================== 量化与投票参数 ====================
    QUANTIZE_METHOD: str = 'percentile'  # 门限计算方法: 'percentile' or 'fixed'
    THETA_L_PERCENTILE: float = 0.25  # 下门限分位数
    THETA_H_PERCENTILE: float = 0.75  # 上门限分位数
    VOTE_THRESHOLD: int = 4  # 投票通过阈值
    TARGET_BITS: int = 256  # 目标比特串长度

    # ==================== BCH纠错码参数 ====================
    BCH_N: int = 255  # BCH码字长度
    BCH_K: int = 131  # BCH消息长度
    BCH_T: int = 18  # BCH纠错能力
    BCH_BLOCKS: int = 2  # 分块数
    BCH_POLY: int = 0x187  # BCH生成多项式

    # ==================== 密钥派生参数 ====================
    HASH_ALGORITHM: str = 'blake3'  # 哈希算法: 'blake3' or 'sha256'
    KEY_LENGTH: int = 32  # 密钥长度（字节）
    DIGEST_LENGTH: int = 8  # 一致性摘要长度（字节）
    HKDF_SALT_DOM: bytes = b'FeatureAuth'  # HKDF盐值
    SESSION_KEY_INFO: str = 'SessionKey'  # 会话密钥派生标识

    # ==================== 上下文参数 ====================
    MAC_LENGTH: int = 6  # MAC地址长度（字节）
    EPOCH_LENGTH: int = 4  # 时间窗编号长度（字节）
    NONCE_LENGTH: int = 16  # 随机数长度（字节）
    VERSION: int = 1  # 算法版本号
    HASH_CHAIN_COUNTER: int = 0  # 哈希链计数器Ci

    def validate(self) -> bool:
        """
        验证配置参数的合法性

        Returns:
            bool: 配置是否合法

        Raises:
            ValueError: 配置参数不合法时抛出异常
        """
        # 采样帧数检查
        if self.M_FRAMES < 4:
            raise ValueError(f"M_FRAMES must be >= 4, got {self.M_FRAMES}")
        if self.M_FRAMES > 10:
            raise ValueError(f"M_FRAMES should be <= 10 for efficiency, got {self.M_FRAMES}")

        # 投票阈值检查
        min_threshold = self.M_FRAMES // 2 + 1
        if self.VOTE_THRESHOLD < min_threshold:
            raise ValueError(
                f"VOTE_THRESHOLD must be > M_FRAMES//2, "
                f"got {self.VOTE_THRESHOLD}, expected >= {min_threshold}"
            )
        if self.VOTE_THRESHOLD > self.M_FRAMES:
            raise ValueError(
                f"VOTE_THRESHOLD cannot exceed M_FRAMES, "
                f"got {self.VOTE_THRESHOLD}, expected <= {self.M_FRAMES}"
            )

        # 子载波数量检查
        if self.N_SUBCARRIER_SELECTED > self.N_SUBCARRIER_TOTAL:
            raise ValueError(
                f"N_SUBCARRIER_SELECTED cannot exceed N_SUBCARRIER_TOTAL, "
                f"got {self.N_SUBCARRIER_SELECTED} > {self.N_SUBCARRIER_TOTAL}"
            )
        if self.N_SUBCARRIER_SELECTED < 16:
            raise ValueError(
                f"N_SUBCARRIER_SELECTED should be >= 16, got {self.N_SUBCARRIER_SELECTED}"
            )

        # 目标比特数检查
        if self.TARGET_BITS <= 0:
            raise ValueError(f"TARGET_BITS must be positive, got {self.TARGET_BITS}")
        if self.TARGET_BITS % 8 != 0:
            raise ValueError(f"TARGET_BITS must be multiple of 8, got {self.TARGET_BITS}")
        if self.TARGET_BITS < 128:
            raise ValueError(f"TARGET_BITS should be >= 128 for security, got {self.TARGET_BITS}")

        # BCH参数检查
        if self.BCH_K >= self.BCH_N:
            raise ValueError(
                f"BCH_K must be < BCH_N, got BCH_K={self.BCH_K}, BCH_N={self.BCH_N}"
            )
        if self.BCH_T < 1:
            raise ValueError(f"BCH_T must be positive, got {self.BCH_T}")

        # 检查BCH分块是否合理
        expected_blocks = (self.TARGET_BITS + self.BCH_K - 1) // self.BCH_K
        if self.BCH_BLOCKS < expected_blocks:
            raise ValueError(
                f"BCH_BLOCKS insufficient for TARGET_BITS, "
                f"got {self.BCH_BLOCKS}, expected >= {expected_blocks}"
            )

        # 密钥长度检查
        valid_key_lengths = [16, 24, 32, 48, 64]
        if self.KEY_LENGTH not in valid_key_lengths:
            raise ValueError(
                f"KEY_LENGTH must be one of {valid_key_lengths}, got {self.KEY_LENGTH}"
            )

        # 分位数检查
        if not (0.0 < self.THETA_L_PERCENTILE < 0.5):
            raise ValueError(
                f"THETA_L_PERCENTILE must be in (0, 0.5), got {self.THETA_L_PERCENTILE}"
            )
        if not (0.5 < self.THETA_H_PERCENTILE < 1.0):
            raise ValueError(
                f"THETA_H_PERCENTILE must be in (0.5, 1.0), got {self.THETA_H_PERCENTILE}"
            )

        # 量化方法检查
        if self.QUANTIZE_METHOD not in ['percentile', 'fixed']:
            raise ValueError(
                f"QUANTIZE_METHOD must be 'percentile' or 'fixed', got {self.QUANTIZE_METHOD}"
            )

        # 哈希算法检查
        if self.HASH_ALGORITHM not in ['blake3', 'sha256']:
            raise ValueError(
                f"HASH_ALGORITHM must be 'blake3' or 'sha256', got {self.HASH_ALGORITHM}"
            )

        return True

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'FeatureEncryptionConfig':
        """
        从字典创建配置对象

        Args:
            config_dict: 配置字典

        Returns:
            FeatureEncryptionConfig: 配置对象
        """
        # 过滤出有效的字段
        valid_fields = {k: v for k, v in config_dict.items() if hasattr(cls, k)}
        config = cls(**valid_fields)
        config.validate()
        return config

    @classmethod
    def from_json(cls, json_path: str) -> 'FeatureEncryptionConfig':
        """
        从JSON文件加载配置

        Args:
            json_path: JSON文件路径

        Returns:
            FeatureEncryptionConfig: 配置对象
        """
        with open(json_path, 'r', encoding='utf-8') as f:
            config_dict = json.load(f)
        return cls.from_dict(config_dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典

        Returns:
            Dict[str, Any]: 配置字典
        """
        return asdict(self)

    def to_json(self, json_path: str) -> None:
        """
        保存为JSON文件

        Args:
            json_path: JSON文件路径
        """
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

    def get_feature_dim(self, mode: str) -> int:
        """
        获取特征维度

        Args:
            mode: 'CSI' or 'RFF'

        Returns:
            int: 特征维度
        """
        if mode.upper() == 'CSI':
            # CSI模式：(N_selected - 1) * 2 (幅度差分 + 相位差分)
            return (self.N_SUBCARRIER_SELECTED - 1) * 2
        elif mode.upper() == 'RFF':
            return self.FEATURE_DIM_RFF
        else:
            raise ValueError(f"Unknown mode: {mode}, expected 'CSI' or 'RFF'")

    def get_computed_bch_blocks(self) -> int:
        """
        计算所需的BCH分块数

        Returns:
            int: BCH分块数
        """
        return (self.TARGET_BITS + self.BCH_K - 1) // self.BCH_K

    def __repr__(self) -> str:
        """字符串表示"""
        return (
            f"FeatureEncryptionConfig(\n"
            f"  M_FRAMES={self.M_FRAMES},\n"
            f"  N_SUBCARRIER_SELECTED={self.N_SUBCARRIER_SELECTED}/{self.N_SUBCARRIER_TOTAL},\n"
            f"  TARGET_BITS={self.TARGET_BITS},\n"
            f"  BCH({self.BCH_N},{self.BCH_K},{self.BCH_T}),\n"
            f"  VOTE_THRESHOLD={self.VOTE_THRESHOLD},\n"
            f"  KEY_LENGTH={self.KEY_LENGTH} bytes\n"
            f")"
        )


# 预定义的配置场景
class ConfigProfiles:
    """预定义的配置场景"""

    @staticmethod
    def default() -> FeatureEncryptionConfig:
        """默认配置"""
        return FeatureEncryptionConfig()

    @staticmethod
    def high_noise() -> FeatureEncryptionConfig:
        """高噪声环境配置"""
        return FeatureEncryptionConfig(
            M_FRAMES=8,
            VOTE_THRESHOLD=6,
            BCH_T=24,
        )

    @staticmethod
    def low_latency() -> FeatureEncryptionConfig:
        """低时延配置"""
        return FeatureEncryptionConfig(
            M_FRAMES=4,
            VOTE_THRESHOLD=3,
            TARGET_BITS=128,
            BCH_BLOCKS=1,
        )

    @staticmethod
    def high_security() -> FeatureEncryptionConfig:
        """高安全性配置"""
        return FeatureEncryptionConfig(
            TARGET_BITS=512,
            N_SUBCARRIER_SELECTED=48,
            KEY_LENGTH=64,
            BCH_BLOCKS=4,
        )


# 导出
__all__ = ['FeatureEncryptionConfig', 'ConfigProfiles']
