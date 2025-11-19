"""
共同数据结构定义

定义认证模块使用的所有数据类。
"""

from dataclasses import dataclass, field
from typing import Optional
import struct


# ==================== 基础数据结构 ====================

@dataclass
class DeviceIdentity:
    """设备标识

    Attributes:
        dev_id: 真实设备标识（MAC地址，6字节）
        dev_pseudo: 伪名（可选，12字节）
        epoch: 时间窗编号
    """
    dev_id: bytes                    # 6 bytes MAC地址
    dev_pseudo: Optional[bytes] = None   # 12 bytes 伪名
    epoch: int = 0

    def __post_init__(self):
        """验证"""
        if len(self.dev_id) != 6:
            raise ValueError(f"dev_id must be 6 bytes (MAC address), got {len(self.dev_id)}")

        if self.dev_pseudo is not None and len(self.dev_pseudo) != 12:
            raise ValueError(f"dev_pseudo must be 12 bytes, got {len(self.dev_pseudo)}")

        if self.epoch < 0 or self.epoch > 2**32 - 1:
            raise ValueError(f"epoch must be in [0, 2^32-1], got {self.epoch}")


@dataclass
class AuthContext:
    """认证上下文

    包含认证过程中需要的所有上下文信息。

    Attributes:
        src_mac: 源MAC地址（6字节）
        dst_mac: 目标MAC地址（6字节）
        epoch: 时间窗编号（4字节）
        nonce: 随机数（16字节）
        seq: 序号（4字节）
        alg_id: 算法标识（字符串）
        ver: 版本号（1字节）
        csi_id: CSI窗口标识（4字节，使用序号）
    """
    src_mac: bytes      # 6 bytes
    dst_mac: bytes      # 6 bytes
    epoch: int          # 4 bytes
    nonce: bytes        # 16 bytes
    seq: int            # 4 bytes
    alg_id: str         # 算法标识
    ver: int            # 1 byte
    csi_id: int         # 4 bytes (使用seq作为CSI窗口标识)

    def __post_init__(self):
        """验证"""
        if len(self.src_mac) != 6:
            raise ValueError(f"src_mac must be 6 bytes, got {len(self.src_mac)}")

        if len(self.dst_mac) != 6:
            raise ValueError(f"dst_mac must be 6 bytes, got {len(self.dst_mac)}")

        if self.epoch < 0 or self.epoch > 2**32 - 1:
            raise ValueError(f"epoch must be in [0, 2^32-1], got {self.epoch}")

        if len(self.nonce) != 16:
            raise ValueError(f"nonce must be 16 bytes, got {len(self.nonce)}")

        if self.seq < 0 or self.seq > 2**32 - 1:
            raise ValueError(f"seq must be in [0, 2^32-1], got {self.seq}")

        if self.ver < 0 or self.ver > 255:
            raise ValueError(f"ver must be in [0, 255], got {self.ver}")

        if self.csi_id < 0 or self.csi_id > 2**32 - 1:
            raise ValueError(f"csi_id must be in [0, 2^32-1], got {self.csi_id}")

    def to_bytes(self) -> bytes:
        """序列化为字节串

        Returns:
            bytes: 序列化后的字节串
        """
        alg_id_bytes = self.alg_id.encode('utf-8')
        alg_id_len = len(alg_id_bytes)

        return (
            self.src_mac +
            self.dst_mac +
            struct.pack('<I', self.epoch) +
            self.nonce +
            struct.pack('<I', self.seq) +
            struct.pack('<B', alg_id_len) +
            alg_id_bytes +
            struct.pack('<B', self.ver) +
            struct.pack('<I', self.csi_id)
        )


@dataclass
class AuthResult:
    """认证结果

    Attributes:
        success: 是否认证成功
        mode: 使用的认证模式（"mode1" 或 "mode2"）
        token: 令牌（Token_fast或MAT的序列化）
        session_key: 会话密钥Ks（可选）
        reason: 失败原因（成功时为None）
    """
    success: bool
    mode: str                          # "mode1" or "mode2"
    token: Optional[bytes] = None      # 令牌
    session_key: Optional[bytes] = None    # 会话密钥Ks
    reason: Optional[str] = None       # 失败原因

    def __post_init__(self):
        """验证"""
        if self.mode not in ['mode1', 'mode2']:
            raise ValueError(f"mode must be 'mode1' or 'mode2', got {self.mode}")

        if self.success:
            if self.token is None:
                raise ValueError("token must not be None when success=True")
            if self.reason is not None:
                raise ValueError("reason should be None when success=True")
        else:
            if self.reason is None:
                raise ValueError("reason must not be None when success=False")


# ==================== 模式一数据结构 ====================

@dataclass
class RFFJudgment:
    """物理层RFF判定结果

    Attributes:
        dev_id: 设备标识
        rff_pass: RFF是否通过
        rff_score: RFF匹配得分（0.0-1.0）
        snr: 信噪比（dB）
        ver: RFF模型版本
        timestamp: 时间戳（Unix时间）
    """
    dev_id: bytes
    rff_pass: bool
    rff_score: float
    snr: float = 0.0
    ver: str = "1.0"
    timestamp: int = 0

    def __post_init__(self):
        """验证"""
        if len(self.dev_id) != 6:
            raise ValueError(f"dev_id must be 6 bytes, got {len(self.dev_id)}")

        if not 0.0 <= self.rff_score <= 1.0:
            raise ValueError(f"rff_score must be in [0.0, 1.0], got {self.rff_score}")


@dataclass
class TokenFast:
    """快速令牌（模式一）

    Attributes:
        dev_id: 设备标识（6字节）
        t_start: 开始时间（Unix时间戳，4字节）
        t_expire: 过期时间（Unix时间戳，4字节）
        policy: 策略标识（字符串）
        mac: 完整性校验值（16字节）
    """
    dev_id: bytes       # 6 bytes
    t_start: int        # 4 bytes
    t_expire: int       # 4 bytes
    policy: str         # 策略标识
    mac: bytes          # 16 bytes

    def __post_init__(self):
        """验证"""
        if len(self.dev_id) != 6:
            raise ValueError(f"dev_id must be 6 bytes, got {len(self.dev_id)}")

        if self.t_start < 0 or self.t_start > 2**32 - 1:
            raise ValueError(f"t_start must be in [0, 2^32-1], got {self.t_start}")

        if self.t_expire < 0 or self.t_expire > 2**32 - 1:
            raise ValueError(f"t_expire must be in [0, 2^32-1], got {self.t_expire}")

        if self.t_expire <= self.t_start:
            raise ValueError(f"t_expire must be > t_start")

        if len(self.mac) != 16:
            raise ValueError(f"mac must be 16 bytes, got {len(self.mac)}")

    def serialize(self) -> bytes:
        """序列化为字节串

        Returns:
            bytes: 序列化后的字节串
        """
        policy_bytes = self.policy.encode('utf-8')
        policy_len = len(policy_bytes)

        return (
            self.dev_id +
            struct.pack('<I', self.t_start) +
            struct.pack('<I', self.t_expire) +
            struct.pack('<B', policy_len) +
            policy_bytes +
            self.mac
        )

    @staticmethod
    def deserialize(data: bytes) -> 'TokenFast':
        """从字节串反序列化

        Args:
            data: 字节串

        Returns:
            TokenFast: 反序列化的令牌

        Raises:
            ValueError: 数据格式错误
        """
        if len(data) < 6 + 4 + 4 + 1 + 16:
            raise ValueError(f"Invalid TokenFast data length: {len(data)}")

        offset = 0

        dev_id = data[offset:offset + 6]
        offset += 6

        t_start = struct.unpack('<I', data[offset:offset + 4])[0]
        offset += 4

        t_expire = struct.unpack('<I', data[offset:offset + 4])[0]
        offset += 4

        policy_len = data[offset]
        offset += 1

        policy = data[offset:offset + policy_len].decode('utf-8')
        offset += policy_len

        mac = data[offset:offset + 16]

        return TokenFast(
            dev_id=dev_id,
            t_start=t_start,
            t_expire=t_expire,
            policy=policy,
            mac=mac
        )


# ==================== 模式二数据结构 ====================

@dataclass
class AuthReq:
    """认证请求报文（模式二）

    Attributes:
        dev_pseudo: 伪名（12字节）
        csi_id: CSI窗口标识（4字节）
        epoch: 时间窗编号（4字节）
        nonce: 随机数（16字节）
        seq: 序号（4字节）
        alg_id: 算法标识（字符串）
        ver: 版本号（1字节）
        digest: 配置摘要（32字节）
        tag: 认证标签（16字节）
    """
    dev_pseudo: bytes   # 12 bytes
    csi_id: int         # 4 bytes
    epoch: int          # 4 bytes
    nonce: bytes        # 16 bytes
    seq: int            # 4 bytes
    alg_id: str         # 算法标识
    ver: int            # 1 byte
    digest: bytes       # 32 bytes
    tag: bytes          # 16 bytes

    def __post_init__(self):
        """验证"""
        if len(self.dev_pseudo) != 12:
            raise ValueError(f"dev_pseudo must be 12 bytes, got {len(self.dev_pseudo)}")

        if self.csi_id < 0 or self.csi_id > 2**32 - 1:
            raise ValueError(f"csi_id must be in [0, 2^32-1], got {self.csi_id}")

        if self.epoch < 0 or self.epoch > 2**32 - 1:
            raise ValueError(f"epoch must be in [0, 2^32-1], got {self.epoch}")

        if len(self.nonce) != 16:
            raise ValueError(f"nonce must be 16 bytes, got {len(self.nonce)}")

        if self.seq < 0 or self.seq > 2**32 - 1:
            raise ValueError(f"seq must be in [0, 2^32-1], got {self.seq}")

        if self.ver < 0 or self.ver > 255:
            raise ValueError(f"ver must be in [0, 255], got {self.ver}")

        if len(self.digest) not in [8, 16, 32]:
            raise ValueError(f"digest must be 8/16/32 bytes, got {len(self.digest)}")

        if len(self.tag) not in [12, 16, 20, 24, 32]:
            raise ValueError(f"tag must be 12-32 bytes, got {len(self.tag)}")

    def serialize(self) -> bytes:
        """序列化为字节串

        Returns:
            bytes: 序列化后的字节串
        """
        alg_id_bytes = self.alg_id.encode('utf-8')
        alg_id_len = len(alg_id_bytes)

        return (
            self.dev_pseudo +
            struct.pack('<I', self.csi_id) +
            struct.pack('<I', self.epoch) +
            self.nonce +
            struct.pack('<I', self.seq) +
            struct.pack('<B', alg_id_len) +
            alg_id_bytes +
            struct.pack('<B', self.ver) +
            self.digest +
            self.tag
        )

    @staticmethod
    def deserialize(data: bytes) -> 'AuthReq':
        """从字节串反序列化

        Args:
            data: 字节串

        Returns:
            AuthReq: 反序列化的认证请求

        Raises:
            ValueError: 数据格式错误
        """
        if len(data) < 12 + 4 + 4 + 16 + 4 + 1 + 1 + 32 + 12:
            raise ValueError(f"Invalid AuthReq data length: {len(data)}")

        offset = 0

        dev_pseudo = data[offset:offset + 12]
        offset += 12

        csi_id = struct.unpack('<I', data[offset:offset + 4])[0]
        offset += 4

        epoch = struct.unpack('<I', data[offset:offset + 4])[0]
        offset += 4

        nonce = data[offset:offset + 16]
        offset += 16

        seq = struct.unpack('<I', data[offset:offset + 4])[0]
        offset += 4

        alg_id_len = data[offset]
        offset += 1

        alg_id = data[offset:offset + alg_id_len].decode('utf-8')
        offset += alg_id_len

        ver = data[offset]
        offset += 1

        digest = data[offset:offset + 32]
        offset += 32

        tag = data[offset:]

        return AuthReq(
            dev_pseudo=dev_pseudo,
            csi_id=csi_id,
            epoch=epoch,
            nonce=nonce,
            seq=seq,
            alg_id=alg_id,
            ver=ver,
            digest=digest,
            tag=tag
        )


@dataclass
class MAT:
    """准入令牌（MAC Admission Token，模式二）

    Attributes:
        issuer: 签发者标识（6字节MAC地址）
        dev_pseudo: 设备伪名（12字节）
        epoch: 时间窗编号（4字节）
        ttl: 有效期（秒，4字节）
        mat_id: 令牌唯一标识（16字节）
        signature: 签名（32字节）
    """
    issuer: bytes       # 6 bytes
    dev_pseudo: bytes   # 12 bytes
    epoch: int          # 4 bytes
    ttl: int            # 4 bytes
    mat_id: bytes       # 16 bytes
    signature: bytes    # 32 bytes

    def __post_init__(self):
        """验证"""
        if len(self.issuer) != 6:
            raise ValueError(f"issuer must be 6 bytes, got {len(self.issuer)}")

        if len(self.dev_pseudo) != 12:
            raise ValueError(f"dev_pseudo must be 12 bytes, got {len(self.dev_pseudo)}")

        if self.epoch < 0 or self.epoch > 2**32 - 1:
            raise ValueError(f"epoch must be in [0, 2^32-1], got {self.epoch}")

        if self.ttl <= 0:
            raise ValueError(f"ttl must be positive, got {self.ttl}")

        if len(self.mat_id) != 16:
            raise ValueError(f"mat_id must be 16 bytes, got {len(self.mat_id)}")

        if len(self.signature) != 32:
            raise ValueError(f"signature must be 32 bytes, got {len(self.signature)}")

    def serialize(self) -> bytes:
        """序列化为字节串

        Returns:
            bytes: 序列化后的字节串
        """
        return (
            self.issuer +
            self.dev_pseudo +
            struct.pack('<I', self.epoch) +
            struct.pack('<I', self.ttl) +
            self.mat_id +
            self.signature
        )

    @staticmethod
    def deserialize(data: bytes) -> 'MAT':
        """从字节串反序列化

        Args:
            data: 字节串

        Returns:
            MAT: 反序列化的MAT

        Raises:
            ValueError: 数据格式错误
        """
        expected_len = 6 + 12 + 4 + 4 + 16 + 32
        if len(data) != expected_len:
            raise ValueError(f"Invalid MAT data length: expected {expected_len}, got {len(data)}")

        offset = 0

        issuer = data[offset:offset + 6]
        offset += 6

        dev_pseudo = data[offset:offset + 12]
        offset += 12

        epoch = struct.unpack('<I', data[offset:offset + 4])[0]
        offset += 4

        ttl = struct.unpack('<I', data[offset:offset + 4])[0]
        offset += 4

        mat_id = data[offset:offset + 16]
        offset += 16

        signature = data[offset:offset + 32]

        return MAT(
            issuer=issuer,
            dev_pseudo=dev_pseudo,
            epoch=epoch,
            ttl=ttl,
            mat_id=mat_id,
            signature=signature
        )


# 导出
__all__ = [
    'DeviceIdentity',
    'AuthContext',
    'AuthResult',
    'RFFJudgment',
    'TokenFast',
    'AuthReq',
    'MAT',
]
