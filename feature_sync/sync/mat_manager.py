"""
MAT令牌管理模块
"""
import time
import secrets
import logging
from typing import Dict, Set, List, Optional

from ..auth.mat_token import MATToken
from ..utils.logging_config import get_logger


logger = get_logger(__name__)


class MATManager:
    """MAT令牌管理器"""

    def __init__(self, validator_nodes: List[bytes], signing_keys: List[bytes],
                 region: str = "default"):
        """
        初始化MAT管理器

        Args:
            validator_nodes: 验证节点ID列表（每个6字节）
            signing_keys: 对应的签名密钥列表（每个32字节）
            region: 区域标识
        """
        if len(validator_nodes) != len(signing_keys):
            raise ValueError("validator_nodes and signing_keys must have same length")

        self.validator_nodes = validator_nodes
        self.signing_keys = signing_keys
        self.region = region

        # 已签发的令牌
        self.issued_tokens: Dict[bytes, MATToken] = {}  # {mat_id: MATToken}

        # 吊销列表
        self.revoked_tokens: Set[bytes] = set()  # {mat_id}

        logger.info(f"MATManager initialized: validators={len(validator_nodes)}, "
                   f"region={region}")

    def issue_mat(self, device_pseudonym: bytes, epoch: int, ttl: int = 30000) -> MATToken:
        """
        签发MAT令牌

        Args:
            device_pseudonym: 设备伪名(12字节)
            epoch: 绑定的epoch
            ttl: 有效期(ms)，默认30000ms(30秒)

        Returns:
            MATToken对象
        """
        if len(device_pseudonym) != 12:
            raise ValueError("device_pseudonym must be 12 bytes")

        now = int(time.time() * 1000)

        # 创建令牌
        mat = MATToken(
            issuer_set=self.validator_nodes.copy(),
            device_pseudonym=device_pseudonym,
            epoch=epoch,
            ttl=ttl,
            region=self.region,
            mat_id=secrets.token_bytes(16),
            issued_at=now,
            signature=b''  # 待签名
        )

        # 聚合签名
        mat.sign_with_keys(self.signing_keys)

        # 记录
        self.issued_tokens[mat.mat_id] = mat

        logger.info(f"MAT issued: id={mat.mat_id.hex()}, "
                   f"pseudonym={device_pseudonym.hex()}, epoch={epoch}")

        return mat

    def verify_mat(self, mat: MATToken, current_epoch: int) -> bool:
        """
        验证MAT令牌

        Args:
            mat: MAT令牌
            current_epoch: 当前epoch

        Returns:
            验证是否通过
        """
        now = int(time.time() * 1000)

        # 1. 检查是否被吊销
        if mat.mat_id in self.revoked_tokens:
            logger.warning(f"MAT {mat.mat_id.hex()} is revoked")
            return False

        # 2. 检查有效性（时间和epoch）
        if not mat.is_valid(now, current_epoch):
            logger.warning(f"MAT {mat.mat_id.hex()} is invalid: "
                          f"now={now}, issued_at={mat.issued_at}, ttl={mat.ttl}, "
                          f"current_epoch={current_epoch}, mat_epoch={mat.epoch}")
            return False

        # 3. 验证签名
        if not mat.verify_with_keys(self.signing_keys):
            logger.warning(f"MAT {mat.mat_id.hex()} signature verification failed")
            return False

        logger.debug(f"MAT {mat.mat_id.hex()} verified successfully")
        return True

    def revoke_mat(self, mat_id: bytes):
        """
        吊销MAT令牌

        Args:
            mat_id: 令牌ID(16字节)
        """
        self.revoked_tokens.add(mat_id)
        logger.info(f"MAT {mat_id.hex()} revoked")

    def revoke_mat_by_pseudonym(self, device_pseudonym: bytes):
        """
        根据设备伪名吊销所有相关MAT

        Args:
            device_pseudonym: 设备伪名
        """
        count = 0
        for mat_id, mat in self.issued_tokens.items():
            if mat.device_pseudonym == device_pseudonym:
                self.revoke_mat(mat_id)
                count += 1

        logger.info(f"Revoked {count} MATs for pseudonym {device_pseudonym.hex()}")

    def rotate_mats_on_epoch_change(self, new_epoch: int):
        """
        epoch切换时轮换MAT

        清理旧epoch的MAT

        Args:
            new_epoch: 新的epoch
        """
        # 清理旧MAT（epoch < new_epoch - 1的）
        old_mats = [
            mat_id for mat_id, mat in self.issued_tokens.items()
            if mat.epoch < new_epoch - 1
        ]

        for mat_id in old_mats:
            del self.issued_tokens[mat_id]

        logger.info(f"Cleaned up {len(old_mats)} old MATs for epoch {new_epoch}")

        # 清理旧的吊销记录（可选，避免无限增长）
        # TODO: 实现吊销列表的滑动窗口清理

    def get_active_mat_count(self) -> int:
        """获取活跃的MAT数量"""
        return len(self.issued_tokens)

    def get_revoked_count(self) -> int:
        """获取吊销的MAT数量"""
        return len(self.revoked_tokens)

    def get_revocation_list(self) -> List[bytes]:
        """
        获取吊销列表

        Returns:
            吊销的MAT ID列表
        """
        return list(self.revoked_tokens)

    def sync_revocation_list(self, peer_revocations: List[bytes]):
        """
        同步吊销列表（用于Gossip协议）

        Args:
            peer_revocations: 来自对等节点的吊销列表
        """
        new_revocations = set(peer_revocations) - self.revoked_tokens

        if new_revocations:
            self.revoked_tokens.update(new_revocations)
            logger.info(f"Synced {len(new_revocations)} new revocations from peer")
