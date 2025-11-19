"""
同步服务统一接口
"""
import time
import secrets
import logging
from typing import Optional, List
import numpy as np

from .cluster_head import ClusterHead
from .validator_node import ValidatorNode
from .device_node import DeviceNode
from .key_rotation import KeyRotationManager
from .mat_manager import MATManager
from ..core.feature_config import FeatureConfig
from ..core.key_material import KeyMaterial
from ..auth.mat_token import MATToken
from ..network.election import ClusterElection
from ..network.gossip import GossipProtocol
from ..utils.logging_config import get_logger


logger = get_logger(__name__)


class SynchronizationService:
    """同步服务统一接口（供3.3.2认证模块调用）"""

    def __init__(self, node_type: str, node_id: bytes,
                 peer_validators: Optional[List[bytes]] = None,
                 delta_t: int = 30000,
                 beacon_interval: int = 5000,
                 domain: str = "FeatureAuth",
                 deterministic_for_testing: bool = False):
        """
        初始化同步服务

        Args:
            node_type: 节点类型: 'cluster_head', 'validator', 或 'device'
            node_id: 节点ID（6字节MAC地址）
            peer_validators: 其他验证节点列表（仅验证节点需要）
            delta_t: epoch周期(ms)，默认30000ms
            beacon_interval: 信标广播间隔(ms)，默认5000ms
            domain: 域标识，默认"FeatureAuth"（与3.2认证模块兼容）
            deterministic_for_testing: 是否启用确定性测试模式（用于单元测试）
        """
        if len(node_id) != 6:
            raise ValueError("node_id must be 6 bytes")

        self.node_type = node_type
        self.node_id = node_id
        self.peer_validators = peer_validators or []
        self.delta_t = delta_t
        self.beacon_interval = beacon_interval
        self.domain = domain
        self.deterministic_for_testing = deterministic_for_testing

        # 生成签名/验证密钥（简化实现，实际应使用密钥管理）
        self.signing_key = secrets.token_bytes(32)

        # 初始化节点
        if node_type == 'cluster_head':
            self.cluster_head = ClusterHead(
                node_id=node_id,
                delta_t=delta_t,
                beacon_interval=beacon_interval,
                signing_key=self.signing_key
            )
            self.validator = ValidatorNode(
                node_id=node_id,
                verification_key=self.signing_key
            )
            self.device = None
            self.is_cluster_head = True

        elif node_type == 'validator':
            self.cluster_head = None
            self.validator = ValidatorNode(
                node_id=node_id,
                verification_key=self.signing_key
            )
            self.device = None
            self.is_cluster_head = False

            # 初始化选举
            all_validators = [node_id] + self.peer_validators
            self.election = ClusterElection(
                node_id=node_id,
                all_validators=all_validators
            )

        elif node_type == 'device':
            self.cluster_head = None
            self.validator = None
            self.device = DeviceNode(node_id=node_id)
            self.is_cluster_head = False

        else:
            raise ValueError(f"Unknown node type: {node_type}")

        # 初始化密钥轮换管理器（验证节点和设备节点都需要）
        if self.validator:
            # 验证节点使用validator的epoch_state
            self.key_rotation = KeyRotationManager(
                epoch_state=self.validator.epoch_state,
                domain=self.domain,  # 使用配置的domain
                deterministic_for_testing=self.deterministic_for_testing
            )
        elif self.device:
            # 设备节点使用device的epoch_state
            self.key_rotation = KeyRotationManager(
                epoch_state=self.device.epoch_state,
                domain=self.domain,  # 使用配置的domain
                deterministic_for_testing=self.deterministic_for_testing
            )
        else:
            self.key_rotation = None

        # 初始化MAT管理器（仅验证节点）
        if node_type in ['cluster_head', 'validator']:
            validator_ids = [node_id] + self.peer_validators
            signing_keys = [self.signing_key] * len(validator_ids)  # 简化：使用相同密钥
            self.mat_manager = MATManager(
                validator_nodes=validator_ids,
                signing_keys=signing_keys
            )
        else:
            self.mat_manager = None

        # 初始化Gossip协议（仅验证节点）
        if node_type in ['cluster_head', 'validator'] and self.peer_validators:
            self.gossip = GossipProtocol(
                local_node=node_id,
                peer_nodes=self.peer_validators
            )
            # 设置回调
            if self.mat_manager:
                self.gossip.set_state_update_callback(
                    lambda revocations: self._on_gossip_revocation_update(revocations)
                )
        else:
            self.gossip = None

        logger.info(f"SynchronizationService initialized: type={node_type}, "
                   f"node_id={node_id.hex()}")

    def start(self):
        """启动同步服务"""
        logger.info(f"Starting {self.node_type} synchronization service")

        if self.node_type == 'cluster_head':
            # 启动簇首信标广播
            self.cluster_head.start()

        elif self.node_type == 'validator':
            # 启动选举
            winner = self.election.start_election()
            logger.info(f"Election result: {winner.hex()}")

            # 如果自己当选为簇首，启动信标广播
            if winner == self.node_id:
                self.cluster_head = ClusterHead(
                    node_id=self.node_id,
                    delta_t=self.delta_t,
                    beacon_interval=self.beacon_interval,
                    signing_key=self.signing_key
                )
                self.cluster_head.start()
                self.is_cluster_head = True

        # 启动Gossip（如果有）
        if self.gossip:
            self.gossip.start()

        logger.info(f"{self.node_type} synchronization service started")

    def stop(self):
        """停止同步服务"""
        logger.info(f"Stopping {self.node_type} synchronization service")

        if self.cluster_head:
            self.cluster_head.stop()

        if self.gossip:
            self.gossip.stop()

        logger.info(f"{self.node_type} synchronization service stopped")

    # ========== 对外接口（供3.3.2调用） ==========

    def get_current_epoch(self) -> int:
        """获取当前epoch"""
        # 优先返回cluster_head的epoch（如果是簇首节点）
        if self.cluster_head:
            return self.cluster_head.get_current_epoch()
        elif self.validator:
            return self.validator.get_current_epoch()
        elif self.device:
            return self.device.get_current_epoch()
        return 0

    def is_epoch_valid(self, epoch: int) -> bool:
        """
        检查epoch是否在容忍范围内

        Args:
            epoch: 时间窗编号

        Returns:
            是否有效
        """
        if self.validator:
            return self.validator.is_epoch_valid(epoch)
        elif self.device:
            return self.device.is_epoch_valid(epoch)
        return False

    def get_feature_config(self) -> Optional[FeatureConfig]:
        """获取当前特征配置"""
        # 优先返回cluster_head的配置（如果是簇首节点）
        if self.cluster_head:
            return self.cluster_head.get_feature_config()
        elif self.validator:
            return self.validator.get_feature_config()
        elif self.device:
            return self.device.epoch_state.current_config
        return None

    def get_key_material(self, device_mac: bytes, epoch: int) -> Optional[KeyMaterial]:
        """
        获取密钥材料（供3.3.2认证使用）

        Args:
            device_mac: 设备MAC地址
            epoch: 时间窗编号

        Returns:
            KeyMaterial或None
        """
        if not self.key_rotation:
            logger.error("Key rotation manager not available")
            return None

        return self.key_rotation.get_key_material(device_mac, epoch)

    def generate_or_get_key_material(self, device_mac: bytes, epoch: int,
                                    feature_vector: Optional[np.ndarray] = None,
                                    nonce: Optional[bytes] = None,
                                    validator_mac: Optional[bytes] = None) -> KeyMaterial:
        """
        生成或获取密钥材料

        如果已存在则返回，否则生成新的
        注意：使用FE的register模式，适用于设备端和验证端

        Args:
            device_mac: 设备MAC地址（6字节）
            epoch: 时间窗编号
            feature_vector: 特征向量（可选）
            nonce: 随机数（可选，默认随机生成）
            validator_mac: 验证节点MAC地址（可选，默认使用self.node_id）

        Returns:
            KeyMaterial对象
        """
        if not self.key_rotation:
            raise RuntimeError("Key rotation manager not available")

        # 默认使用本节点ID作为validator_mac
        if validator_mac is None:
            validator_mac = self.node_id

        # 先尝试获取
        existing = self.get_key_material(device_mac, epoch)
        if existing:
            now = int(time.time() * 1000)
            if existing.is_valid(now):
                return existing

        # 不存在或已过期，生成新的
        if nonce is None:
            nonce = secrets.token_bytes(16)

        return self.key_rotation.generate_key_material(
            device_mac=device_mac,
            validator_mac=validator_mac,
            epoch=epoch,
            feature_vector=feature_vector,
            nonce=nonce
        )

    def authenticate_and_recover_key_material(self, device_mac: bytes, epoch: int,
                                             feature_vector: np.ndarray,
                                             nonce: bytes) -> Optional[KeyMaterial]:
        """
        认证并恢复密钥材料（验证端使用）

        使用FE的authenticate模式，可以从略有不同的特征向量中恢复相同的密钥
        （通过BCH纠错）。适用于验证端认证设备时使用。

        Args:
            device_mac: 设备MAC地址（6字节）
            epoch: 时间窗编号
            feature_vector: 特征向量（验证端测量的CSI）
            nonce: 随机数（16字节）

        Returns:
            KeyMaterial对象，如果认证失败则返回None
        """
        if not self.key_rotation:
            raise RuntimeError("Key rotation manager not available")

        # 先尝试获取已有的
        existing = self.get_key_material(device_mac, epoch)
        if existing:
            now = int(time.time() * 1000)
            if existing.is_valid(now):
                return existing

        # 不存在或已过期，使用authenticate模式恢复
        return self.key_rotation.authenticate_key_material(
            device_mac=device_mac,
            validator_mac=self.node_id,
            epoch=epoch,
            feature_vector=feature_vector,
            nonce=nonce
        )

    def issue_mat_token(self, device_pseudonym: bytes, epoch: int,
                       session_key: bytes, ttl: int = 30000) -> MATToken:
        """
        签发MAT令牌（仅验证节点）

        Args:
            device_pseudonym: 设备伪名（12字节）
            epoch: 绑定的epoch
            session_key: 会话密钥（32字节）
            ttl: 有效期(ms)

        Returns:
            MATToken对象
        """
        if not self.mat_manager:
            raise RuntimeError("MAT manager not initialized")

        return self.mat_manager.issue_mat(device_pseudonym, epoch, ttl)

    def verify_mat_token(self, mat: MATToken) -> bool:
        """
        验证MAT令牌（仅验证节点）

        Args:
            mat: MAT令牌

        Returns:
            验证是否通过
        """
        if not self.mat_manager:
            raise RuntimeError("MAT manager not initialized")

        current_epoch = self.get_current_epoch()
        return self.mat_manager.verify_mat(mat, current_epoch)

    def revoke_mat_token(self, mat_id: bytes):
        """
        吊销MAT令牌（仅验证节点）

        Args:
            mat_id: 令牌ID（16字节）
        """
        if not self.mat_manager:
            raise RuntimeError("MAT manager not initialized")

        self.mat_manager.revoke_mat(mat_id)

        # 同步到Gossip
        if self.gossip:
            self.gossip.add_revocation(mat_id)

    def is_synchronized(self) -> bool:
        """检查是否已同步"""
        if self.validator:
            return self.validator.is_synchronized()
        elif self.device:
            return self.device.check_synchronization()
        return True  # 簇首总是同步的

    # ========== 内部方法 ==========

    def _on_gossip_revocation_update(self, new_revocations: set):
        """处理Gossip吊销更新"""
        if self.mat_manager:
            for mat_id in new_revocations:
                self.mat_manager.revoke_mat(mat_id)
                logger.info(f"Revoked MAT {mat_id.hex()} via Gossip")

    def __repr__(self) -> str:
        return (
            f"SynchronizationService(type={self.node_type}, "
            f"node_id={self.node_id.hex()}, "
            f"epoch={self.get_current_epoch()}, "
            f"synchronized={self.is_synchronized()})"
        )
