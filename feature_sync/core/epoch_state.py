"""
周期状态模块
"""
from dataclasses import dataclass, field
from typing import Dict, Set, Optional

from .feature_config import FeatureConfig
from .key_material import KeyMaterial


@dataclass
class EpochState:
    """节点维护的周期状态"""

    # 当前时间窗
    current_epoch: int
    epoch_start_time: int         # epoch开始时间戳(ms)
    epoch_duration: int           # epoch持续时间(ms)

    # 特征配置
    current_config: Optional[FeatureConfig] = None

    # 容错窗口
    tolerated_epochs: Set[int] = field(default_factory=set)  # 允许的epoch集合{epoch-1, epoch, epoch+1}

    # 双密钥状态（新旧切换期）
    # 外层key是epoch，内层key是device_mac
    active_keys: Dict[int, Dict[bytes, KeyMaterial]] = field(default_factory=dict)

    # 同步状态
    last_beacon_time: int = 0     # 最后收到信标的时间
    is_synchronized: bool = False # 是否已同步

    def is_epoch_valid(self, epoch: int) -> bool:
        """
        检查epoch是否在容忍范围内

        Args:
            epoch: 时间窗编号

        Returns:
            是否有效
        """
        return epoch in self.tolerated_epochs

    def update_epoch(self, new_epoch: int, epoch_start_time: int,
                    epoch_duration: int, config: Optional[FeatureConfig] = None):
        """
        更新到新epoch

        Args:
            new_epoch: 新的epoch编号
            epoch_start_time: epoch开始时间
            epoch_duration: epoch持续时间
            config: 可选的特征配置
        """
        self.current_epoch = new_epoch
        self.epoch_start_time = epoch_start_time
        self.epoch_duration = epoch_duration

        if config is not None:
            self.current_config = config

        # 更新容忍窗口
        self.update_tolerated_epochs(new_epoch)

        # 清理旧密钥（保留当前和前一个epoch）
        self._cleanup_old_keys(new_epoch)

    def update_tolerated_epochs(self, current_epoch: int):
        """
        更新容忍的epoch集合

        允许当前epoch及相邻的前后各1个epoch

        Args:
            current_epoch: 当前epoch
        """
        self.tolerated_epochs = {
            current_epoch - 1,
            current_epoch,
            current_epoch + 1
        }

    def get_active_key(self, device_mac: bytes, epoch: int) -> Optional[KeyMaterial]:
        """
        获取指定设备和epoch的密钥材料

        Args:
            device_mac: 设备MAC地址
            epoch: 时间窗编号

        Returns:
            KeyMaterial或None
        """
        if epoch not in self.active_keys:
            return None

        return self.active_keys[epoch].get(device_mac)

    def add_key_material(self, device_mac: bytes, key_material: KeyMaterial):
        """
        添加密钥材料

        Args:
            device_mac: 设备MAC地址
            key_material: 密钥材料
        """
        epoch = key_material.epoch

        if epoch not in self.active_keys:
            self.active_keys[epoch] = {}

        self.active_keys[epoch][device_mac] = key_material

    def _cleanup_old_keys(self, current_epoch: int):
        """
        清理旧的密钥材料

        保留当前和前一个epoch的密钥

        Args:
            current_epoch: 当前epoch
        """
        epochs_to_remove = [
            e for e in self.active_keys.keys()
            if e < current_epoch - 1
        ]

        for epoch in epochs_to_remove:
            del self.active_keys[epoch]

    def get_epoch_progress(self, now: int) -> float:
        """
        获取当前epoch的进度

        Args:
            now: 当前时间戳(ms)

        Returns:
            进度百分比 (0.0-1.0)
        """
        if self.epoch_duration == 0:
            return 0.0

        elapsed = now - self.epoch_start_time
        return min(1.0, max(0.0, elapsed / self.epoch_duration))

    def time_until_next_epoch(self, now: int) -> int:
        """
        距离下一个epoch的时间

        Args:
            now: 当前时间戳(ms)

        Returns:
            剩余时间(ms)
        """
        next_epoch_time = self.epoch_start_time + self.epoch_duration
        return max(0, next_epoch_time - now)

    def should_advance_epoch(self, now: int) -> bool:
        """
        检查是否应该推进epoch

        Args:
            now: 当前时间戳(ms)

        Returns:
            是否应该推进
        """
        return now >= self.epoch_start_time + self.epoch_duration

    def __repr__(self) -> str:
        return (
            f"EpochState(epoch={self.current_epoch}, "
            f"tolerated={self.tolerated_epochs}, "
            f"synchronized={self.is_synchronized}, "
            f"active_keys_count={sum(len(keys) for keys in self.active_keys.values())})"
        )
