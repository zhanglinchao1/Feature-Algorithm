"""
密钥派生模块

使用BLAKE3和HKDF进行密钥派生和上下文绑定。
"""

import struct
from typing import Dict, Any
try:
    import blake3
    HAS_BLAKE3 = True
except ImportError:
    HAS_BLAKE3 = False
    import hashlib

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .config import FeatureEncryptionConfig


class KeyDerivation:
    """密钥派生器"""

    def __init__(self, config: FeatureEncryptionConfig):
        """
        初始化密钥派生器

        Args:
            config: 算法配置
        """
        self.config = config

    def compute_L(
        self,
        epoch: int,
        nonce: bytes
    ) -> bytes:
        """
        计算随机扰动值 L

        L = Trunc_{256}(BLAKE3(epoch || nonce))

        Args:
            epoch: 时间窗编号（4字节）
            nonce: 随机数（16字节）

        Returns:
            L: 随机扰动值（32字节）
        """
        # 验证输入
        if not isinstance(epoch, int) or epoch < 0:
            raise ValueError(f"epoch must be non-negative int, got {epoch}")
        if len(nonce) != self.config.NONCE_LENGTH:
            raise ValueError(
                f"nonce length must be {self.config.NONCE_LENGTH}, got {len(nonce)}"
            )

        # 编码epoch为4字节
        epoch_bytes = struct.pack('<I', epoch)  # 小端序，无符号整数

        # 拼接数据
        data = epoch_bytes + nonce

        # BLAKE3哈希
        hash_output = self._hash(data)

        # 截断到32字节
        L = hash_output[:32]

        return L

    def derive_feature_key(
        self,
        S: bytes,
        L: bytes,
        dom: bytes,
        srcMAC: bytes,
        dstMAC: bytes,
        ver: int,
        epoch: int
    ) -> bytes:
        """
        派生特征密钥 K

        K = HKDF-Expand(
            PRK = HKDF-Extract(salt=dom, IKM=S||L),
            info = ver||srcMAC||dstMAC||epoch,
            L = KEY_LENGTH
        )

        Args:
            S: 稳定特征串（32字节）
            L: 随机扰动值（32字节）
            dom: 域标识
            srcMAC: 源MAC地址（6字节）
            dstMAC: 目标MAC地址（6字节）
            ver: 算法版本号
            epoch: 时间窗编号

        Returns:
            K: 特征密钥（KEY_LENGTH字节）
        """
        # 验证输入
        if len(S) != 32:
            raise ValueError(f"S length must be 32 bytes, got {len(S)}")
        if len(L) != 32:
            raise ValueError(f"L length must be 32 bytes, got {len(L)}")
        if len(srcMAC) != self.config.MAC_LENGTH:
            raise ValueError(
                f"srcMAC length must be {self.config.MAC_LENGTH}, got {len(srcMAC)}"
            )
        if len(dstMAC) != self.config.MAC_LENGTH:
            raise ValueError(
                f"dstMAC length must be {self.config.MAC_LENGTH}, got {len(dstMAC)}"
            )

        # 准备IKM
        IKM = S + L  # 64 bytes

        # HKDF-Extract
        salt = dom
        hkdf_extract = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=b'',
        )
        PRK = hkdf_extract.derive(IKM)

        # 准备info
        ver_bytes = struct.pack('B', ver)  # 1 byte
        epoch_bytes = struct.pack('<I', epoch)  # 4 bytes
        info = ver_bytes + srcMAC + dstMAC + epoch_bytes  # 1+6+6+4 = 17 bytes

        # HKDF-Expand
        hkdf_expand = HKDF(
            algorithm=hashes.SHA256(),
            length=self.config.KEY_LENGTH,
            salt=None,
            info=info,
        )
        K = hkdf_expand.derive(PRK)

        return K

    def derive_session_key(
        self,
        K: bytes,
        epoch: int,
        Ci: int
    ) -> bytes:
        """
        派生会话密钥 Ks

        Ks = HKDF-Expand(
            PRK = K,
            info = "SessionKey"||epoch||Ci,
            L = KEY_LENGTH
        )

        Args:
            K: 特征密钥（KEY_LENGTH字节）
            epoch: 时间窗编号
            Ci: 哈希链计数器

        Returns:
            Ks: 会话密钥（KEY_LENGTH字节）
        """
        # 验证输入
        if len(K) != self.config.KEY_LENGTH:
            raise ValueError(
                f"K length must be {self.config.KEY_LENGTH}, got {len(K)}"
            )

        # 准备info
        session_key_label = self.config.SESSION_KEY_INFO.encode('utf-8')
        epoch_bytes = struct.pack('<I', epoch)  # 4 bytes
        ci_bytes = struct.pack('<I', Ci)  # 4 bytes
        info = session_key_label + epoch_bytes + ci_bytes

        # HKDF-Expand (PRK = K)
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=self.config.KEY_LENGTH,
            salt=None,
            info=info,
        )
        Ks = hkdf.derive(K)

        return Ks

    def generate_digest(
        self,
        mask_bytes: bytes,
        theta_L: bytes,
        theta_H: bytes,
        algID: int = 1,
        ver: int = None
    ) -> bytes:
        """
        生成一致性摘要

        digest = Trunc_{DIGEST_LENGTH}(BLAKE3(mask||theta_L||theta_H||algID||ver))

        Args:
            mask_bytes: 特征掩码字节串
            theta_L: 下门限数组字节串
            theta_H: 上门限数组字节串
            algID: 算法ID
            ver: 版本号，默认使用配置

        Returns:
            digest: 一致性摘要（DIGEST_LENGTH字节）
        """
        if ver is None:
            ver = self.config.VERSION

        # 拼接数据
        algID_bytes = struct.pack('B', algID)
        ver_bytes = struct.pack('B', ver)

        data = mask_bytes + theta_L + theta_H + algID_bytes + ver_bytes

        # BLAKE3哈希
        hash_output = self._hash(data)

        # 截断
        digest = hash_output[:self.config.DIGEST_LENGTH]

        return digest

    def _hash(self, data: bytes) -> bytes:
        """
        内部哈希函数

        Args:
            data: 待哈希数据

        Returns:
            hash_output: 哈希值（32字节）
        """
        if self.config.HASH_ALGORITHM == 'blake3' and HAS_BLAKE3:
            return blake3.blake3(data).digest()
        else:
            # 回退到SHA256
            return hashlib.sha256(data).digest()

    def bits_to_bytes(self, bits: list) -> bytes:
        """
        将比特列表转换为字节串

        Args:
            bits: 比特列表

        Returns:
            bytes: 字节串
        """
        # 补齐到8的倍数
        padded_bits = bits + [0] * ((-len(bits)) % 8)

        bytes_array = bytearray()
        for i in range(0, len(padded_bits), 8):
            byte = 0
            for j in range(8):
                byte |= padded_bits[i + j] << j
            bytes_array.append(byte)

        return bytes(bytes_array)


# 导出
__all__ = ['KeyDerivation']
