"""
基于特征的MAC身份认证统一API（UAV自组织网络版）

提供简单易用的无人机节点认证和验证接口，封装三模块集成的复杂性。
适用于UAV自组织网络中的节点间相互认证。
"""

import sys
import secrets
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

# 添加路径
# 从src目录往上一级到项目根目录
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 添加feature-authentication到路径
feature_auth_path = project_root / 'feature-authentication'
if str(feature_auth_path) not in sys.path:
    sys.path.insert(0, str(feature_auth_path))

from feature_synchronization.sync.synchronization_service import SynchronizationService
from src.mode2_strong_auth import DeviceSide, VerifierSide
from src.config import AuthConfig
from src.common import AuthContext, AuthReq, AuthResult


@dataclass
class AuthenticationResponse:
    """认证响应结果

    Attributes:
        success: 认证是否成功
        reason: 失败原因（成功时为None）
        session_key: 会话密钥（成功时返回，32字节）
        node_id: UAV节点MAC地址（6字节）
        epoch: 认证时的epoch编号
        token: MAT令牌（成功时返回，可选）
        latency_ms: 认证延迟（毫秒）
        feature_key: 特征密钥（用于注册，32字节，可选）
    """
    success: bool
    reason: Optional[str] = None
    session_key: Optional[bytes] = None
    node_id: Optional[bytes] = None
    epoch: Optional[int] = None
    token: Optional[bytes] = None
    latency_ms: Optional[float] = None
    feature_key: Optional[bytes] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'success': self.success,
            'reason': self.reason,
            'session_key': self.session_key.hex() if self.session_key else None,
            'node_id': self.node_id.hex() if self.node_id else None,
            'epoch': self.epoch,
            'token_size': len(self.token) if self.token else 0,
            'latency_ms': self.latency_ms,
            'feature_key': self.feature_key.hex() if self.feature_key else None
        }


class FeatureBasedAuthenticationAPI:
    """基于特征的MAC身份认证统一API（UAV自组织网络版）

    这个类提供简单的接口用于UAV节点间的身份认证，基于物理层特征（CSI）。
    适用于无人机自组织网络中节点间的相互认证。

    使用示例:
        # UAV节点（请求认证方）
        uav_node_api = FeatureBasedAuthenticationAPI.create_uav_node(
            node_mac=b'\\x00\\x11\\x22\\x33\\x44\\x55',
            peer_mac=b'\\xAA\\xBB\\xCC\\xDD\\xEE\\xFF'
        )
        response = uav_node_api.authenticate(csi_data)

        # 对等验证节点（验证方）
        peer_verifier_api = FeatureBasedAuthenticationAPI.create_peer_verifier(
            node_mac=b'\\xAA\\xBB\\xCC\\xDD\\xEE\\xFF',
            signing_key=secrets.token_bytes(32)
        )
        response = peer_verifier_api.verify(auth_request, csi_data)
    """

    @classmethod
    def create_uav_node(cls,
                       node_mac: bytes,
                       peer_mac: bytes,
                       epoch_period_ms: int = 30000,
                       domain: str = "FeatureAuth",
                       deterministic: bool = False) -> 'UAVNodeAuthAPI':
        """创建UAV节点认证API（请求认证方）

        Args:
            node_mac: 本UAV节点MAC地址（6字节）
            peer_mac: 目标对等节点MAC地址（6字节）
            epoch_period_ms: Epoch周期（毫秒），默认30秒
            domain: 认证域标识，默认"FeatureAuth"
            deterministic: 是否使用确定性模式（仅用于测试）

        Returns:
            UAVNodeAuthAPI实例

        Raises:
            ValueError: MAC地址长度不正确
        """
        if len(node_mac) != 6:
            raise ValueError(f"node_mac必须是6字节，当前为{len(node_mac)}字节")
        if len(peer_mac) != 6:
            raise ValueError(f"peer_mac必须是6字节，当前为{len(peer_mac)}字节")

        return UAVNodeAuthAPI(
            node_mac=node_mac,
            peer_mac=peer_mac,
            epoch_period_ms=epoch_period_ms,
            domain=domain,
            deterministic=deterministic
        )

    @classmethod
    def create_peer_verifier(cls,
                            node_mac: bytes,
                            signing_key: bytes,
                            epoch_period_ms: int = 30000,
                            beacon_interval_ms: int = 5000,
                            domain: str = "FeatureAuth",
                            deterministic: bool = False) -> 'PeerVerifierAuthAPI':
        """创建对等验证节点认证API（验证方）

        Args:
            node_mac: 本验证节点MAC地址（6字节）
            signing_key: 节点签名密钥（32字节）
            epoch_period_ms: Epoch周期（毫秒），默认30秒
            beacon_interval_ms: 信标广播间隔（毫秒），默认5秒
            domain: 认证域标识，默认"FeatureAuth"
            deterministic: 是否使用确定性模式（仅用于测试）

        Returns:
            PeerVerifierAuthAPI实例

        Raises:
            ValueError: 参数长度不正确
        """
        if len(node_mac) != 6:
            raise ValueError(f"node_mac必须是6字节，当前为{len(node_mac)}字节")
        if len(signing_key) != 32:
            raise ValueError(f"signing_key必须是32字节，当前为{len(signing_key)}字节")

        return PeerVerifierAuthAPI(
            node_mac=node_mac,
            signing_key=signing_key,
            epoch_period_ms=epoch_period_ms,
            beacon_interval_ms=beacon_interval_ms,
            domain=domain,
            deterministic=deterministic
        )


class UAVNodeAuthAPI:
    """UAV节点认证API（请求认证方）

    封装UAV节点的认证请求生成逻辑。
    """

    def __init__(self,
                 node_mac: bytes,
                 peer_mac: bytes,
                 epoch_period_ms: int,
                 domain: str,
                 deterministic: bool):
        """初始化UAV节点API（内部使用，请使用create_uav_node创建）"""
        self.node_mac = node_mac
        self.peer_mac = peer_mac

        # 初始化同步服务
        self.sync_service = SynchronizationService(
            node_type='device',
            node_id=node_mac,
            delta_t=epoch_period_ms,
            domain=domain,
            deterministic_for_testing=deterministic
        )

        # 初始化认证服务
        self.auth_service = DeviceSide(
            config=AuthConfig(),
            sync_service=self.sync_service
        )

        self._seq_counter = 0

    def authenticate(self,
                    csi_measurements: np.ndarray,
                    nonce: Optional[bytes] = None) -> Tuple[bytes, AuthenticationResponse]:
        """执行UAV节点认证

        Args:
            csi_measurements: CSI测量数据，shape为(M, D)，通常为(6, 62)
                M: 帧数（通常为6）
                D: 特征维度（通常为62）
            nonce: 随机数（16字节），如果为None则自动生成

        Returns:
            (auth_request_bytes, response)
            - auth_request_bytes: 序列化的认证请求（需发送给对等节点）
            - response: 认证响应对象

        Raises:
            ValueError: CSI数据格式不正确
        """
        import time
        start_time = time.time()

        # 验证CSI数据
        if not isinstance(csi_measurements, np.ndarray):
            raise ValueError("csi_measurements必须是numpy数组")
        if len(csi_measurements.shape) != 2:
            raise ValueError(f"csi_measurements必须是2D数组，当前shape: {csi_measurements.shape}")

        # 生成nonce
        if nonce is None:
            nonce = secrets.token_bytes(16)
        elif len(nonce) != 16:
            raise ValueError(f"nonce必须是16字节，当前为{len(nonce)}字节")

        # 创建认证上下文
        self._seq_counter += 1
        context = AuthContext(
            src_mac=self.node_mac,
            dst_mac=self.peer_mac,
            epoch=0,  # 会被sync_service覆盖
            nonce=nonce,
            seq=self._seq_counter,
            alg_id='Mode2',
            ver=1,
            csi_id=int(time.time() * 1000) % 65536
        )

        try:
            # 生成认证请求
            auth_req, session_key, feature_key = self.auth_service.create_auth_request(
                dev_id=self.node_mac,
                Z_frames=csi_measurements,
                context=context
            )

            # 计算延迟
            latency_ms = (time.time() - start_time) * 1000

            # 构造响应
            response = AuthenticationResponse(
                success=True,
                session_key=session_key,
                node_id=self.node_mac,
                epoch=auth_req.epoch,
                latency_ms=latency_ms,
                feature_key=feature_key  # 包含feature_key用于注册
            )

            # 序列化认证请求
            auth_request_bytes = auth_req.serialize()

            return auth_request_bytes, response

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            response = AuthenticationResponse(
                success=False,
                reason=f"认证请求生成失败: {str(e)}",
                node_id=self.node_mac,
                latency_ms=latency_ms
            )
            return b'', response


class PeerVerifierAuthAPI:
    """对等验证节点认证API（验证方）

    封装对等验证节点的认证验证逻辑。
    """

    def __init__(self,
                 node_mac: bytes,
                 signing_key: bytes,
                 epoch_period_ms: int,
                 beacon_interval_ms: int,
                 domain: str,
                 deterministic: bool):
        """初始化对等验证节点API（内部使用，请使用create_peer_verifier创建）"""
        self.node_mac = node_mac
        self.signing_key = signing_key

        # 初始化同步服务
        self.sync_service = SynchronizationService(
            node_type='validator',
            node_id=node_mac,
            delta_t=epoch_period_ms,
            beacon_interval=beacon_interval_ms,
            domain=domain,
            deterministic_for_testing=deterministic
        )

        # 初始化认证服务
        self.auth_service = VerifierSide(
            config=AuthConfig(),
            issuer_id=node_mac,
            issuer_key=signing_key,
            sync_service=self.sync_service
        )

        self._uav_node_registry = {}

    def register_uav_node(self,
                         node_mac: bytes,
                         feature_key: bytes,
                         epoch: int = 0) -> bool:
        """注册UAV节点

        首次认证前需要注册UAV节点的特征密钥。实际部署中，这应该通过
        安全的带外渠道完成。

        Args:
            node_mac: UAV节点MAC地址（6字节）
            feature_key: UAV节点特征密钥（32字节）
            epoch: 注册时的epoch编号，默认0

        Returns:
            是否注册成功
        """
        try:
            if len(node_mac) != 6:
                return False
            if len(feature_key) != 32:
                return False

            self.auth_service.register_device(node_mac, feature_key, epoch)
            self._uav_node_registry[node_mac] = {
                'registered_at': __import__('time').time(),
                'epoch': epoch
            }
            return True
        except Exception:
            return False

    def verify(self,
              auth_request_bytes: bytes,
              csi_measurements: np.ndarray) -> AuthenticationResponse:
        """验证UAV节点认证请求

        Args:
            auth_request_bytes: 序列化的认证请求（从UAV节点接收）
            csi_measurements: 验证节点测量的CSI数据，shape为(M, D)
                注意：应与请求节点测量相同信道（信道互惠性）

        Returns:
            AuthenticationResponse: 认证响应对象

        Raises:
            ValueError: 参数格式不正确
        """
        import time
        start_time = time.time()

        # 验证CSI数据
        if not isinstance(csi_measurements, np.ndarray):
            raise ValueError("csi_measurements必须是numpy数组")
        if len(csi_measurements.shape) != 2:
            raise ValueError(f"csi_measurements必须是2D数组，当前shape: {csi_measurements.shape}")

        try:
            # 反序列化认证请求
            auth_req = AuthReq.deserialize(auth_request_bytes)

            # 执行验证
            result = self.auth_service.verify_auth_request(
                auth_req=auth_req,
                Z_frames=csi_measurements
            )

            # 计算延迟
            latency_ms = (time.time() - start_time) * 1000

            # 查找UAV节点ID（通过DevPseudo）
            node_id = None
            for uav_mac in self._uav_node_registry.keys():
                if uav_mac in self.auth_service.device_registry:
                    node_id = uav_mac
                    break

            # 构造响应
            if result.success:
                return AuthenticationResponse(
                    success=True,
                    session_key=result.session_key,
                    node_id=node_id,
                    epoch=auth_req.epoch,
                    token=result.token,
                    latency_ms=latency_ms
                )
            else:
                return AuthenticationResponse(
                    success=False,
                    reason=result.reason,
                    node_id=node_id,
                    epoch=auth_req.epoch,
                    latency_ms=latency_ms
                )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return AuthenticationResponse(
                success=False,
                reason=f"验证失败: {str(e)}",
                latency_ms=latency_ms
            )

    def get_current_epoch(self) -> int:
        """获取当前epoch编号"""
        return self.sync_service.get_current_epoch()

    def is_synchronized(self) -> bool:
        """检查是否已同步"""
        return self.sync_service.is_synchronized()


# 导出API
__all__ = [
    'FeatureBasedAuthenticationAPI',
    'AuthenticationResponse',
    'UAVNodeAuthAPI',
    'PeerVerifierAuthAPI'
]
