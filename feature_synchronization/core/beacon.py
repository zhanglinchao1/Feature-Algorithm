"""
同步信标模块
"""
from dataclasses import dataclass
from typing import Optional

from .feature_config import FeatureConfig
from ..utils.serialization import TLVEncoder, TLVDecoder
from ..crypto.signatures import SimpleHMAC


@dataclass
class SyncBeacon:
    """同步信标结构"""

    # 基础时间信息
    epoch: int                    # 当前时间窗编号
    timestamp: int                # 信标生成时间戳(ms)
    delta_t: int                  # 时间窗周期(ms), 默认30000

    # 簇首信息
    cluster_head_id: bytes        # 簇首节点ID (6字节MAC)
    beacon_seq: int               # 信标序号

    # 特征参数配置
    feature_config: FeatureConfig # 特征参数配置

    # 完整性保护
    signature: bytes              # 簇首签名(32字节)

    def pack(self) -> bytes:
        """
        打包为字节流

        Returns:
            序列化的字节流
        """
        encoder = TLVEncoder()

        data = encoder.encode_uint32(self.epoch)
        data += encoder.encode_uint64(self.timestamp)
        data += encoder.encode_uint32(self.delta_t)
        data += encoder.encode_bytes_fixed(self.cluster_head_id, 6)
        data += encoder.encode_uint32(self.beacon_seq)

        # 编码特征配置
        config_data = self.feature_config.pack()
        data += encoder.encode_bytes(config_data)

        # 签名放在最后
        data += encoder.encode_bytes_fixed(self.signature, 32)

        return data

    @staticmethod
    def unpack(data: bytes) -> 'SyncBeacon':
        """
        从字节流解包

        Args:
            data: 序列化的字节流

        Returns:
            SyncBeacon对象
        """
        decoder = TLVDecoder(data)

        epoch = decoder.decode_uint32()
        timestamp = decoder.decode_uint64()
        delta_t = decoder.decode_uint32()
        cluster_head_id = decoder.decode_bytes_fixed(6)
        beacon_seq = decoder.decode_uint32()

        # 解码特征配置
        config_data = decoder.decode_bytes()
        feature_config = FeatureConfig.unpack(config_data)

        # 签名
        signature = decoder.decode_bytes_fixed(32)

        return SyncBeacon(
            epoch=epoch,
            timestamp=timestamp,
            delta_t=delta_t,
            cluster_head_id=cluster_head_id,
            beacon_seq=beacon_seq,
            feature_config=feature_config,
            signature=signature
        )

    def compute_signature_data(self) -> bytes:
        """
        计算用于签名的数据

        Returns:
            待签名的数据
        """
        encoder = TLVEncoder()

        data = encoder.encode_uint32(self.epoch)
        data += encoder.encode_uint64(self.timestamp)
        data += encoder.encode_uint32(self.delta_t)
        data += encoder.encode_bytes_fixed(self.cluster_head_id, 6)
        data += encoder.encode_uint32(self.beacon_seq)
        data += encoder.encode_bytes(self.feature_config.pack())

        return data

    def sign(self, signing_key: bytes):
        """
        对信标签名

        Args:
            signing_key: 签名密钥
        """
        signer = SimpleHMAC(signing_key)
        sig_data = self.compute_signature_data()
        self.signature = signer.sign(sig_data)

    def verify(self, verification_key: bytes) -> bool:
        """
        验证信标签名

        Args:
            verification_key: 验证密钥

        Returns:
            验证是否通过
        """
        verifier = SimpleHMAC(verification_key)
        sig_data = self.compute_signature_data()
        return verifier.verify(sig_data, self.signature)

    def __repr__(self) -> str:
        return (
            f"SyncBeacon(epoch={self.epoch}, "
            f"seq={self.beacon_seq}, "
            f"cluster_head={self.cluster_head_id.hex()}, "
            f"timestamp={self.timestamp})"
        )
