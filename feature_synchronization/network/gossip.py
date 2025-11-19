"""
Gossip协议模块
"""
import time
import random
import logging
import threading
from typing import List, Set, Dict, Optional, Callable

from ..auth.mat_token import MATToken
from ..utils.logging_config import get_logger


logger = get_logger(__name__)


class GossipMessage:
    """Gossip消息"""

    def __init__(self, from_node: bytes, version: int, epoch: int,
                 revocation_list: List[bytes]):
        """
        初始化Gossip消息

        Args:
            from_node: 发送节点ID
            version: 状态版本号
            epoch: 当前epoch
            revocation_list: 吊销的MAT ID列表
        """
        self.from_node = from_node
        self.version = version
        self.epoch = epoch
        self.revocation_list = revocation_list
        self.timestamp = int(time.time() * 1000)

    def to_dict(self) -> dict:
        """转换为字典（用于序列化）"""
        return {
            'type': 'GOSSIP',
            'from': self.from_node.hex(),
            'version': self.version,
            'epoch': self.epoch,
            'revocation_list': [mat_id.hex() for mat_id in self.revocation_list],
            'timestamp': self.timestamp
        }

    @staticmethod
    def from_dict(data: dict) -> 'GossipMessage':
        """从字典构造（用于反序列化）"""
        return GossipMessage(
            from_node=bytes.fromhex(data['from']),
            version=data['version'],
            epoch=data['epoch'],
            revocation_list=[bytes.fromhex(mat_id) for mat_id in data['revocation_list']]
        )


class GossipProtocol:
    """验证节点间Gossip协议"""

    def __init__(self, local_node: bytes, peer_nodes: List[bytes],
                 gossip_interval: int = 3000):
        """
        初始化Gossip协议

        Args:
            local_node: 本地节点ID（6字节）
            peer_nodes: 对等节点ID列表
            gossip_interval: Gossip间隔(ms)，默认3000ms(3秒)
        """
        if len(local_node) != 6:
            raise ValueError("local_node must be 6 bytes")

        self.local_node = local_node
        self.peer_nodes = peer_nodes
        self.gossip_interval = gossip_interval

        # 状态版本
        self.state_version = 0

        # 需要同步的状态
        self.revocation_list: Set[bytes] = set()  # 吊销的MAT ID
        self.mat_cache: Dict[bytes, MATToken] = {}  # MAT缓存

        # 控制
        self._running = False
        self._gossip_thread: Optional[threading.Thread] = None

        # 回调函数
        self.send_message_callback: Optional[Callable[[bytes, GossipMessage], None]] = None
        self.on_state_update_callback: Optional[Callable[[Set[bytes]], None]] = None

        logger.info(f"GossipProtocol initialized: node={local_node.hex()}, "
                   f"peers={[p.hex() for p in peer_nodes]}, "
                   f"interval={gossip_interval}ms")

    def start(self):
        """启动Gossip循环"""
        if self._running:
            logger.warning("Gossip protocol already running")
            return

        self._running = True

        # 启动gossip线程
        self._gossip_thread = threading.Thread(
            target=self._gossip_loop,
            daemon=True,
            name="GossipProtocol"
        )
        self._gossip_thread.start()

        logger.info("Gossip protocol started")

    def stop(self):
        """停止Gossip循环"""
        if not self._running:
            return

        self._running = False

        if self._gossip_thread:
            self._gossip_thread.join(timeout=2.0)

        logger.info("Gossip protocol stopped")

    def _gossip_loop(self):
        """Gossip循环"""
        logger.info("Gossip loop started")

        while self._running:
            try:
                self._gossip_round()
                time.sleep(self.gossip_interval / 1000.0)

            except Exception as e:
                logger.error(f"Error in gossip loop: {e}", exc_info=True)
                time.sleep(1.0)

        logger.info("Gossip loop stopped")

    def _gossip_round(self):
        """执行一轮gossip"""
        if not self.peer_nodes:
            logger.debug("No peers to gossip with")
            return

        # 随机选择一个peer
        peer = random.choice(self.peer_nodes)

        # 构造gossip消息
        msg = self._build_gossip_message()

        # 发送给peer
        self._send_gossip(peer, msg)

        logger.debug(f"Gossip sent to {peer.hex()}: version={msg.version}, "
                    f"revocations={len(msg.revocation_list)}")

    def _build_gossip_message(self) -> GossipMessage:
        """构造gossip消息"""
        return GossipMessage(
            from_node=self.local_node,
            version=self.state_version,
            epoch=0,  # 由调用者设置
            revocation_list=list(self.revocation_list)
        )

    def on_gossip_received(self, msg: GossipMessage):
        """
        处理收到的gossip消息

        Args:
            msg: Gossip消息
        """
        logger.debug(f"Received gossip from {msg.from_node.hex()}: "
                    f"version={msg.version}, revocations={len(msg.revocation_list)}")

        # 合并吊销列表
        peer_revocations = set(msg.revocation_list)
        new_revocations = peer_revocations - self.revocation_list

        if new_revocations:
            self.revocation_list.update(new_revocations)
            self.state_version += 1

            logger.info(f"Merged {len(new_revocations)} new revocations from {msg.from_node.hex()}")

            # 触发回调
            if self.on_state_update_callback:
                self.on_state_update_callback(new_revocations)

    def add_revocation(self, mat_id: bytes):
        """
        添加吊销记录

        Args:
            mat_id: MAT ID（16字节）
        """
        if mat_id not in self.revocation_list:
            self.revocation_list.add(mat_id)
            self.state_version += 1
            logger.debug(f"Added revocation: {mat_id.hex()}")

    def get_revocation_list(self) -> List[bytes]:
        """获取吊销列表"""
        return list(self.revocation_list)

    def is_revoked(self, mat_id: bytes) -> bool:
        """
        检查MAT是否被吊销

        Args:
            mat_id: MAT ID

        Returns:
            是否被吊销
        """
        return mat_id in self.revocation_list

    def _send_gossip(self, peer: bytes, msg: GossipMessage):
        """
        发送gossip消息

        Args:
            peer: 对等节点ID
            msg: Gossip消息
        """
        if self.send_message_callback:
            self.send_message_callback(peer, msg)

    def set_send_callback(self, callback: Callable[[bytes, GossipMessage], None]):
        """
        设置消息发送回调

        Args:
            callback: 回调函数，参数为(peer, message)
        """
        self.send_message_callback = callback

    def set_state_update_callback(self, callback: Callable[[Set[bytes]], None]):
        """
        设置状态更新回调

        Args:
            callback: 回调函数，参数为新的吊销集合
        """
        self.on_state_update_callback = callback
