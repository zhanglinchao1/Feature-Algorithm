"""
UAV移动性支持 - 快速切换和漫游

提供UAV在群组内移动时的快速切换、MAT令牌漫游等功能。
"""

import time
import secrets
from typing import Optional, Dict, Tuple
from dataclasses import dataclass, field
import numpy as np

from authentication_api import (
    FeatureBasedAuthenticationAPI,
    UAVNodeAuthAPI,
    PeerVerifierAuthAPI,
    AuthenticationResponse
)


@dataclass
class HandoverContext:
    """切换上下文"""
    old_peer_mac: bytes
    new_peer_mac: bytes
    mat_token: bytes
    session_key: bytes
    handover_started_at: float = field(default_factory=time.time)
    handover_completed: bool = False
    handover_latency_ms: Optional[float] = None


class UAVMobilitySupport:
    """UAV移动性支持

    支持UAV在对等节点间快速切换和漫游，减少重新认证开销。
    """

    def __init__(self,
                 node_mac: bytes,
                 fast_handover_enabled: bool = True,
                 mat_token_cache_time: int = 300):
        """初始化移动性支持

        Args:
            node_mac: 本UAV节点MAC地址（6字节）
            fast_handover_enabled: 是否启用快速切换
            mat_token_cache_time: MAT令牌缓存时间（秒），默认5分钟
        """
        self.node_mac = node_mac
        self.fast_handover_enabled = fast_handover_enabled
        self.mat_token_cache_time = mat_token_cache_time

        # MAT令牌缓存 {peer_mac: (mat_token, session_key, timestamp)}
        self.mat_token_cache: Dict[bytes, Tuple[bytes, bytes, float]] = {}

        # 当前连接的对等节点
        self.current_peer: Optional[bytes] = None
        self.current_session_key: Optional[bytes] = None
        self.current_mat_token: Optional[bytes] = None

        # 切换历史
        self.handover_history: list[HandoverContext] = []

        print(f"[UAVMobilitySupport] 初始化完成")
        print(f"  节点MAC: {node_mac.hex()}")
        print(f"  快速切换: {'启用' if fast_handover_enabled else '禁用'}")

    def cache_mat_token(self,
                       peer_mac: bytes,
                       mat_token: bytes,
                       session_key: bytes):
        """缓存MAT令牌

        Args:
            peer_mac: 对等节点MAC地址
            mat_token: MAT令牌
            session_key: 会话密钥
        """
        self.mat_token_cache[peer_mac] = (mat_token, session_key, time.time())
        print(f"[UAVMobilitySupport] MAT令牌已缓存: {peer_mac.hex()}")

    def get_cached_mat_token(self, peer_mac: bytes) -> Optional[Tuple[bytes, bytes]]:
        """获取缓存的MAT令牌

        Args:
            peer_mac: 对等节点MAC地址

        Returns:
            (mat_token, session_key) 如果缓存有效，否则None
        """
        if peer_mac not in self.mat_token_cache:
            return None

        mat_token, session_key, cached_at = self.mat_token_cache[peer_mac]

        # 检查是否过期
        if time.time() - cached_at > self.mat_token_cache_time:
            print(f"[UAVMobilitySupport] MAT令牌已过期: {peer_mac.hex()}")
            del self.mat_token_cache[peer_mac]
            return None

        print(f"[UAVMobilitySupport] 使用缓存的MAT令牌: {peer_mac.hex()}")
        return mat_token, session_key

    def fast_handover(self,
                     old_peer_mac: bytes,
                     new_peer_mac: bytes,
                     mat_token: Optional[bytes] = None,
                     session_key: Optional[bytes] = None) -> Tuple[bool, Optional[HandoverContext]]:
        """快速切换到新的对等节点

        使用已有的MAT令牌进行快速切换，避免完整的重新认证。

        Args:
            old_peer_mac: 旧对等节点MAC地址
            new_peer_mac: 新对等节点MAC地址
            mat_token: MAT令牌（可选，如果None则从缓存获取）
            session_key: 会话密钥（可选）

        Returns:
            (是否成功, 切换上下文)
        """
        if not self.fast_handover_enabled:
            print(f"[UAVMobilitySupport] 快速切换未启用")
            return False, None

        start_time = time.time()

        # 尝试从缓存获取MAT令牌
        if mat_token is None or session_key is None:
            cached = self.get_cached_mat_token(old_peer_mac)
            if cached:
                mat_token, session_key = cached
            else:
                print(f"[UAVMobilitySupport] 无可用的MAT令牌，无法快速切换")
                return False, None

        # 创建切换上下文
        context = HandoverContext(
            old_peer_mac=old_peer_mac,
            new_peer_mac=new_peer_mac,
            mat_token=mat_token,
            session_key=session_key
        )

        # 更新当前连接
        self.current_peer = new_peer_mac
        self.current_session_key = session_key
        self.current_mat_token = mat_token

        # 缓存MAT令牌到新对等节点
        self.cache_mat_token(new_peer_mac, mat_token, session_key)

        # 完成切换
        context.handover_completed = True
        context.handover_latency_ms = (time.time() - start_time) * 1000

        # 记录历史
        self.handover_history.append(context)

        print(f"[UAVMobilitySupport] 快速切换成功")
        print(f"  {old_peer_mac.hex()} → {new_peer_mac.hex()}")
        print(f"  延迟: {context.handover_latency_ms:.2f}ms")

        return True, context

    def full_handover(self,
                     old_peer_mac: bytes,
                     new_peer_mac: bytes,
                     new_peer_api: UAVNodeAuthAPI,
                     csi_measurements: np.ndarray) -> Tuple[bool, Optional[HandoverContext], AuthenticationResponse]:
        """完整切换到新的对等节点（包含重新认证）

        Args:
            old_peer_mac: 旧对等节点MAC地址
            new_peer_mac: 新对等节点MAC地址
            new_peer_api: 新对等节点的UAVNodeAuthAPI
            csi_measurements: CSI测量数据

        Returns:
            (是否成功, 切换上下文, 认证响应)
        """
        start_time = time.time()

        print(f"[UAVMobilitySupport] 执行完整切换（重新认证）")
        print(f"  {old_peer_mac.hex()} → {new_peer_mac.hex()}")

        # 执行完整认证
        auth_request, response = new_peer_api.authenticate(csi_measurements)

        if not response.success:
            print(f"[UAVMobilitySupport] 切换失败: {response.reason}")
            return False, None, response

        # 创建切换上下文
        context = HandoverContext(
            old_peer_mac=old_peer_mac,
            new_peer_mac=new_peer_mac,
            mat_token=response.token or b'',
            session_key=response.session_key
        )

        # 更新当前连接
        self.current_peer = new_peer_mac
        self.current_session_key = response.session_key
        self.current_mat_token = response.token

        # 缓存新的MAT令牌
        if response.token:
            self.cache_mat_token(new_peer_mac, response.token, response.session_key)

        # 完成切换
        context.handover_completed = True
        context.handover_latency_ms = (time.time() - start_time) * 1000

        # 记录历史
        self.handover_history.append(context)

        print(f"[UAVMobilitySupport] 完整切换成功")
        print(f"  延迟: {context.handover_latency_ms:.2f}ms")

        return True, context, response

    def smart_handover(self,
                      old_peer_mac: bytes,
                      new_peer_mac: bytes,
                      new_peer_api: Optional[UAVNodeAuthAPI] = None,
                      csi_measurements: Optional[np.ndarray] = None) -> Tuple[bool, str]:
        """智能切换（自动选择快速切换或完整切换）

        Args:
            old_peer_mac: 旧对等节点MAC地址
            new_peer_mac: 新对等节点MAC地址
            new_peer_api: 新对等节点API（完整切换需要）
            csi_measurements: CSI测量数据（完整切换需要）

        Returns:
            (是否成功, 切换方式)
        """
        # 尝试快速切换
        if self.fast_handover_enabled:
            success, context = self.fast_handover(old_peer_mac, new_peer_mac)
            if success:
                return True, "fast_handover"

        # 快速切换失败，尝试完整切换
        if new_peer_api and csi_measurements is not None:
            print(f"[UAVMobilitySupport] 快速切换不可用，执行完整切换")
            success, context, response = self.full_handover(
                old_peer_mac, new_peer_mac, new_peer_api, csi_measurements
            )
            if success:
                return True, "full_handover"
            else:
                return False, "failed"
        else:
            print(f"[UAVMobilitySupport] 缺少完整切换所需参数")
            return False, "insufficient_params"

    def clear_mat_token_cache(self):
        """清除所有MAT令牌缓存"""
        count = len(self.mat_token_cache)
        self.mat_token_cache.clear()
        print(f"[UAVMobilitySupport] 已清除 {count} 个MAT令牌缓存")

    def cleanup_expired_tokens(self) -> int:
        """清理过期的MAT令牌

        Returns:
            清理的令牌数量
        """
        now = time.time()
        expired = []

        for peer_mac, (_, _, cached_at) in self.mat_token_cache.items():
            if now - cached_at > self.mat_token_cache_time:
                expired.append(peer_mac)

        for peer_mac in expired:
            del self.mat_token_cache[peer_mac]

        if expired:
            print(f"[UAVMobilitySupport] 清理了 {len(expired)} 个过期MAT令牌")

        return len(expired)

    def get_handover_statistics(self) -> Dict:
        """获取切换统计信息

        Returns:
            统计信息字典
        """
        total_handovers = len(self.handover_history)
        successful_handovers = sum(1 for h in self.handover_history if h.handover_completed)

        if successful_handovers > 0:
            avg_latency = sum(h.handover_latency_ms for h in self.handover_history
                            if h.handover_completed) / successful_handovers
        else:
            avg_latency = 0

        return {
            'node_mac': self.node_mac.hex(),
            'total_handovers': total_handovers,
            'successful_handovers': successful_handovers,
            'failed_handovers': total_handovers - successful_handovers,
            'average_latency_ms': avg_latency,
            'cached_tokens': len(self.mat_token_cache),
            'current_peer': self.current_peer.hex() if self.current_peer else None
        }

    def print_statistics(self):
        """打印统计信息"""
        stats = self.get_handover_statistics()

        print("\n" + "=" * 80)
        print("UAV移动性统计")
        print("=" * 80)
        print(f"节点MAC: {stats['node_mac']}")
        print(f"当前对等节点: {stats['current_peer'] or '无'}")
        print(f"总切换次数: {stats['total_handovers']}")
        print(f"成功切换: {stats['successful_handovers']}")
        print(f"失败切换: {stats['failed_handovers']}")
        print(f"平均延迟: {stats['average_latency_ms']:.2f}ms")
        print(f"缓存令牌数: {stats['cached_tokens']}")
        print("=" * 80)

        if self.handover_history:
            print("\n最近5次切换:")
            for h in self.handover_history[-5:]:
                status = "✓" if h.handover_completed else "✗"
                print(f"  {status} {h.old_peer_mac.hex()[:12]}... → "
                      f"{h.new_peer_mac.hex()[:12]}..., "
                      f"{h.handover_latency_ms:.2f}ms")
        print()


# 导出
__all__ = [
    'UAVMobilitySupport',
    'HandoverContext'
]
