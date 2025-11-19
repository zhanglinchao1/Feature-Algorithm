"""
签名和验签模块
"""
import hashlib
import hmac
from typing import Optional


class SimpleHMAC:
    """简单的HMAC签名实现"""

    def __init__(self, key: bytes, hash_algo=hashlib.sha256):
        """
        初始化HMAC

        Args:
            key: 签名密钥
            hash_algo: 哈希算法
        """
        self.key = key
        self.hash_algo = hash_algo

    def sign(self, data: bytes) -> bytes:
        """
        对数据签名

        Args:
            data: 待签名数据

        Returns:
            签名值
        """
        return hmac.new(self.key, data, self.hash_algo).digest()

    def verify(self, data: bytes, signature: bytes) -> bool:
        """
        验证签名

        Args:
            data: 数据
            signature: 签名值

        Returns:
            验证是否通过
        """
        expected = self.sign(data)
        return hmac.compare_digest(expected, signature)


class AggregateSignature:
    """
    聚合签名（简化版）

    在实际部署中，应使用BLS签名等真正的聚合签名方案
    这里使用多个HMAC的XOR作为简化实现
    """

    @staticmethod
    def aggregate(signatures: list[bytes]) -> bytes:
        """
        聚合多个签名

        Args:
            signatures: 签名列表

        Returns:
            聚合后的签名
        """
        if not signatures:
            return b''

        # 简化实现：对所有签名做XOR
        result = bytearray(signatures[0])
        for sig in signatures[1:]:
            if len(sig) != len(result):
                raise ValueError("Signature length mismatch")
            for i in range(len(result)):
                result[i] ^= sig[i]

        return bytes(result)

    @staticmethod
    def verify_aggregate(data: bytes, aggregate_sig: bytes,
                        public_keys: list[bytes],
                        threshold: Optional[int] = None) -> bool:
        """
        验证聚合签名

        Args:
            data: 原始数据
            aggregate_sig: 聚合签名
            public_keys: 公钥列表
            threshold: 门限值（可选）

        Returns:
            验证是否通过
        """
        # 简化实现：重新计算所有签名并聚合
        individual_sigs = []
        for key in public_keys:
            signer = SimpleHMAC(key)
            individual_sigs.append(signer.sign(data))

        expected = AggregateSignature.aggregate(individual_sigs)
        return hmac.compare_digest(expected, aggregate_sig)


def compute_hmac_tag(key: bytes, *data_parts: bytes) -> bytes:
    """
    计算HMAC标签

    Args:
        key: 密钥
        *data_parts: 数据片段

    Returns:
        HMAC标签 (32字节)
    """
    h = hmac.new(key, digestmod=hashlib.sha256)
    for part in data_parts:
        h.update(part)
    return h.digest()


def truncate_tag(tag: bytes, length: int) -> bytes:
    """
    截断标签

    Args:
        tag: 完整标签
        length: 目标长度

    Returns:
        截断后的标签
    """
    return tag[:length]
