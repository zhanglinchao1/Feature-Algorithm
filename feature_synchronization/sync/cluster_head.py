"""
簇首节点模块
"""
import time
import secrets
import threading
import logging
from typing import Optional, Callable

from ..core.beacon import SyncBeacon
from ..core.feature_config import FeatureConfig
from ..utils.logging_config import get_logger


logger = get_logger(__name__)


class ClusterHead:
    """簇首节点"""

    def __init__(self, node_id: bytes, delta_t: int = 30000,
                 beacon_interval: int = 5000,
                 signing_key: Optional[bytes] = None):
        """
        初始化簇首节点

        Args:
            node_id: 节点ID（6字节MAC地址）
            delta_t: epoch周期(ms)，默认30000ms(30秒)
            beacon_interval: 信标广播间隔(ms)，默认5000ms(5秒)
            signing_key: 签名密钥（可选，默认随机生成）
        """
        if len(node_id) != 6:
            raise ValueError("node_id must be 6 bytes")

        self.node_id = node_id
        self.delta_t = delta_t
        self.beacon_interval = beacon_interval
        self.signing_key = signing_key or secrets.token_bytes(32)

        # 状态
        self.current_epoch = 0
        self.epoch_start_time = 0
        self.beacon_seq = 0
        self.feature_config = self._init_feature_config()

        # 控制
        self._running = False
        self._broadcast_thread: Optional[threading.Thread] = None

        # 回调函数（用于测试和网络层集成）
        self.beacon_callback: Optional[Callable[[SyncBeacon], None]] = None

        logger.info(f"ClusterHead initialized: node_id={node_id.hex()}, "
                   f"delta_t={delta_t}ms, beacon_interval={beacon_interval}ms")

    def _init_feature_config(self) -> FeatureConfig:
        """初始化特征配置"""
        return FeatureConfig.create_default()

    def start(self):
        """启动信标广播"""
        if self._running:
            logger.warning("ClusterHead already running")
            return

        self._running = True
        self.epoch_start_time = int(time.time() * 1000)

        # 启动广播线程
        self._broadcast_thread = threading.Thread(
            target=self._beacon_broadcast_loop,
            daemon=True,
            name="ClusterHeadBeacon"
        )
        self._broadcast_thread.start()

        logger.info("ClusterHead started")

    def stop(self):
        """停止信标广播"""
        if not self._running:
            return

        self._running = False

        if self._broadcast_thread:
            self._broadcast_thread.join(timeout=2.0)

        logger.info("ClusterHead stopped")

    def _beacon_broadcast_loop(self):
        """信标广播循环"""
        logger.info("Beacon broadcast loop started")

        while self._running:
            try:
                # 生成并广播信标
                beacon = self._generate_beacon()
                self._broadcast_beacon(beacon)

                # 等待下一次广播
                time.sleep(self.beacon_interval / 1000.0)

            except Exception as e:
                logger.error(f"Error in beacon broadcast loop: {e}", exc_info=True)
                time.sleep(1.0)  # 出错后短暂休眠

        logger.info("Beacon broadcast loop stopped")

    def _generate_beacon(self) -> SyncBeacon:
        """
        生成同步信标

        Returns:
            SyncBeacon对象
        """
        now = int(time.time() * 1000)

        # 检查是否需要推进epoch
        if self._should_advance_epoch(now):
            self._advance_epoch(now)

        # 创建信标
        beacon = SyncBeacon(
            epoch=self.current_epoch,
            timestamp=now,
            delta_t=self.delta_t,
            cluster_head_id=self.node_id,
            beacon_seq=self.beacon_seq,
            feature_config=self.feature_config,
            signature=b''  # 将在签名后填充
        )

        # 签名
        beacon.sign(self.signing_key)

        # 更新序号
        self.beacon_seq += 1

        logger.debug(f"Generated beacon: epoch={beacon.epoch}, seq={beacon.beacon_seq}")

        return beacon

    def _should_advance_epoch(self, now: int) -> bool:
        """
        检查是否应该推进epoch

        Args:
            now: 当前时间戳(ms)

        Returns:
            是否应该推进
        """
        elapsed = now - self.epoch_start_time
        return elapsed >= self.delta_t

    def _advance_epoch(self, now: int):
        """
        推进到下一个epoch

        Args:
            now: 当前时间戳(ms)
        """
        old_epoch = self.current_epoch
        self.current_epoch += 1
        self.epoch_start_time = now

        logger.info(f"Epoch advanced: {old_epoch} -> {self.current_epoch}")

        # 检查是否需要轮换特征配置
        if self._should_rotate_config():
            self._rotate_feature_config()

    def _should_rotate_config(self) -> bool:
        """
        检查是否应该轮换特征配置

        Returns:
            是否应该轮换
        """
        # 每10个epoch轮换一次
        return self.current_epoch % 10 == 0 and self.current_epoch > 0

    def _rotate_feature_config(self):
        """轮换特征参数配置"""
        old_version = self.feature_config.version

        # 生成新的子载波选择种子
        new_seed = secrets.token_bytes(8)

        # 创建新配置（保留导频计划）
        self.feature_config = FeatureConfig(
            version=old_version + 1,
            config_id=secrets.token_bytes(16),
            pilot_plan=self.feature_config.pilot_plan,  # 保持不变
            measurement_window_ms=self.feature_config.measurement_window_ms,
            sample_count=self.feature_config.sample_count,
            subcarrier_seed=new_seed,
            subcarrier_count=self.feature_config.subcarrier_count,
            quantization_alpha=self.feature_config.quantization_alpha,
            digest=b''
        )

        # 计算新摘要
        self.feature_config.digest = self.feature_config.compute_digest()

        logger.info(f"Feature config rotated: version {old_version} -> {self.feature_config.version}")

    def _broadcast_beacon(self, beacon: SyncBeacon):
        """
        广播信标

        Args:
            beacon: 要广播的信标
        """
        # 调用回调函数（用于网络层发送）
        if self.beacon_callback:
            self.beacon_callback(beacon)
        else:
            # 默认行为：仅记录日志
            logger.debug(f"Beacon broadcast: {beacon}")

    def get_current_epoch(self) -> int:
        """获取当前epoch"""
        return self.current_epoch

    def get_feature_config(self) -> FeatureConfig:
        """获取当前特征配置"""
        return self.feature_config

    def set_beacon_callback(self, callback: Callable[[SyncBeacon], None]):
        """
        设置信标广播回调函数

        Args:
            callback: 回调函数，接收SyncBeacon参数
        """
        self.beacon_callback = callback
