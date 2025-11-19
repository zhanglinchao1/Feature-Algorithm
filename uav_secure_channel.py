"""
UAV安全通信信道 - 数据加密与解密

基于认证后的会话密钥（session_key）和群组密钥（group_key），
提供UAV节点间的安全数据通信。

特性：
- 点对点加密通信（使用session_key）
- 群组广播加密（使用group_key）
- 防重放攻击（序列号检查）
- 消息完整性保护（AES-GCM）
- 时间戳验证
"""

import time
import struct
import secrets
from typing import Tuple, Optional, Dict
from dataclasses import dataclass
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend


@dataclass
class SecureMessage:
    """安全消息结构"""
    version: int = 1
    msg_type: int = 1  # 1=点对点, 2=群组广播
    src_mac: bytes = b'\x00' * 6
    dst_mac: bytes = b'\x00' * 6  # 或 group_id_hash（群组模式）
    sequence: int = 0
    timestamp: int = 0  # Unix时间戳（毫秒）
    nonce: bytes = b'\x00' * 12
    ciphertext: bytes = b''
    tag: bytes = b'\x00' * 16  # GCM认证标签（包含在ciphertext中）

    def serialize(self) -> bytes:
        """序列化为字节流"""
        return (
            struct.pack('B', self.version) +           # 1 byte
            struct.pack('B', self.msg_type) +          # 1 byte
            self.src_mac +                             # 6 bytes
            self.dst_mac +                             # 6 bytes
            struct.pack('>I', self.sequence) +         # 4 bytes
            struct.pack('>Q', self.timestamp) +        # 8 bytes
            self.nonce +                               # 12 bytes
            struct.pack('>H', len(self.ciphertext)) +  # 2 bytes
            self.ciphertext                            # variable + 16 bytes tag
        )

    @staticmethod
    def deserialize(data: bytes) -> 'SecureMessage':
        """从字节流反序列化"""
        if len(data) < 40:  # 最小消息长度
            raise ValueError(f"消息太短: {len(data)} bytes")

        offset = 0
        version = struct.unpack('B', data[offset:offset+1])[0]
        offset += 1

        msg_type = struct.unpack('B', data[offset:offset+1])[0]
        offset += 1

        src_mac = data[offset:offset+6]
        offset += 6

        dst_mac = data[offset:offset+6]
        offset += 6

        sequence = struct.unpack('>I', data[offset:offset+4])[0]
        offset += 4

        timestamp = struct.unpack('>Q', data[offset:offset+8])[0]
        offset += 8

        nonce = data[offset:offset+12]
        offset += 12

        ciphertext_len = struct.unpack('>H', data[offset:offset+2])[0]
        offset += 2

        if len(data) < offset + ciphertext_len:
            raise ValueError(f"密文长度不匹配: 期望{ciphertext_len}, 实际{len(data) - offset}")

        ciphertext = data[offset:offset+ciphertext_len]

        return SecureMessage(
            version=version,
            msg_type=msg_type,
            src_mac=src_mac,
            dst_mac=dst_mac,
            sequence=sequence,
            timestamp=timestamp,
            nonce=nonce,
            ciphertext=ciphertext
        )


class UAVSecureChannel:
    """UAV安全通信信道

    提供基于AES-256-GCM的加密通信，支持点对点和群组广播。
    """

    # 消息类型
    MSG_TYPE_P2P = 1      # 点对点
    MSG_TYPE_GROUP = 2    # 群组广播

    # 安全参数
    MAX_MESSAGE_AGE_MS = 30000  # 消息最大有效期（30秒）
    REPLAY_WINDOW_SIZE = 1000   # 重放检测窗口大小

    def __init__(self, node_mac: bytes):
        """初始化安全信道

        Args:
            node_mac: 本节点MAC地址（6字节）
        """
        if len(node_mac) != 6:
            raise ValueError(f"node_mac必须是6字节，当前为{len(node_mac)}字节")

        self.node_mac = node_mac

        # 序列号计数器（每个对等节点/群组独立）
        self._sequence_counters: Dict[bytes, int] = {}

        # 重放检测（记录已接收的序列号）
        self._received_sequences: Dict[bytes, set] = {}

        print(f"[UAVSecureChannel] 初始化完成")
        print(f"  节点MAC: {node_mac.hex()}")

    def encrypt_p2p(self,
                    plaintext: bytes,
                    session_key: bytes,
                    dst_mac: bytes) -> bytes:
        """点对点加密

        Args:
            plaintext: 明文数据
            session_key: 会话密钥（32字节）
            dst_mac: 目标节点MAC地址（6字节）

        Returns:
            加密后的消息（序列化字节流）

        Raises:
            ValueError: 参数错误
        """
        if len(session_key) != 32:
            raise ValueError(f"session_key必须是32字节，当前为{len(session_key)}字节")
        if len(dst_mac) != 6:
            raise ValueError(f"dst_mac必须是6字节，当前为{len(dst_mac)}字节")

        # 生成序列号
        sequence = self._get_next_sequence(dst_mac)

        # 生成时间戳
        timestamp = int(time.time() * 1000)

        # 生成nonce（12字节）
        nonce = secrets.token_bytes(12)

        # 构造AAD（Additional Authenticated Data）
        aad = self._build_aad(
            msg_type=self.MSG_TYPE_P2P,
            src_mac=self.node_mac,
            dst_mac=dst_mac,
            sequence=sequence,
            timestamp=timestamp
        )

        # AES-GCM加密
        aesgcm = AESGCM(session_key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, aad)  # 包含16字节tag

        # 构造消息
        message = SecureMessage(
            version=1,
            msg_type=self.MSG_TYPE_P2P,
            src_mac=self.node_mac,
            dst_mac=dst_mac,
            sequence=sequence,
            timestamp=timestamp,
            nonce=nonce,
            ciphertext=ciphertext
        )

        return message.serialize()

    def decrypt_p2p(self,
                    encrypted_data: bytes,
                    session_key: bytes) -> Tuple[bool, Optional[bytes], Optional[bytes]]:
        """点对点解密

        Args:
            encrypted_data: 加密的消息
            session_key: 会话密钥（32字节）

        Returns:
            (成功标志, 明文数据, 源MAC地址)
            - 成功: (True, plaintext, src_mac)
            - 失败: (False, None, None)
        """
        try:
            # 反序列化消息
            message = SecureMessage.deserialize(encrypted_data)

            # 验证消息类型
            if message.msg_type != self.MSG_TYPE_P2P:
                print(f"[UAVSecureChannel] 消息类型错误: {message.msg_type}")
                return False, None, None

            # 验证目标MAC
            if message.dst_mac != self.node_mac:
                print(f"[UAVSecureChannel] 目标MAC不匹配: {message.dst_mac.hex()} != {self.node_mac.hex()}")
                return False, None, None

            # 验证时间戳（防止过期消息）
            current_time = int(time.time() * 1000)
            message_age = current_time - message.timestamp

            if message_age > self.MAX_MESSAGE_AGE_MS:
                print(f"[UAVSecureChannel] 消息过期: {message_age}ms")
                return False, None, None

            if message_age < -5000:  # 允许5秒时钟偏差
                print(f"[UAVSecureChannel] 消息时间戳来自未来: {message_age}ms")
                return False, None, None

            # 检测重放攻击
            if self._is_replay(message.src_mac, message.sequence):
                print(f"[UAVSecureChannel] 检测到重放攻击: seq={message.sequence}")
                return False, None, None

            # 构造AAD
            aad = self._build_aad(
                msg_type=message.msg_type,
                src_mac=message.src_mac,
                dst_mac=message.dst_mac,
                sequence=message.sequence,
                timestamp=message.timestamp
            )

            # AES-GCM解密
            aesgcm = AESGCM(session_key)
            plaintext = aesgcm.decrypt(message.nonce, message.ciphertext, aad)

            # 记录序列号（防重放）
            self._record_sequence(message.src_mac, message.sequence)

            return True, plaintext, message.src_mac

        except Exception as e:
            print(f"[UAVSecureChannel] 解密失败: {str(e)}")
            return False, None, None

    def encrypt_group(self,
                     plaintext: bytes,
                     group_key: bytes,
                     group_id: str) -> bytes:
        """群组广播加密

        Args:
            plaintext: 明文数据
            group_key: 群组密钥（32字节）
            group_id: 群组标识符

        Returns:
            加密后的消息（序列化字节流）
        """
        if len(group_key) != 32:
            raise ValueError(f"group_key必须是32字节，当前为{len(group_key)}字节")

        # 计算群组ID哈希（6字节）
        group_id_hash = self._hash_group_id(group_id)

        # 生成序列号（使用群组ID哈希作为标识）
        sequence = self._get_next_sequence(group_id_hash)

        # 生成时间戳
        timestamp = int(time.time() * 1000)

        # 生成nonce（12字节）
        nonce = secrets.token_bytes(12)

        # 构造AAD
        aad = self._build_aad(
            msg_type=self.MSG_TYPE_GROUP,
            src_mac=self.node_mac,
            dst_mac=group_id_hash,
            sequence=sequence,
            timestamp=timestamp
        )

        # AES-GCM加密
        aesgcm = AESGCM(group_key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, aad)

        # 构造消息
        message = SecureMessage(
            version=1,
            msg_type=self.MSG_TYPE_GROUP,
            src_mac=self.node_mac,
            dst_mac=group_id_hash,
            sequence=sequence,
            timestamp=timestamp,
            nonce=nonce,
            ciphertext=ciphertext
        )

        return message.serialize()

    def decrypt_group(self,
                     encrypted_data: bytes,
                     group_key: bytes,
                     group_id: str) -> Tuple[bool, Optional[bytes], Optional[bytes]]:
        """群组广播解密

        Args:
            encrypted_data: 加密的消息
            group_key: 群组密钥（32字节）
            group_id: 群组标识符

        Returns:
            (成功标志, 明文数据, 源MAC地址)
        """
        try:
            # 反序列化消息
            message = SecureMessage.deserialize(encrypted_data)

            # 验证消息类型
            if message.msg_type != self.MSG_TYPE_GROUP:
                print(f"[UAVSecureChannel] 消息类型错误: {message.msg_type}")
                return False, None, None

            # 验证群组ID
            group_id_hash = self._hash_group_id(group_id)
            if message.dst_mac != group_id_hash:
                print(f"[UAVSecureChannel] 群组ID不匹配")
                return False, None, None

            # 验证时间戳
            current_time = int(time.time() * 1000)
            message_age = current_time - message.timestamp

            if message_age > self.MAX_MESSAGE_AGE_MS:
                print(f"[UAVSecureChannel] 消息过期: {message_age}ms")
                return False, None, None

            if message_age < -5000:
                print(f"[UAVSecureChannel] 消息时间戳来自未来: {message_age}ms")
                return False, None, None

            # 检测重放攻击（基于源MAC + 序列号）
            replay_key = message.src_mac + b':' + group_id_hash
            if self._is_replay(replay_key, message.sequence):
                print(f"[UAVSecureChannel] 检测到重放攻击: seq={message.sequence}")
                return False, None, None

            # 构造AAD
            aad = self._build_aad(
                msg_type=message.msg_type,
                src_mac=message.src_mac,
                dst_mac=message.dst_mac,
                sequence=message.sequence,
                timestamp=message.timestamp
            )

            # AES-GCM解密
            aesgcm = AESGCM(group_key)
            plaintext = aesgcm.decrypt(message.nonce, message.ciphertext, aad)

            # 记录序列号（防重放）
            self._record_sequence(replay_key, message.sequence)

            return True, plaintext, message.src_mac

        except Exception as e:
            print(f"[UAVSecureChannel] 解密失败: {str(e)}")
            return False, None, None

    def _build_aad(self,
                   msg_type: int,
                   src_mac: bytes,
                   dst_mac: bytes,
                   sequence: int,
                   timestamp: int) -> bytes:
        """构造AAD（Additional Authenticated Data）

        AAD会被认证但不会被加密，用于防止消息被篡改。
        """
        return (
            struct.pack('B', 1) +                # version
            struct.pack('B', msg_type) +         # msg_type
            src_mac +                            # src_mac (6 bytes)
            dst_mac +                            # dst_mac (6 bytes)
            struct.pack('>I', sequence) +        # sequence (4 bytes)
            struct.pack('>Q', timestamp)         # timestamp (8 bytes)
        )

    def _get_next_sequence(self, identifier: bytes) -> int:
        """获取下一个序列号

        Args:
            identifier: 标识符（对等节点MAC或群组ID哈希）

        Returns:
            序列号
        """
        if identifier not in self._sequence_counters:
            self._sequence_counters[identifier] = 0

        self._sequence_counters[identifier] += 1
        return self._sequence_counters[identifier]

    def _is_replay(self, identifier: bytes, sequence: int) -> bool:
        """检测是否为重放攻击

        Args:
            identifier: 标识符
            sequence: 序列号

        Returns:
            是否为重放
        """
        if identifier not in self._received_sequences:
            return False

        return sequence in self._received_sequences[identifier]

    def _record_sequence(self, identifier: bytes, sequence: int) -> None:
        """记录已接收的序列号

        Args:
            identifier: 标识符
            sequence: 序列号
        """
        if identifier not in self._received_sequences:
            self._received_sequences[identifier] = set()

        self._received_sequences[identifier].add(sequence)

        # 限制窗口大小（防止内存溢出）
        if len(self._received_sequences[identifier]) > self.REPLAY_WINDOW_SIZE:
            # 移除最旧的序列号（简单实现：保留最近的1000个）
            sorted_seqs = sorted(self._received_sequences[identifier])
            self._received_sequences[identifier] = set(sorted_seqs[-self.REPLAY_WINDOW_SIZE:])

    def _hash_group_id(self, group_id: str) -> bytes:
        """计算群组ID的哈希（6字节）

        Args:
            group_id: 群组标识符

        Returns:
            6字节哈希值
        """
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(group_id.encode('utf-8'))
        return digest.finalize()[:6]

    def get_statistics(self) -> Dict:
        """获取统计信息

        Returns:
            统计信息字典
        """
        total_sent = sum(self._sequence_counters.values())
        total_received = sum(len(seqs) for seqs in self._received_sequences.values())

        return {
            'node_mac': self.node_mac.hex(),
            'total_messages_sent': total_sent,
            'total_messages_received': total_received,
            'active_channels': len(self._sequence_counters),
            'replay_detection_entries': sum(len(seqs) for seqs in self._received_sequences.values())
        }

    def reset_sequence(self, identifier: bytes) -> None:
        """重置序列号计数器

        Args:
            identifier: 标识符（对等节点MAC或群组ID哈希）
        """
        if identifier in self._sequence_counters:
            del self._sequence_counters[identifier]
        if identifier in self._received_sequences:
            del self._received_sequences[identifier]

        print(f"[UAVSecureChannel] 已重置序列号: {identifier.hex()}")


# 导出
__all__ = [
    'UAVSecureChannel',
    'SecureMessage'
]
