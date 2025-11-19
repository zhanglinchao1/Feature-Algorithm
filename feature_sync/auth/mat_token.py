"""
MAT令牌模块
"""
from dataclasses import dataclass
from typing import List

from ..utils.serialization import TLVEncoder, TLVDecoder
from ..crypto.signatures import AggregateSignature, compute_hmac_tag


@dataclass
class MATToken:
    """准入令牌（MAC Authentication Token）"""

    issuer_set: List[bytes]       # 签发验证节点集合（每个6字节）
    device_pseudonym: bytes       # 设备伪名(12字节)
    epoch: int                    # 绑定的epoch
    ttl: int                      # 有效期(ms)
    region: str                   # 区域标识
    mat_id: bytes                 # 令牌唯一ID(16字节)
    issued_at: int                # 签发时间戳(ms)
    signature: bytes              # 聚合签名(32字节)

    def is_valid(self, now: int, current_epoch: int, tolerance: int = 1) -> bool:
        """
        检查令牌有效性

        Args:
            now: 当前时间戳(ms)
            current_epoch: 当前epoch
            tolerance: epoch容忍度，默认±1

        Returns:
            是否有效
        """
        # 检查时间
        if now > self.issued_at + self.ttl:
            return False

        # 检查epoch（允许相邻epoch）
        if abs(current_epoch - self.epoch) > tolerance:
            return False

        return True

    def pack(self) -> bytes:
        """序列化"""
        encoder = TLVEncoder()

        # 签发者集合
        data = encoder.encode_uint16(len(self.issuer_set))
        for issuer in self.issuer_set:
            data += encoder.encode_bytes_fixed(issuer, 6)

        # 其他字段
        data += encoder.encode_bytes_fixed(self.device_pseudonym, 12)
        data += encoder.encode_uint32(self.epoch)
        data += encoder.encode_uint32(self.ttl)
        data += encoder.encode_bytes(self.region.encode('utf-8'))
        data += encoder.encode_bytes_fixed(self.mat_id, 16)
        data += encoder.encode_uint64(self.issued_at)
        data += encoder.encode_bytes_fixed(self.signature, 32)

        return data

    @staticmethod
    def unpack(data: bytes) -> 'MATToken':
        """反序列化"""
        decoder = TLVDecoder(data)

        # 签发者集合
        num_issuers = decoder.decode_uint16()
        issuer_set = [decoder.decode_bytes_fixed(6) for _ in range(num_issuers)]

        # 其他字段
        device_pseudonym = decoder.decode_bytes_fixed(12)
        epoch = decoder.decode_uint32()
        ttl = decoder.decode_uint32()
        region = decoder.decode_bytes().decode('utf-8')
        mat_id = decoder.decode_bytes_fixed(16)
        issued_at = decoder.decode_uint64()
        signature = decoder.decode_bytes_fixed(32)

        return MATToken(
            issuer_set=issuer_set,
            device_pseudonym=device_pseudonym,
            epoch=epoch,
            ttl=ttl,
            region=region,
            mat_id=mat_id,
            issued_at=issued_at,
            signature=signature
        )

    def compute_signature_data(self) -> bytes:
        """
        计算用于签名的数据

        Returns:
            待签名的数据
        """
        encoder = TLVEncoder()

        # 签发者集合
        data = b''.join(self.issuer_set)

        # 其他关键字段
        data += self.device_pseudonym
        data += self.epoch.to_bytes(4, 'big')
        data += self.mat_id

        return data

    def sign_with_keys(self, signing_keys: List[bytes]):
        """
        使用多个密钥签名（聚合签名）

        Args:
            signing_keys: 签名密钥列表
        """
        sig_data = self.compute_signature_data()

        # 生成各个签名
        individual_sigs = []
        for key in signing_keys:
            sig = compute_hmac_tag(key, sig_data)
            individual_sigs.append(sig)

        # 聚合
        self.signature = AggregateSignature.aggregate(individual_sigs)

    def verify_with_keys(self, verification_keys: List[bytes]) -> bool:
        """
        验证聚合签名

        Args:
            verification_keys: 验证密钥列表

        Returns:
            验证是否通过
        """
        sig_data = self.compute_signature_data()
        return AggregateSignature.verify_aggregate(
            sig_data, self.signature, verification_keys
        )

    def __repr__(self) -> str:
        return (
            f"MATToken(id={self.mat_id.hex()}, "
            f"pseudonym={self.device_pseudonym.hex()}, "
            f"epoch={self.epoch}, "
            f"issued_at={self.issued_at})"
        )
