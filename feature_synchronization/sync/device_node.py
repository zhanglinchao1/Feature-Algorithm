"""
设备节点模块
"""
import time
import logging
from typing import Optional

from ..core.beacon import SyncBeacon
from ..core.epoch_state import EpochState
from ..utils.logging_config import get_logger


logger = get_logger(__name__)


class DeviceNode:
    """设备节点"""

    def __init__(self, node_id: bytes, beacon_timeout: int = 15000):
        """
        初始化设备节点

        Args:
            node_id: 节点ID（6字节MAC地址）
            beacon_timeout: 信标超时时间(ms)，默认15000ms(15秒)
        """
        if len(node_id) != 6:
            raise ValueError("node_id must be 6 bytes")

        self.node_id = node_id
        self.beacon_timeout = beacon_timeout

        # epoch状态（简化版，设备节点不需要维护密钥）
        self.epoch_state = EpochState(
            current_epoch=0,
            epoch_start_time=0,
            epoch_duration=30000,
            current_config=None,
            tolerated_epochs=set(),
            active_keys={},  # 设备节点不维护其他设备的密钥
            last_beacon_time=0,
            is_synchronized=False
        )

        # 初始化容忍窗口
        self.epoch_state.update_tolerated_epochs(0)

        logger.info(f"DeviceNode initialized: node_id={node_id.hex()}")

    def on_beacon_received(self, beacon: SyncBeacon) -> bool:
        """
        处理收到的信标

        Args:
            beacon: 收到的信标

        Returns:
            处理是否成功
        """
        logger.debug(f"Device received beacon: epoch={beacon.epoch}")

        now = int(time.time() * 1000)
        self.epoch_state.last_beacon_time = now

        # 同步到新epoch
        if beacon.epoch > self.epoch_state.current_epoch:
            self.epoch_state.update_epoch(
                new_epoch=beacon.epoch,
                epoch_start_time=beacon.timestamp,
                epoch_duration=beacon.delta_t,
                config=beacon.feature_config
            )
            logger.info(f"Device synced to epoch {beacon.epoch}")

        # 更新容忍窗口
        self.epoch_state.update_tolerated_epochs(beacon.epoch)

        self.epoch_state.is_synchronized = True
        return True

    def check_synchronization(self) -> bool:
        """
        检查同步状态

        Returns:
            是否同步
        """
        now = int(time.time() * 1000)

        if now - self.epoch_state.last_beacon_time > self.beacon_timeout:
            logger.warning("Device beacon timeout")
            self.epoch_state.is_synchronized = False
            return False

        return self.epoch_state.is_synchronized

    def get_current_epoch(self) -> int:
        """获取当前epoch"""
        return self.epoch_state.current_epoch

    def is_epoch_valid(self, epoch: int) -> bool:
        """检查epoch是否有效"""
        return self.epoch_state.is_epoch_valid(epoch)
