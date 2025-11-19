"""
HKDF密钥派生函数
"""
import hashlib
import hmac
from typing import Optional


class HKDF:
    """
    HKDF密钥派生函数 (RFC 5869)
    """

    def __init__(self, hash_algo=hashlib.sha256):
        """
        初始化HKDF

        Args:
            hash_algo: 哈希算法，默认SHA256
        """
        self.hash_algo = hash_algo
        self.hash_len = hash_algo().digest_size

    def extract(self, salt: Optional[bytes], ikm: bytes) -> bytes:
        """
        HKDF-Extract步骤

        Args:
            salt: 盐值（可选）
            ikm: 输入密钥材料

        Returns:
            伪随机密钥PRK
        """
        if salt is None or len(salt) == 0:
            salt = bytes([0] * self.hash_len)

        return hmac.new(salt, ikm, self.hash_algo).digest()

    def expand(self, prk: bytes, info: bytes, length: int) -> bytes:
        """
        HKDF-Expand步骤

        Args:
            prk: 伪随机密钥
            info: 上下文信息
            length: 输出长度

        Returns:
            派生的密钥材料
        """
        if length > 255 * self.hash_len:
            raise ValueError("Length too long")

        n = (length + self.hash_len - 1) // self.hash_len
        okm = b''
        t = b''

        for i in range(1, n + 1):
            t = hmac.new(prk, t + info + bytes([i]), self.hash_algo).digest()
            okm += t

        return okm[:length]

    def derive(self, ikm: bytes, length: int,
               salt: Optional[bytes] = None,
               info: Optional[bytes] = None) -> bytes:
        """
        一步完成HKDF派生

        Args:
            ikm: 输入密钥材料
            length: 输出长度
            salt: 盐值（可选）
            info: 上下文信息（可选）

        Returns:
            派生的密钥材料
        """
        if info is None:
            info = b''

        prk = self.extract(salt, ikm)
        return self.expand(prk, info, length)


def blake3_hash(data: bytes) -> bytes:
    """
    BLAKE3哈希函数（使用SHA3-256模拟）

    注意：这是一个简化实现，生产环境应使用真实的BLAKE3库
    """
    return hashlib.sha3_256(data).digest()


def derive_feature_key(stable_feature: bytes, random_perturbation: bytes,
                      domain: str, src_mac: bytes, dst_mac: bytes,
                      version: int) -> bytes:
    """
    派生特征密钥K

    K = HKDF(S || L; salt=dom; info=srcMAC||dstMAC||ver)

    Args:
        stable_feature: 稳定特征串S
        random_perturbation: 随机扰动值L
        domain: 域标识
        src_mac: 源MAC地址
        dst_mac: 目标MAC地址
        version: 算法版本

    Returns:
        特征密钥K (32字节)
    """
    hkdf = HKDF()

    # IKM = S || L
    ikm = stable_feature + random_perturbation

    # salt = domain
    salt = domain.encode('utf-8')

    # info = srcMAC || dstMAC || version
    info = src_mac + dst_mac + version.to_bytes(4, 'big')

    return hkdf.derive(ikm, 32, salt, info)


def derive_session_key(feature_key: bytes, epoch: int,
                       hash_chain_counter: int) -> bytes:
    """
    派生会话密钥Ks

    Ks = HKDF(K; info=epoch||Ci)

    Args:
        feature_key: 特征密钥K
        epoch: 时间窗编号
        hash_chain_counter: 哈希链计数器Ci

    Returns:
        会话密钥Ks (32字节)
    """
    hkdf = HKDF()

    # info = epoch || Ci
    info = epoch.to_bytes(4, 'big') + hash_chain_counter.to_bytes(4, 'big')

    return hkdf.derive(feature_key, 32, info=info)


def truncate(data: bytes, length: int) -> bytes:
    """截断函数"""
    return data[:length]
