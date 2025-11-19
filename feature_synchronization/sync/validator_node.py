"""
验证节点模块
"""
import time
import logging
from typing import Optional

from ..core.beacon import SyncBeacon
from ..core.epoch_state import EpochState
from ..core.feature_config import FeatureConfig
from ..utils.logging_config import get_logger


logger = get_logger(__name__)


class ValidatorNode:
    """验证节点"""

    def __init__(self, node_id: bytes, beacon_timeout: int = 15000,
                 verification_key: Optional[bytes] = None):
        """
        初始化验证节点

        Args:
            node_id: 节点ID（6字节MAC地址）
            beacon_timeout: 信标超时时间(ms)，默认15000ms(15秒)
            verification_key: 签名验证密钥（可选）
        """
        if len(node_id) != 6:
            raise ValueError("node_id must be 6 bytes")

        self.node_id = node_id
        self.beacon_timeout = beacon_timeout
        self.verification_key = verification_key

        # epoch状态
        self.epoch_state = EpochState(
            current_epoch=0,
            epoch_start_time=0,
            epoch_duration=30000,  # 默认30秒
            current_config=None,
            tolerated_epochs=set(),
            active_keys={},
            last_beacon_time=0,
            is_synchronized=False
        )

        # 本地推进计数器
        self.local_progression_count = 0
        self.max_local_progression_epochs = 5

        logger.info(f"ValidatorNode initialized: node_id={node_id.hex()}, "
                   f"beacon_timeout={beacon_timeout}ms")

    def on_beacon_received(self, beacon: SyncBeacon) -> bool:
        """
        处理收到的信标

        Args:
            beacon: 收到的信标

        Returns:
            处理是否成功
        """
        logger.debug(f"Received beacon: {beacon}")

        # 1. 验证签名
        if self.verification_key and not beacon.verify(self.verification_key):
            logger.warning("Beacon signature verification failed")
            return False

        # 2. 更新最后收到信标的时间
        now = int(time.time() * 1000)
        self.epoch_state.last_beacon_time = now

        # 3. 检查是否需要同步到新epoch
        if beacon.epoch > self.epoch_state.current_epoch:
            self._sync_to_epoch(beacon)
        elif beacon.epoch < self.epoch_state.current_epoch - 1:
            # 信标过旧，可能网络分区恢复
            logger.warning(f"Received old beacon: beacon_epoch={beacon.epoch}, "
                          f"current_epoch={self.epoch_state.current_epoch}")
            return False

        # 4. 更新容忍窗口
        self.epoch_state.update_tolerated_epochs(beacon.epoch)

        # 5. 同步特征配置
        if self.epoch_state.current_config is None or \
           beacon.feature_config.config_id != self.epoch_state.current_config.config_id:
            self._sync_feature_config(beacon.feature_config)

        # 6. 标记为已同步
        self.epoch_state.is_synchronized = True
        self.local_progression_count = 0  # 重置本地推进计数

        return True

    def _sync_to_epoch(self, beacon: SyncBeacon):
        """
        同步到新的epoch

        Args:
            beacon: 同步信标
        """
        old_epoch = self.epoch_state.current_epoch
        new_epoch = beacon.epoch

        logger.info(f"Syncing from epoch {old_epoch} to {new_epoch}")

        # 更新epoch状态
        self.epoch_state.update_epoch(
            new_epoch=new_epoch,
            epoch_start_time=beacon.timestamp,
            epoch_duration=beacon.delta_t,
            config=beacon.feature_config
        )

    def _sync_feature_config(self, config: FeatureConfig):
        """
        同步特征配置

        Args:
            config: 特征配置
        """
        # 验证摘要
        expected_digest = config.compute_digest()
        if config.digest != expected_digest:
            logger.error("Feature config digest mismatch")
            return

        self.epoch_state.current_config = config
        logger.info(f"Feature config synced: version={config.version}")

    def check_synchronization(self) -> bool:
        """
        检查同步状态

        Returns:
            是否同步
        """
        now = int(time.time() * 1000)

        # 检查信标超时
        if now - self.epoch_state.last_beacon_time > self.beacon_timeout:
            logger.warning("Beacon timeout detected")
            self.epoch_state.is_synchronized = False
            self._enter_local_progression()
            return False

        return self.epoch_state.is_synchronized

    def _enter_local_progression(self):
        """进入本地epoch推进模式"""
        now = int(time.time() * 1000)

        # 检查是否应该推进epoch
        if not self.epoch_state.should_advance_epoch(now):
            return

        # 检查是否达到本地推进上限
        if self.local_progression_count >= self.max_local_progression_epochs:
            logger.error(f"Reached max local progression limit: {self.max_local_progression_epochs}")
            return

        # 推进epoch
        epochs_to_advance = (now - self.epoch_state.epoch_start_time) // self.epoch_state.epoch_duration

        for _ in range(int(epochs_to_advance)):
            self.epoch_state.current_epoch += 1
            self.epoch_state.epoch_start_time += self.epoch_state.epoch_duration
            self.local_progression_count += 1

            logger.info(f"Local epoch progression to {self.epoch_state.current_epoch} "
                       f"(count={self.local_progression_count})")

        # 更新容忍窗口
        self.epoch_state.update_tolerated_epochs(self.epoch_state.current_epoch)

    def force_resynchronization(self):
        """强制重新同步"""
        logger.info("Forcing resynchronization")

        # 重置状态
        self.epoch_state.is_synchronized = False
        self.local_progression_count = 0

        # 清空密钥（需要重新认证）
        self.epoch_state.active_keys.clear()

    def get_current_epoch(self) -> int:
        """获取当前epoch"""
        return self.epoch_state.current_epoch

    def is_epoch_valid(self, epoch: int) -> bool:
        """
        检查epoch是否有效

        Args:
            epoch: 要检查的epoch

        Returns:
            是否有效
        """
        return self.epoch_state.is_epoch_valid(epoch)

    def get_feature_config(self) -> Optional[FeatureConfig]:
        """获取当前特征配置"""
        return self.epoch_state.current_config

    def is_synchronized(self) -> bool:
        """检查是否已同步"""
        return self.epoch_state.is_synchronized
