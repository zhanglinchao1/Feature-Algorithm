"""
密钥材料模块
"""
import hmac
import hashlib
from dataclasses import dataclass
from typing import Optional

from ..utils.serialization import TLVEncoder, TLVDecoder
from ..crypto.hkdf import truncate


@dataclass
class KeyMaterial:
    """与epoch绑定的密钥材料"""

    epoch: int                    # 绑定的时间窗

    # 由3.3.1生成的密钥（接口调用）
    feature_key: bytes            # 特征密钥K (32字节)
    session_key: bytes            # 会话密钥Ks (32字节)

    # 派生的标识
    pseudonym: bytes              # 伪名 (12字节)

    # 哈希链状态
    hash_chain_counter: int       # 计数器Ci

    # 有效期
    valid_from: int               # 生效时间戳(ms)
    valid_until: int              # 失效时间戳(ms)

    def is_valid(self, now: int) -> bool:
        """
        检查是否在有效期内

        Args:
            now: 当前时间戳(ms)

        Returns:
            是否有效
        """
        return self.valid_from <= now <= self.valid_until

    def is_epoch_match(self, epoch: int) -> bool:
        """
        检查epoch是否匹配

        Args:
            epoch: 时间窗编号

        Returns:
            是否匹配
        """
        return self.epoch == epoch

    @staticmethod
    def derive_pseudonym(feature_key: bytes, epoch: int, counter: int) -> bytes:
        """
        派生伪名

        DevPseudo = Trunc96(HMAC(K, "psn" || epoch || Ci))

        Args:
            feature_key: 特征密钥K
            epoch: 时间窗编号
            counter: 哈希链计数器Ci

        Returns:
            伪名 (12字节)
        """
        # 构造输入: "psn" || epoch || Ci
        data = b"psn"
        data += epoch.to_bytes(4, 'big')
        data += counter.to_bytes(4, 'big')

        # 计算HMAC
        tag = hmac.new(feature_key, data, hashlib.sha256).digest()

        # 截断到96位(12字节)
        return truncate(tag, 12)

    def pack(self) -> bytes:
        """序列化"""
        encoder = TLVEncoder()

        data = encoder.encode_uint32(self.epoch)
        data += encoder.encode_bytes_fixed(self.feature_key, 32)
        data += encoder.encode_bytes_fixed(self.session_key, 32)
        data += encoder.encode_bytes_fixed(self.pseudonym, 12)
        data += encoder.encode_uint32(self.hash_chain_counter)
        data += encoder.encode_uint64(self.valid_from)
        data += encoder.encode_uint64(self.valid_until)

        return data

    @staticmethod
    def unpack(data: bytes) -> 'KeyMaterial':
        """反序列化"""
        decoder = TLVDecoder(data)

        epoch = decoder.decode_uint32()
        feature_key = decoder.decode_bytes_fixed(32)
        session_key = decoder.decode_bytes_fixed(32)
        pseudonym = decoder.decode_bytes_fixed(12)
        hash_chain_counter = decoder.decode_uint32()
        valid_from = decoder.decode_uint64()
        valid_until = decoder.decode_uint64()

        return KeyMaterial(
            epoch=epoch,
            feature_key=feature_key,
            session_key=session_key,
            pseudonym=pseudonym,
            hash_chain_counter=hash_chain_counter,
            valid_from=valid_from,
            valid_until=valid_until
        )

    def __repr__(self) -> str:
        return (
            f"KeyMaterial(epoch={self.epoch}, "
            f"pseudonym={self.pseudonym.hex()}, "
            f"valid={self.valid_from}-{self.valid_until})"
        )
