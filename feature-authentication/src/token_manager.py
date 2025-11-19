"""
令牌管理模块

管理TokenFast（模式一）和MAT（模式二）的生成、验证和存储。
"""

import secrets
import struct
import time
import logging
from typing import Dict, Optional, Tuple

from .config import AuthConfig
from .common import TokenFast, MAT
from .utils import compute_mac, constant_time_compare, format_bytes_preview


logger = logging.getLogger(__name__)


class TokenFastManager:
    """快速令牌管理器（模式一）

    管理TokenFast的签发和验证。
    """

    def __init__(self, config: AuthConfig, k_mgmt: bytes):
        """初始化

        Args:
            config: 配置对象
            k_mgmt: 管理密钥（16或32字节）

        Raises:
            ValueError: k_mgmt长度无效
        """
        self.config = config

        if len(k_mgmt) not in [16, 32]:
            raise ValueError(f"k_mgmt must be 16 or 32 bytes, got {len(k_mgmt)}")

        self.k_mgmt = k_mgmt

        # 令牌存储：dev_id -> TokenFast
        self._token_store: Dict[bytes, TokenFast] = {}

        logger.info(f"TokenFastManager initialized with k_mgmt length={len(k_mgmt)}")

    def issue_token_fast(
        self,
        dev_id: bytes,
        policy: str = "default"
    ) -> TokenFast:
        """签发快速令牌

        Args:
            dev_id: 设备标识（6字节）
            policy: 策略标识

        Returns:
            TokenFast: 签发的令牌

        Raises:
            ValueError: dev_id无效
        """
        logger.info(f"Issuing TokenFast for device {dev_id.hex()}")
        logger.debug(f"  Policy: {policy}, TTL: {self.config.TOKEN_FAST_TTL}s")

        if len(dev_id) != 6:
            raise ValueError(f"dev_id must be 6 bytes, got {len(dev_id)}")

        # 当前时间和过期时间
        t_start = int(time.time())
        t_expire = t_start + self.config.TOKEN_FAST_TTL

        logger.debug(f"  t_start: {t_start}, t_expire: {t_expire}")

        # 计算MAC
        # MAC = MAC(K_mgmt, dev_id || t_start || t_expire || policy)
        policy_bytes = policy.encode('utf-8')
        msg = (
            dev_id +
            struct.pack('<I', t_start) +
            struct.pack('<I', t_expire) +
            policy_bytes
        )

        mac = compute_mac(
            key=self.k_mgmt,
            data=msg,
            algorithm=self.config.MAC_ALGORITHM,
            length=16
        )

        logger.debug(f"  MAC computed: {format_bytes_preview(mac, 16)}")

        # 创建令牌
        token = TokenFast(
            dev_id=dev_id,
            t_start=t_start,
            t_expire=t_expire,
            policy=policy,
            mac=mac
        )

        # 存储令牌
        self._token_store[dev_id] = token

        logger.info(f"✓ TokenFast issued: expires at {t_expire} (in {self.config.TOKEN_FAST_TTL}s)")
        return token

    def verify_token_fast(
        self,
        token: TokenFast,
        current_time: Optional[int] = None
    ) -> bool:
        """验证快速令牌

        Args:
            token: 待验证的令牌
            current_time: 当前时间（Unix时间戳），None表示使用系统时间

        Returns:
            bool: 是否验证通过
        """
        logger.info(f"Verifying TokenFast for device {token.dev_id.hex()}")

        if current_time is None:
            current_time = int(time.time())

        logger.debug(f"  Current time: {current_time}, Token expires: {token.t_expire}")

        # 检查过期
        if current_time > token.t_expire:
            logger.warning(f"✗ Token expired (current={current_time}, expire={token.t_expire})")
            return False

        if current_time < token.t_start:
            logger.warning(f"✗ Token not yet valid (current={current_time}, start={token.t_start})")
            return False

        logger.debug(f"✓ Time check passed")

        # 重新计算MAC
        policy_bytes = token.policy.encode('utf-8')
        msg = (
            token.dev_id +
            struct.pack('<I', token.t_start) +
            struct.pack('<I', token.t_expire) +
            policy_bytes
        )

        expected_mac = compute_mac(
            key=self.k_mgmt,
            data=msg,
            algorithm=self.config.MAC_ALGORITHM,
            length=16
        )

        logger.debug(f"  Expected MAC: {format_bytes_preview(expected_mac, 16)}")
        logger.debug(f"  Received MAC: {format_bytes_preview(token.mac, 16)}")

        # 常时比较
        if not constant_time_compare(expected_mac, token.mac):
            logger.error(f"✗ MAC verification failed")
            return False

        logger.info(f"✓✓✓ TokenFast verification passed")
        return True

    def revoke_token(self, dev_id: bytes) -> bool:
        """撤销令牌

        Args:
            dev_id: 设备标识

        Returns:
            bool: 是否成功撤销
        """
        if dev_id in self._token_store:
            del self._token_store[dev_id]
            logger.info(f"TokenFast revoked for device {dev_id.hex()}")
            return True
        else:
            logger.warning(f"No TokenFast found for device {dev_id.hex()}")
            return False


class MATManager:
    """准入令牌管理器（模式二）

    管理MAT的签发和验证。
    """

    def __init__(self, config: AuthConfig, issuer_id: bytes, issuer_key: bytes):
        """初始化

        Args:
            config: 配置对象
            issuer_id: 签发者标识（6字节MAC地址）
            issuer_key: 签发者密钥（32字节）

        Raises:
            ValueError: 参数无效
        """
        self.config = config

        if len(issuer_id) != 6:
            raise ValueError(f"issuer_id must be 6 bytes, got {len(issuer_id)}")

        if len(issuer_key) != 32:
            raise ValueError(f"issuer_key must be 32 bytes, got {len(issuer_key)}")

        self.issuer_id = issuer_id
        self.issuer_key = issuer_key

        # MAT存储：mat_id -> (MAT, issue_time)
        self._mat_store: Dict[bytes, Tuple[MAT, int]] = {}

        logger.info(f"MATManager initialized for issuer {issuer_id.hex()}")

    def issue_mat(
        self,
        dev_pseudo: bytes,
        epoch: int
    ) -> MAT:
        """签发准入令牌

        Args:
            dev_pseudo: 设备伪名（12字节）
            epoch: 时间窗编号

        Returns:
            MAT: 签发的准入令牌

        Raises:
            ValueError: 参数无效
        """
        logger.info(f"=" * 60)
        logger.info(f"Issuing MAT for device pseudo={format_bytes_preview(dev_pseudo, 24)}")
        logger.debug(f"  Epoch: {epoch}, TTL: {self.config.MAT_TTL}s")

        if len(dev_pseudo) != 12:
            raise ValueError(f"dev_pseudo must be 12 bytes, got {len(dev_pseudo)}")

        if epoch < 0 or epoch > 2**32 - 1:
            raise ValueError(f"epoch must be in [0, 2^32-1], got {epoch}")

        # 生成唯一MAT ID
        mat_id = secrets.token_bytes(16)
        logger.debug(f"  MAT ID: {format_bytes_preview(mat_id, 32)}")

        # 计算签名
        # signature = MAC(issuer_key, issuer_id || dev_pseudo || epoch || ttl || mat_id)
        msg = (
            self.issuer_id +
            dev_pseudo +
            struct.pack('<I', epoch) +
            struct.pack('<I', self.config.MAT_TTL) +
            mat_id
        )

        logger.debug(f"  Signing message of {len(msg)} bytes")

        signature = compute_mac(
            key=self.issuer_key,
            data=msg,
            algorithm=self.config.MAC_ALGORITHM,
            length=32
        )

        logger.debug(f"  Signature: {format_bytes_preview(signature, 32)}")

        # 创建MAT
        mat = MAT(
            issuer=self.issuer_id,
            dev_pseudo=dev_pseudo,
            epoch=epoch,
            ttl=self.config.MAT_TTL,
            mat_id=mat_id,
            signature=signature
        )

        # 存储MAT
        issue_time = int(time.time())
        self._mat_store[mat_id] = (mat, issue_time)

        logger.info(f"✓ MAT issued: ID={format_bytes_preview(mat_id, 16)}, TTL={self.config.MAT_TTL}s")
        logger.info(f"=" * 60)

        return mat

    def verify_mat(
        self,
        mat: MAT,
        current_time: Optional[int] = None
    ) -> bool:
        """验证准入令牌

        Args:
            mat: 待验证的MAT
            current_time: 当前时间（Unix时间戳），None表示使用系统时间

        Returns:
            bool: 是否验证通过
        """
        logger.info(f"=" * 60)
        logger.info(f"Verifying MAT: ID={format_bytes_preview(mat.mat_id, 16)}")
        logger.debug(f"  Dev pseudo: {format_bytes_preview(mat.dev_pseudo, 24)}")
        logger.debug(f"  Epoch: {mat.epoch}, TTL: {mat.ttl}s")

        # 检查签发者
        if mat.issuer != self.issuer_id:
            logger.warning(f"✗ Issuer mismatch")
            logger.debug(f"  Expected: {self.issuer_id.hex()}")
            logger.debug(f"  Got: {mat.issuer.hex()}")
            return False

        logger.debug(f"✓ Issuer check passed")

        # 检查是否在存储中
        if mat.mat_id not in self._mat_store:
            logger.warning(f"✗ MAT not found in store (unknown or revoked)")
            return False

        stored_mat, issue_time = self._mat_store[mat.mat_id]

        logger.debug(f"✓ MAT found in store, issued at {issue_time}")

        # 检查过期
        if current_time is None:
            current_time = int(time.time())

        expire_time = issue_time + mat.ttl

        logger.debug(f"  Current: {current_time}, Expire: {expire_time}")

        if current_time > expire_time:
            logger.warning(f"✗ MAT expired (current={current_time}, expire={expire_time})")
            return False

        logger.debug(f"✓ Time check passed")

        # 重新计算签名
        msg = (
            mat.issuer +
            mat.dev_pseudo +
            struct.pack('<I', mat.epoch) +
            struct.pack('<I', mat.ttl) +
            mat.mat_id
        )

        expected_signature = compute_mac(
            key=self.issuer_key,
            data=msg,
            algorithm=self.config.MAC_ALGORITHM,
            length=32
        )

        logger.debug(f"  Expected signature: {format_bytes_preview(expected_signature, 32)}")
        logger.debug(f"  Received signature: {format_bytes_preview(mat.signature, 32)}")

        # 常时比较
        if not constant_time_compare(expected_signature, mat.signature):
            logger.error(f"✗ Signature verification failed")
            return False

        logger.info(f"✓✓✓ MAT verification passed")
        logger.info(f"=" * 60)

        return True

    def revoke_mat(self, mat_id: bytes) -> bool:
        """撤销MAT

        Args:
            mat_id: MAT唯一标识

        Returns:
            bool: 是否成功撤销
        """
        if mat_id in self._mat_store:
            del self._mat_store[mat_id]
            logger.info(f"MAT revoked: {format_bytes_preview(mat_id, 16)}")
            return True
        else:
            logger.warning(f"No MAT found for ID {format_bytes_preview(mat_id, 16)}")
            return False

    def cleanup_expired_mats(self, current_time: Optional[int] = None) -> int:
        """清理过期的MAT

        Args:
            current_time: 当前时间（Unix时间戳）

        Returns:
            int: 清理的MAT数量
        """
        if current_time is None:
            current_time = int(time.time())

        logger.info(f"Cleaning up expired MATs (current_time={current_time})")

        expired_ids = []
        for mat_id, (mat, issue_time) in self._mat_store.items():
            expire_time = issue_time + mat.ttl
            if current_time > expire_time:
                expired_ids.append(mat_id)

        for mat_id in expired_ids:
            del self._mat_store[mat_id]

        logger.info(f"Cleaned up {len(expired_ids)} expired MATs")

        return len(expired_ids)


# 导出
__all__ = [
    'TokenFastManager',
    'MATManager',
]
