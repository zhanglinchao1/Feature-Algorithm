"""
簇首选举模块（Bully算法简化版）
"""
import time
import logging
from typing import List, Optional, Callable
from enum import Enum

from ..utils.logging_config import get_logger


logger = get_logger(__name__)


class ElectionMessageType(Enum):
    """选举消息类型"""
    ELECTION = 1      # 选举请求
    ANSWER = 2        # 选举应答
    COORDINATOR = 3   # 簇首宣告
    HEARTBEAT = 4     # 心跳


class ElectionMessage:
    """选举消息"""

    def __init__(self, msg_type: ElectionMessageType, from_node: bytes,
                 cluster_head: Optional[bytes] = None):
        self.msg_type = msg_type
        self.from_node = from_node
        self.cluster_head = cluster_head
        self.timestamp = int(time.time() * 1000)


class ClusterElection:
    """簇首选举管理（Bully算法简化版，适用于2节点）"""

    def __init__(self, node_id: bytes, all_validators: List[bytes],
                 election_timeout: int = 5000,
                 heartbeat_interval: int = 2000):
        """
        初始化选举管理器

        Args:
            node_id: 本节点ID（6字节）
            all_validators: 所有验证节点ID列表
            election_timeout: 选举超时(ms)
            heartbeat_interval: 心跳间隔(ms)
        """
        if len(node_id) != 6:
            raise ValueError("node_id must be 6 bytes")

        self.node_id = node_id
        self.all_validators = sorted(all_validators)  # 按ID排序
        self.election_timeout = election_timeout
        self.heartbeat_interval = heartbeat_interval

        # 当前簇首
        self.current_cluster_head: Optional[bytes] = None

        # 心跳时间
        self.last_heartbeat_time = 0

        # 消息回调（用于网络发送）
        self.send_message_callback: Optional[Callable[[bytes, ElectionMessage], None]] = None

        # 收到的消息队列（模拟，实际应由网络层提供）
        self._message_queue: List[ElectionMessage] = []

        logger.info(f"ClusterElection initialized: node_id={node_id.hex()}, "
                   f"validators={[v.hex() for v in all_validators]}")

    def start_election(self) -> bytes:
        """
        启动选举流程

        Returns:
            当选的簇首ID
        """
        logger.info(f"Node {self.node_id.hex()} starting election")

        # 找到比自己ID大的节点
        higher_nodes = [v for v in self.all_validators if v > self.node_id]

        if not higher_nodes:
            # 没有更大的ID，自己成为簇首
            self._become_cluster_head()
            return self.node_id
        else:
            # 向更大的ID发送ELECTION消息
            for node in higher_nodes:
                self._send_election_message(node)

            # 等待ANSWER消息
            answer_received = self._wait_for_answer(timeout_ms=2000)

            if not answer_received:
                # 没有收到应答，自己成为簇首
                self._become_cluster_head()
                return self.node_id
            else:
                # 等待COORDINATOR消息
                new_head = self._wait_for_coordinator(timeout_ms=3000)
                if new_head:
                    self.current_cluster_head = new_head
                    logger.info(f"Accepted new cluster head: {new_head.hex()}")
                    return new_head
                else:
                    # 超时，重新选举
                    logger.warning("COORDINATOR timeout, restarting election")
                    return self.start_election()

    def _become_cluster_head(self):
        """成为簇首"""
        self.current_cluster_head = self.node_id
        logger.info(f"Node {self.node_id.hex()} became cluster head")

        # 向所有其他节点广播COORDINATOR消息
        for node in self.all_validators:
            if node != self.node_id:
                self._send_coordinator_message(node)

    def check_cluster_head_alive(self) -> bool:
        """
        检查簇首是否存活

        Returns:
            簇首是否存活
        """
        if self.current_cluster_head == self.node_id:
            # 自己是簇首，当然存活
            return True

        now = int(time.time() * 1000)

        if now - self.last_heartbeat_time > self.election_timeout:
            logger.warning("Cluster head seems dead, triggering re-election")
            return False

        return True

    def on_heartbeat_received(self, from_node: bytes):
        """
        收到心跳

        Args:
            from_node: 发送节点ID
        """
        if from_node == self.current_cluster_head:
            self.last_heartbeat_time = int(time.time() * 1000)
            logger.debug(f"Heartbeat received from cluster head {from_node.hex()}")

    def on_message_received(self, msg: ElectionMessage):
        """
        处理收到的选举消息

        Args:
            msg: 选举消息
        """
        if msg.msg_type == ElectionMessageType.ELECTION:
            self._handle_election_message(msg)
        elif msg.msg_type == ElectionMessageType.ANSWER:
            self._handle_answer_message(msg)
        elif msg.msg_type == ElectionMessageType.COORDINATOR:
            self._handle_coordinator_message(msg)
        elif msg.msg_type == ElectionMessageType.HEARTBEAT:
            self.on_heartbeat_received(msg.from_node)

    def _handle_election_message(self, msg: ElectionMessage):
        """处理ELECTION消息"""
        logger.debug(f"Received ELECTION from {msg.from_node.hex()}")

        # 如果发送者ID比自己小，发送ANSWER并启动选举
        if msg.from_node < self.node_id:
            self._send_answer_message(msg.from_node)
            # 自己也启动选举
            self.start_election()

    def _handle_answer_message(self, msg: ElectionMessage):
        """处理ANSWER消息"""
        logger.debug(f"Received ANSWER from {msg.from_node.hex()}")
        self._message_queue.append(msg)

    def _handle_coordinator_message(self, msg: ElectionMessage):
        """处理COORDINATOR消息"""
        if msg.cluster_head:
            logger.info(f"Received COORDINATOR: new head is {msg.cluster_head.hex()}")
            self.current_cluster_head = msg.cluster_head
            self.last_heartbeat_time = int(time.time() * 1000)
            self._message_queue.append(msg)

    def _send_election_message(self, to_node: bytes):
        """发送ELECTION消息"""
        msg = ElectionMessage(ElectionMessageType.ELECTION, self.node_id)
        self._send_message(to_node, msg)
        logger.debug(f"Sent ELECTION to {to_node.hex()}")

    def _send_answer_message(self, to_node: bytes):
        """发送ANSWER消息"""
        msg = ElectionMessage(ElectionMessageType.ANSWER, self.node_id)
        self._send_message(to_node, msg)
        logger.debug(f"Sent ANSWER to {to_node.hex()}")

    def _send_coordinator_message(self, to_node: bytes):
        """发送COORDINATOR消息"""
        msg = ElectionMessage(ElectionMessageType.COORDINATOR, self.node_id, self.node_id)
        self._send_message(to_node, msg)
        logger.debug(f"Sent COORDINATOR to {to_node.hex()}")

    def _send_message(self, to_node: bytes, msg: ElectionMessage):
        """发送消息（通过回调）"""
        if self.send_message_callback:
            self.send_message_callback(to_node, msg)

    def _wait_for_answer(self, timeout_ms: int) -> bool:
        """等待ANSWER消息"""
        start_time = time.time() * 1000

        while (time.time() * 1000 - start_time) < timeout_ms:
            # 检查消息队列
            for msg in self._message_queue:
                if msg.msg_type == ElectionMessageType.ANSWER:
                    self._message_queue.remove(msg)
                    return True

            time.sleep(0.1)

        return False

    def _wait_for_coordinator(self, timeout_ms: int) -> Optional[bytes]:
        """等待COORDINATOR消息"""
        start_time = time.time() * 1000

        while (time.time() * 1000 - start_time) < timeout_ms:
            # 检查消息队列
            for msg in self._message_queue:
                if msg.msg_type == ElectionMessageType.COORDINATOR:
                    self._message_queue.remove(msg)
                    return msg.cluster_head

            time.sleep(0.1)

        return None

    def set_send_callback(self, callback: Callable[[bytes, ElectionMessage], None]):
        """
        设置消息发送回调

        Args:
            callback: 回调函数，参数为(to_node, message)
        """
        self.send_message_callback = callback
