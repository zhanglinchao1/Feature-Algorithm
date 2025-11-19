"""
UAV安全群组通信 - 集成认证与加密

整合认证、密钥管理和安全通信功能，提供完整的UAV群组安全通信解决方案。
"""

import time
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from authentication_api import FeatureBasedAuthenticationAPI, AuthenticationResponse
from uav_swarm_manager import UAVSwarmManager, UAVMemberInfo
from uav_secure_channel import UAVSecureChannel


@dataclass
class SecureCommunicationSession:
    """安全通信会话"""
    peer_mac: bytes
    session_key: bytes
    secure_channel: UAVSecureChannel
    established_at: float
    last_used: float
    messages_sent: int = 0
    messages_received: int = 0


class UAVSecureSwarmCommunicator:
    """UAV安全群组通信器

    提供完整的UAV群组安全通信功能：
    - 基于物理层特征的认证
    - 点对点加密通信
    - 群组广播加密
    - 会话管理
    """

    def __init__(self,
                 node_mac: bytes,
                 is_coordinator: bool = False,
                 coordinator_signing_key: Optional[bytes] = None,
                 group_id: str = "UAVSwarm"):
        """初始化安全通信器

        Args:
            node_mac: 本节点MAC地址（6字节）
            is_coordinator: 是否为协调节点
            coordinator_signing_key: 协调节点签名密钥（协调节点必需）
            group_id: 群组标识符
        """
        self.node_mac = node_mac
        self.is_coordinator = is_coordinator
        self.group_id = group_id

        # 初始化安全信道
        self.secure_channel = UAVSecureChannel(node_mac)

        # 通信会话管理
        self.sessions: Dict[bytes, SecureCommunicationSession] = {}

        # 群组管理器（仅协调节点）
        self.swarm_manager: Optional[UAVSwarmManager] = None
        if is_coordinator:
            if coordinator_signing_key is None:
                raise ValueError("协调节点必须提供signing_key")
            self.swarm_manager = UAVSwarmManager(
                coordinator_mac=node_mac,
                coordinator_signing_key=coordinator_signing_key,
                group_id=group_id
            )

        # 认证API（用于建立会话）
        self.auth_api: Optional[FeatureBasedAuthenticationAPI] = None

        print(f"[UAVSecureSwarmCommunicator] 初始化完成")
        print(f"  节点MAC: {node_mac.hex()}")
        print(f"  角色: {'协调节点' if is_coordinator else '普通节点'}")
        print(f"  群组ID: {group_id}")

    def authenticate_and_establish_session(self,
                                          peer_mac: bytes,
                                          my_csi: np.ndarray,
                                          peer_csi: Optional[np.ndarray] = None,
                                          peer_signing_key: Optional[bytes] = None,
                                          is_requester: bool = True) -> Tuple[bool, Optional[str]]:
        """认证并建立安全通信会话

        Args:
            peer_mac: 对等节点MAC地址
            my_csi: 本节点测量的CSI数据
            peer_csi: 对等节点测量的CSI数据（验证方需要）
            peer_signing_key: 对等节点签名密钥（作为验证方时需要）
            is_requester: 是否为认证请求方

        Returns:
            (成功标志, 失败原因)
        """
        try:
            if is_requester:
                # 作为请求方
                print(f"[Session] 向 {peer_mac.hex()} 发起认证请求...")

                # 创建认证API
                if self.auth_api is None:
                    self.auth_api = FeatureBasedAuthenticationAPI.create_uav_node(
                        node_mac=self.node_mac,
                        peer_mac=peer_mac,
                        deterministic=True  # 生产环境应设为False
                    )

                # 生成认证请求
                auth_request_bytes, response = self.auth_api.authenticate(my_csi)

                if not response.success:
                    return False, f"认证请求生成失败: {response.reason}"

                # 注意：实际场景中，这里需要通过网络发送 auth_request_bytes 到对等节点
                # 并等待验证结果。这里为了演示简化处理。

                # 建立会话
                session = SecureCommunicationSession(
                    peer_mac=peer_mac,
                    session_key=response.session_key,
                    secure_channel=self.secure_channel,
                    established_at=time.time(),
                    last_used=time.time()
                )
                self.sessions[peer_mac] = session

                print(f"[Session] 会话已建立: {peer_mac.hex()}")
                print(f"  Session Key: {response.session_key.hex()[:32]}...")

                return True, None

            else:
                # 作为验证方
                print(f"[Session] 验证来自 {peer_mac.hex()} 的认证请求...")

                if peer_signing_key is None:
                    return False, "验证方必须提供signing_key"

                if peer_csi is None:
                    return False, "验证方必须提供CSI数据"

                # 创建验证API
                verifier_api = FeatureBasedAuthenticationAPI.create_peer_verifier(
                    node_mac=self.node_mac,
                    signing_key=peer_signing_key,
                    deterministic=True
                )

                # 注册对等节点（简化处理）
                # 实际场景中，feature_key应该通过安全带外渠道获取
                temp_auth_api = FeatureBasedAuthenticationAPI.create_uav_node(
                    node_mac=peer_mac,
                    peer_mac=self.node_mac,
                    deterministic=True
                )
                _, temp_response = temp_auth_api.authenticate(my_csi)

                verifier_api.register_uav_node(
                    node_mac=peer_mac,
                    feature_key=temp_response.feature_key,
                    epoch=temp_response.epoch
                )

                # 生成认证请求（模拟）
                auth_request_bytes, _ = temp_auth_api.authenticate(my_csi)

                # 验证
                response = verifier_api.verify(auth_request_bytes, peer_csi)

                if not response.success:
                    return False, f"认证验证失败: {response.reason}"

                # 建立会话
                session = SecureCommunicationSession(
                    peer_mac=peer_mac,
                    session_key=response.session_key,
                    secure_channel=self.secure_channel,
                    established_at=time.time(),
                    last_used=time.time()
                )
                self.sessions[peer_mac] = session

                print(f"[Session] 会话已建立（验证方）: {peer_mac.hex()}")

                return True, None

        except Exception as e:
            return False, f"认证异常: {str(e)}"

    def send_secure_message(self,
                          plaintext: bytes,
                          dst_mac: bytes) -> Tuple[bool, Optional[bytes], Optional[str]]:
        """发送点对点加密消息

        Args:
            plaintext: 明文数据
            dst_mac: 目标节点MAC地址

        Returns:
            (成功标志, 加密消息, 失败原因)
        """
        # 检查会话
        if dst_mac not in self.sessions:
            return False, None, f"未建立到 {dst_mac.hex()} 的会话"

        session = self.sessions[dst_mac]

        try:
            # 加密
            encrypted_data = self.secure_channel.encrypt_p2p(
                plaintext=plaintext,
                session_key=session.session_key,
                dst_mac=dst_mac
            )

            # 更新统计
            session.messages_sent += 1
            session.last_used = time.time()

            print(f"[P2P] 已发送加密消息到 {dst_mac.hex()}")
            print(f"  明文大小: {len(plaintext)} bytes")
            print(f"  密文大小: {len(encrypted_data)} bytes")

            return True, encrypted_data, None

        except Exception as e:
            return False, None, f"加密失败: {str(e)}"

    def receive_secure_message(self,
                              encrypted_data: bytes) -> Tuple[bool, Optional[bytes], Optional[bytes], Optional[str]]:
        """接收点对点加密消息

        Args:
            encrypted_data: 加密的消息

        Returns:
            (成功标志, 明文数据, 源MAC地址, 失败原因)
        """
        # 首先反序列化消息获取源MAC
        from uav_secure_channel import SecureMessage
        try:
            message = SecureMessage.deserialize(encrypted_data)
            src_mac = message.src_mac
        except Exception as e:
            return False, None, None, f"消息反序列化失败: {str(e)}"

        # 检查会话
        if src_mac not in self.sessions:
            return False, None, src_mac, f"未建立到 {src_mac.hex()} 的会话"

        # 获取session_key
        session = self.sessions[src_mac]

        # 尝试解密
        success, plaintext, _ = self.secure_channel.decrypt_p2p(
            encrypted_data=encrypted_data,
            session_key=session.session_key
        )

        if not success:
            return False, None, src_mac, "解密失败"

        # 更新统计
        session.messages_received += 1
        session.last_used = time.time()

        print(f"[P2P] 已接收来自 {src_mac.hex()} 的加密消息")
        print(f"  密文大小: {len(encrypted_data)} bytes")
        print(f"  明文大小: {len(plaintext)} bytes")

        return True, plaintext, src_mac, None

    def broadcast_secure_message(self,
                                plaintext: bytes) -> Tuple[bool, Optional[bytes], Optional[str]]:
        """广播群组加密消息

        Args:
            plaintext: 明文数据

        Returns:
            (成功标志, 加密消息, 失败原因)
        """
        if not self.is_coordinator:
            if self.swarm_manager is None:
                return False, None, "只有协调节点或已加入群组的节点可以广播"

        try:
            # 获取群组密钥
            if self.is_coordinator:
                group_key, _ = self.swarm_manager.get_group_key()
            else:
                # 普通节点需要从协调节点获取群组密钥（简化处理）
                return False, None, "普通节点暂不支持广播（需实现群组密钥分发）"

            # 加密
            encrypted_data = self.secure_channel.encrypt_group(
                plaintext=plaintext,
                group_key=group_key,
                group_id=self.group_id
            )

            print(f"[GROUP] 已广播加密消息到群组 {self.group_id}")
            print(f"  明文大小: {len(plaintext)} bytes")
            print(f"  密文大小: {len(encrypted_data)} bytes")

            return True, encrypted_data, None

        except Exception as e:
            return False, None, f"加密失败: {str(e)}"

    def receive_broadcast_message(self,
                                 encrypted_data: bytes,
                                 group_key: bytes) -> Tuple[bool, Optional[bytes], Optional[bytes], Optional[str]]:
        """接收群组广播消息

        Args:
            encrypted_data: 加密的消息
            group_key: 群组密钥

        Returns:
            (成功标志, 明文数据, 源MAC地址, 失败原因)
        """
        try:
            # 解密
            success, plaintext, src_mac = self.secure_channel.decrypt_group(
                encrypted_data=encrypted_data,
                group_key=group_key,
                group_id=self.group_id
            )

            if not success:
                return False, None, None, "解密失败"

            print(f"[GROUP] 已接收来自 {src_mac.hex()} 的群组广播")
            print(f"  密文大小: {len(encrypted_data)} bytes")
            print(f"  明文大小: {len(plaintext)} bytes")

            return True, plaintext, src_mac, None

        except Exception as e:
            return False, None, None, f"解密失败: {str(e)}"

    def get_session_info(self, peer_mac: bytes) -> Optional[Dict]:
        """获取会话信息

        Args:
            peer_mac: 对等节点MAC地址

        Returns:
            会话信息字典
        """
        if peer_mac not in self.sessions:
            return None

        session = self.sessions[peer_mac]
        return {
            'peer_mac': peer_mac.hex(),
            'established_at': session.established_at,
            'last_used': session.last_used,
            'age_seconds': time.time() - session.established_at,
            'idle_seconds': time.time() - session.last_used,
            'messages_sent': session.messages_sent,
            'messages_received': session.messages_received
        }

    def get_all_sessions(self) -> List[Dict]:
        """获取所有会话信息

        Returns:
            会话信息列表
        """
        return [self.get_session_info(mac) for mac in self.sessions.keys()]

    def close_session(self, peer_mac: bytes) -> bool:
        """关闭会话

        Args:
            peer_mac: 对等节点MAC地址

        Returns:
            是否成功
        """
        if peer_mac in self.sessions:
            del self.sessions[peer_mac]
            self.secure_channel.reset_sequence(peer_mac)
            print(f"[Session] 已关闭到 {peer_mac.hex()} 的会话")
            return True
        return False

    def cleanup_expired_sessions(self, max_idle_seconds: int = 3600) -> List[bytes]:
        """清理过期会话

        Args:
            max_idle_seconds: 最大空闲时间（秒），默认1小时

        Returns:
            被清理的会话MAC列表
        """
        now = time.time()
        expired = []

        for peer_mac, session in list(self.sessions.items()):
            if now - session.last_used > max_idle_seconds:
                expired.append(peer_mac)
                del self.sessions[peer_mac]
                self.secure_channel.reset_sequence(peer_mac)
                print(f"[Session] 清理过期会话: {peer_mac.hex()}")

        if expired:
            print(f"[Session] 共清理 {len(expired)} 个过期会话")

        return expired

    def print_status(self):
        """打印状态信息"""
        print("\n" + "=" * 80)
        print("UAV安全群组通信状态")
        print("=" * 80)
        print(f"节点MAC: {self.node_mac.hex()}")
        print(f"角色: {'协调节点' if self.is_coordinator else '普通节点'}")
        print(f"群组ID: {self.group_id}")
        print(f"活跃会话数: {len(self.sessions)}")

        if self.is_coordinator and self.swarm_manager:
            print(f"群组成员数: {self.swarm_manager.get_member_count()}")
            group_key, version = self.swarm_manager.get_group_key()
            print(f"群组密钥版本: {version}")

        # 安全信道统计
        stats = self.secure_channel.get_statistics()
        print(f"发送消息总数: {stats['total_messages_sent']}")
        print(f"接收消息总数: {stats['total_messages_received']}")
        print("=" * 80)

        if self.sessions:
            print("\n活跃会话:")
            for peer_mac, session in self.sessions.items():
                print(f"  {peer_mac.hex()}:")
                print(f"    建立时间: {time.time() - session.established_at:.1f}秒前")
                print(f"    最后活跃: {time.time() - session.last_used:.1f}秒前")
                print(f"    发送: {session.messages_sent} | 接收: {session.messages_received}")
        print()


# 导出
__all__ = [
    'UAVSecureSwarmCommunicator',
    'SecureCommunicationSession'
]
