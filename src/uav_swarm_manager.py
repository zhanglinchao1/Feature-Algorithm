"""
UAV群组管理器 - 密钥管理和成员管理

提供UAV群组的成员管理、密钥轮换、快速切换等高级功能。
"""

import time
import secrets
import hashlib
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from authentication_api import (
    FeatureBasedAuthenticationAPI,
    PeerVerifierAuthAPI,
    AuthenticationResponse
)
import numpy as np


@dataclass
class UAVMemberInfo:
    """UAV成员信息"""
    node_mac: bytes
    feature_key: bytes
    session_key: Optional[bytes] = None
    mat_token: Optional[bytes] = None
    joined_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    epoch: int = 0
    auth_count: int = 0
    is_active: bool = True


class UAVSwarmManager:
    """UAV群组管理器

    管理UAV群组中的成员、密钥轮换、快速切换等功能。
    适用于UAV自组织网络的群组管理。
    """

    def __init__(self,
                 coordinator_mac: bytes,
                 coordinator_signing_key: bytes,
                 group_id: str = "UAVSwarm",
                 member_timeout: int = 300,
                 key_rotation_interval: int = 3600):
        """初始化UAV群组管理器

        Args:
            coordinator_mac: 协调节点MAC地址（6字节）
            coordinator_signing_key: 协调节点签名密钥（32字节）
            group_id: 群组标识符
            member_timeout: 成员超时时间（秒），默认5分钟
            key_rotation_interval: 群组密钥轮换间隔（秒），默认1小时
        """
        self.coordinator_mac = coordinator_mac
        self.coordinator_signing_key = coordinator_signing_key
        self.group_id = group_id
        self.member_timeout = member_timeout
        self.key_rotation_interval = key_rotation_interval

        # 成员管理
        self.members: Dict[bytes, UAVMemberInfo] = {}

        # 群组密钥
        self.group_key: Optional[bytes] = None
        self.group_key_version: int = 0
        self.last_key_rotation: float = time.time()

        # 验证器API
        self.verifier_api = FeatureBasedAuthenticationAPI.create_peer_verifier(
            node_mac=coordinator_mac,
            signing_key=coordinator_signing_key
        )

        # 初始化群组密钥
        self._rotate_group_key()

        print(f"[UAVSwarmManager] 初始化完成")
        print(f"  群组ID: {group_id}")
        print(f"  协调节点: {coordinator_mac.hex()}")
        print(f"  群组密钥版本: {self.group_key_version}")

    def add_member(self,
                   node_mac: bytes,
                   feature_key: bytes,
                   epoch: int = 0,
                   session_key: Optional[bytes] = None,
                   mat_token: Optional[bytes] = None) -> bool:
        """添加UAV成员到群组

        Args:
            node_mac: UAV节点MAC地址（6字节）
            feature_key: 特征密钥（32字节）
            epoch: epoch编号
            session_key: 会话密钥（可选）
            mat_token: MAT令牌（可选）

        Returns:
            是否添加成功
        """
        if node_mac in self.members:
            print(f"[UAVSwarmManager] 成员已存在: {node_mac.hex()}")
            return False

        # 注册到验证器
        success = self.verifier_api.register_uav_node(node_mac, feature_key, epoch)
        if not success:
            print(f"[UAVSwarmManager] 注册失败: {node_mac.hex()}")
            return False

        # 创建成员信息
        member = UAVMemberInfo(
            node_mac=node_mac,
            feature_key=feature_key,
            session_key=session_key,
            mat_token=mat_token,
            epoch=epoch
        )

        self.members[node_mac] = member
        print(f"[UAVSwarmManager] 成员已添加: {node_mac.hex()}")
        print(f"  当前成员数量: {len(self.members)}")

        return True

    def remove_member(self, node_mac: bytes) -> bool:
        """移除UAV成员

        Args:
            node_mac: UAV节点MAC地址

        Returns:
            是否移除成功
        """
        if node_mac not in self.members:
            print(f"[UAVSwarmManager] 成员不存在: {node_mac.hex()}")
            return False

        # 标记为不活跃
        self.members[node_mac].is_active = False

        # 从注册表中移除
        del self.members[node_mac]

        print(f"[UAVSwarmManager] 成员已移除: {node_mac.hex()}")
        print(f"  当前成员数量: {len(self.members)}")

        return True

    def revoke_member(self, node_mac: bytes, reason: str = "Revoked by admin") -> bool:
        """撤销UAV成员（安全移除）

        Args:
            node_mac: UAV节点MAC地址
            reason: 撤销原因

        Returns:
            是否撤销成功
        """
        if node_mac not in self.members:
            return False

        member = self.members[node_mac]
        member.is_active = False

        print(f"[UAVSwarmManager] 成员已撤销: {node_mac.hex()}")
        print(f"  原因: {reason}")

        # 触发群组密钥轮换（排除被撤销的成员）
        self._rotate_group_key()

        # 移除成员
        del self.members[node_mac]

        return True

    def update_member_activity(self, node_mac: bytes) -> bool:
        """更新成员活跃时间

        Args:
            node_mac: UAV节点MAC地址

        Returns:
            是否更新成功
        """
        if node_mac not in self.members:
            return False

        self.members[node_mac].last_seen = time.time()
        return True

    def cleanup_inactive_members(self) -> List[bytes]:
        """清理不活跃的成员

        Returns:
            被清理的成员MAC列表
        """
        now = time.time()
        inactive = []

        for node_mac, member in list(self.members.items()):
            if now - member.last_seen > self.member_timeout:
                inactive.append(node_mac)
                print(f"[UAVSwarmManager] 清理不活跃成员: {node_mac.hex()}")
                print(f"  上次活跃: {now - member.last_seen:.1f}秒前")
                del self.members[node_mac]

        if inactive:
            print(f"[UAVSwarmManager] 清理完成，移除 {len(inactive)} 个不活跃成员")
            # 清理后轮换群组密钥
            self._rotate_group_key()

        return inactive

    def verify_member(self,
                     auth_request_bytes: bytes,
                     csi_measurements: np.ndarray) -> Tuple[bool, Optional[bytes], AuthenticationResponse]:
        """验证成员认证请求

        Args:
            auth_request_bytes: 认证请求
            csi_measurements: CSI测量数据

        Returns:
            (是否成功, 节点MAC, 响应对象)
        """
        response = self.verifier_api.verify(auth_request_bytes, csi_measurements)

        if response.success and response.node_id:
            # 更新成员信息
            if response.node_id in self.members:
                member = self.members[response.node_id]
                member.last_seen = time.time()
                member.session_key = response.session_key
                member.mat_token = response.token
                member.auth_count += 1

                print(f"[UAVSwarmManager] 成员认证成功: {response.node_id.hex()}")
                print(f"  认证次数: {member.auth_count}")

                return True, response.node_id, response
            else:
                print(f"[UAVSwarmManager] 未知成员: {response.node_id.hex()}")
                return False, response.node_id, response
        else:
            print(f"[UAVSwarmManager] 认证失败: {response.reason}")
            return False, None, response

    def _rotate_group_key(self) -> bytes:
        """轮换群组密钥（内部方法）

        Returns:
            新的群组密钥
        """
        # 收集所有活跃成员的session_key
        active_session_keys = []
        for member in self.members.values():
            if member.is_active and member.session_key:
                active_session_keys.append(member.session_key)

        # 派生群组密钥
        self.group_key = self._derive_group_key(active_session_keys)
        self.group_key_version += 1
        self.last_key_rotation = time.time()

        print(f"[UAVSwarmManager] 群组密钥已轮换")
        print(f"  版本: {self.group_key_version}")
        print(f"  活跃成员数: {len(active_session_keys)}")

        return self.group_key

    def _derive_group_key(self, session_keys: List[bytes]) -> bytes:
        """从多个session_key派生群组密钥

        Args:
            session_keys: 所有活跃成员的session_key列表

        Returns:
            群组密钥（32字节）
        """
        if not session_keys:
            # 没有活跃成员，使用协调节点密钥
            base = self.coordinator_signing_key
        else:
            # 组合所有session_key（排序确保一致性）
            combined = b''.join(sorted(session_keys))
            base = combined

        # 添加群组标识和版本
        data = (
            self.group_id.encode('utf-8') +
            base +
            self.group_key_version.to_bytes(4, 'little')
        )

        # 使用SHA256派生
        return hashlib.sha256(data).digest()

    def update_group_key(self) -> bytes:
        """手动更新群组密钥

        Returns:
            新的群组密钥
        """
        print(f"[UAVSwarmManager] 手动触发群组密钥轮换")
        return self._rotate_group_key()

    def auto_rotate_group_key_if_needed(self) -> bool:
        """自动轮换群组密钥（如果达到时间间隔）

        Returns:
            是否执行了轮换
        """
        now = time.time()
        if now - self.last_key_rotation > self.key_rotation_interval:
            print(f"[UAVSwarmManager] 自动轮换群组密钥（已过 {now - self.last_key_rotation:.1f} 秒）")
            self._rotate_group_key()
            return True
        return False

    def get_member_info(self, node_mac: bytes) -> Optional[UAVMemberInfo]:
        """获取成员信息

        Args:
            node_mac: UAV节点MAC地址

        Returns:
            成员信息，如果不存在返回None
        """
        return self.members.get(node_mac)

    def get_active_members(self) -> List[bytes]:
        """获取所有活跃成员

        Returns:
            活跃成员MAC列表
        """
        return [mac for mac, member in self.members.items() if member.is_active]

    def get_member_count(self) -> int:
        """获取成员数量

        Returns:
            成员总数
        """
        return len(self.members)

    def get_active_member_count(self) -> int:
        """获取活跃成员数量

        Returns:
            活跃成员数量
        """
        return len(self.get_active_members())

    def get_group_key(self) -> Tuple[bytes, int]:
        """获取当前群组密钥

        Returns:
            (群组密钥, 版本号)
        """
        return self.group_key, self.group_key_version

    def get_statistics(self) -> Dict:
        """获取群组统计信息

        Returns:
            统计信息字典
        """
        total_auth = sum(m.auth_count for m in self.members.values())
        now = time.time()

        return {
            'group_id': self.group_id,
            'coordinator': self.coordinator_mac.hex(),
            'total_members': len(self.members),
            'active_members': self.get_active_member_count(),
            'total_authentications': total_auth,
            'group_key_version': self.group_key_version,
            'last_key_rotation': self.last_key_rotation,
            'time_since_rotation': now - self.last_key_rotation,
            'next_rotation_in': max(0, self.key_rotation_interval - (now - self.last_key_rotation))
        }

    def print_status(self):
        """打印群组状态"""
        stats = self.get_statistics()

        print("\n" + "=" * 80)
        print("UAV群组状态")
        print("=" * 80)
        print(f"群组ID: {stats['group_id']}")
        print(f"协调节点: {stats['coordinator']}")
        print(f"成员总数: {stats['total_members']}")
        print(f"活跃成员: {stats['active_members']}")
        print(f"总认证次数: {stats['total_authentications']}")
        print(f"群组密钥版本: {stats['group_key_version']}")
        print(f"距上次密钥轮换: {stats['time_since_rotation']:.1f}秒")
        print(f"下次轮换倒计时: {stats['next_rotation_in']:.1f}秒")
        print("=" * 80)

        if self.members:
            print("\n成员列表:")
            for mac, member in self.members.items():
                status = "✓ 活跃" if member.is_active else "✗ 不活跃"
                print(f"  {mac.hex()}: {status}, 认证{member.auth_count}次, "
                      f"上次活跃{time.time() - member.last_seen:.1f}秒前")
        print()


# 导出
__all__ = [
    'UAVSwarmManager',
    'UAVMemberInfo'
]
