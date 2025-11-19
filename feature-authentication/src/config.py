"""
认证模块配置管理

提供两种认证模式的配置参数管理。
"""

from dataclasses import dataclass, field
from typing import Optional
import logging


@dataclass
class AuthConfig:
    """认证配置类

    管理模式一（RFF快速认证）和模式二（强认证）的所有配置参数。
    """

    # ==================== 模式选择 ====================
    MODE1_ENABLED: bool = False  # 模式一：RFF快速认证（可选）
    MODE2_ENABLED: bool = True   # 模式二：强认证（默认启用）

    # ==================== 模式一配置 ====================
    # RFF快速认证相关
    RFF_THRESHOLD: float = 0.8          # RFF得分阈值（0.0-1.0）
    TOKEN_FAST_TTL: int = 60            # Token_fast有效期（秒）
    K_MGMT_LENGTH: int = 32             # 管理密钥长度（字节）

    # ==================== 模式二配置 ====================
    # 强认证相关
    TAG_LENGTH: int = 16                # 认证标签长度（字节，128位）
    PSEUDO_LENGTH: int = 12             # 伪名长度（字节，96位）
    MAT_TTL: int = 300                  # MAT有效期（秒，5分钟）
    MAT_ID_LENGTH: int = 16             # MAT ID长度（字节）
    SIGNATURE_LENGTH: int = 32          # 签名长度（字节，256位）

    # 上下文参数
    NONCE_LENGTH: int = 16              # nonce长度（字节）
    EPOCH_MAX: int = 2**32 - 1          # epoch最大值

    # ==================== 密码学配置 ====================
    HASH_ALGORITHM: str = 'blake3'      # 哈希算法：'blake3' or 'sha256'
    MAC_ALGORITHM: str = 'blake3'       # MAC算法：'blake3' or 'hmac-sha256'

    # ==================== 性能配置 ====================
    MAX_DEVICES: int = 10000            # 最大注册设备数
    PSEUDO_CACHE_SIZE: int = 1000       # 伪名缓存大小

    # ==================== 日志配置 ====================
    LOG_LEVEL: str = 'INFO'             # 日志级别
    LOG_FILE: Optional[str] = None      # 日志文件路径（None表示只输出到控制台）
    LOG_FORMAT: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    def __post_init__(self):
        """初始化后验证"""
        self.validate()

    def validate(self) -> bool:
        """验证配置参数

        Returns:
            bool: 配置是否有效

        Raises:
            ValueError: 配置参数无效时
        """
        # 验证模式选择
        if not self.MODE1_ENABLED and not self.MODE2_ENABLED:
            raise ValueError("At least one authentication mode must be enabled")

        # 验证模式一参数
        if self.MODE1_ENABLED:
            if not 0.0 <= self.RFF_THRESHOLD <= 1.0:
                raise ValueError(f"RFF_THRESHOLD must be in [0.0, 1.0], got {self.RFF_THRESHOLD}")

            if self.TOKEN_FAST_TTL <= 0:
                raise ValueError(f"TOKEN_FAST_TTL must be positive, got {self.TOKEN_FAST_TTL}")

            if self.K_MGMT_LENGTH not in [16, 32]:
                raise ValueError(f"K_MGMT_LENGTH must be 16 or 32, got {self.K_MGMT_LENGTH}")

        # 验证模式二参数
        if self.MODE2_ENABLED:
            if self.TAG_LENGTH not in [8, 12, 16, 20, 24, 32]:
                raise ValueError(f"TAG_LENGTH must be 8-32 bytes, got {self.TAG_LENGTH}")

            if self.PSEUDO_LENGTH not in [8, 12, 16]:
                raise ValueError(f"PSEUDO_LENGTH must be 8-16 bytes, got {self.PSEUDO_LENGTH}")

            if self.MAT_TTL <= 0:
                raise ValueError(f"MAT_TTL must be positive, got {self.MAT_TTL}")

            if self.NONCE_LENGTH not in [12, 16, 24, 32]:
                raise ValueError(f"NONCE_LENGTH must be 12-32 bytes, got {self.NONCE_LENGTH}")

        # 验证密码学配置
        if self.HASH_ALGORITHM not in ['blake3', 'sha256']:
            raise ValueError(f"HASH_ALGORITHM must be 'blake3' or 'sha256', got {self.HASH_ALGORITHM}")

        if self.MAC_ALGORITHM not in ['blake3', 'hmac-sha256']:
            raise ValueError(f"MAC_ALGORITHM must be 'blake3' or 'hmac-sha256', got {self.MAC_ALGORITHM}")

        # 验证日志级别
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.LOG_LEVEL not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}, got {self.LOG_LEVEL}")

        return True

    @staticmethod
    def default() -> 'AuthConfig':
        """默认配置

        Returns:
            AuthConfig: 默认配置实例
        """
        return AuthConfig()

    @staticmethod
    def high_security() -> 'AuthConfig':
        """高安全配置

        Returns:
            AuthConfig: 高安全配置实例
        """
        return AuthConfig(
            MODE1_ENABLED=False,      # 只使用强认证
            MODE2_ENABLED=True,
            TAG_LENGTH=32,            # 更长的标签
            PSEUDO_LENGTH=16,         # 更长的伪名
            MAT_TTL=180,              # 更短的有效期（3分钟）
            SIGNATURE_LENGTH=32,
        )

    @staticmethod
    def low_latency() -> 'AuthConfig':
        """低延迟配置

        Returns:
            AuthConfig: 低延迟配置实例
        """
        return AuthConfig(
            MODE1_ENABLED=True,       # 启用快速认证
            MODE2_ENABLED=True,
            RFF_THRESHOLD=0.75,       # 稍低的阈值
            TOKEN_FAST_TTL=30,        # 更短的快速令牌
            TAG_LENGTH=12,            # 更短的标签（性能优先）
            MAT_TTL=600,              # 更长的MAT（减少重认证）
        )

    @staticmethod
    def iot_optimized() -> 'AuthConfig':
        """IoT优化配置

        适合资源受限的物联网设备。

        Returns:
            AuthConfig: IoT优化配置实例
        """
        return AuthConfig(
            MODE1_ENABLED=True,
            MODE2_ENABLED=True,
            RFF_THRESHOLD=0.7,
            TOKEN_FAST_TTL=120,       # 更长的快速令牌（减少认证频率）
            TAG_LENGTH=12,            # 较短的标签
            PSEUDO_LENGTH=8,          # 较短的伪名
            MAT_TTL=600,
            LOG_LEVEL='WARNING',      # 减少日志输出
        )

    def __repr__(self) -> str:
        """字符串表示"""
        return (
            f"AuthConfig(\n"
            f"  Modes: Mode1={'ON' if self.MODE1_ENABLED else 'OFF'}, "
            f"Mode2={'ON' if self.MODE2_ENABLED else 'OFF'}\n"
            f"  Mode1: RFF_THRESHOLD={self.RFF_THRESHOLD}, TTL={self.TOKEN_FAST_TTL}s\n"
            f"  Mode2: TAG_LEN={self.TAG_LENGTH}B, PSEUDO_LEN={self.PSEUDO_LENGTH}B, "
            f"MAT_TTL={self.MAT_TTL}s\n"
            f"  Crypto: HASH={self.HASH_ALGORITHM}, MAC={self.MAC_ALGORITHM}\n"
            f"  Log: LEVEL={self.LOG_LEVEL}\n"
            f")"
        )


# 导出
__all__ = ['AuthConfig']
