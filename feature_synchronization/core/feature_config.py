"""
特征参数配置模块
"""
import hashlib
import secrets
from dataclasses import dataclass
from typing import List
import numpy as np

from ..utils.serialization import TLVEncoder, TLVDecoder


@dataclass
class PilotPlan:
    """TDD导频时隙配置"""

    frame_duration_ms: int        # TDD帧周期(ms)
    pilot_slots: List[int]        # 导频时隙索引列表
    training_pattern: bytes       # 训练序列图案

    def get_pilot_times(self, epoch_start: int, epoch_duration: int) -> List[int]:
        """
        获取epoch内的导频时刻

        Args:
            epoch_start: epoch开始时间戳(ms)
            epoch_duration: epoch持续时间(ms)

        Returns:
            导频时刻列表(ms)
        """
        pilot_times = []
        current_time = epoch_start

        while current_time < epoch_start + epoch_duration:
            for slot in self.pilot_slots:
                pilot_time = current_time + slot
                if pilot_time < epoch_start + epoch_duration:
                    pilot_times.append(pilot_time)

            current_time += self.frame_duration_ms

        return pilot_times

    def pack(self) -> bytes:
        """序列化"""
        encoder = TLVEncoder()
        data = encoder.encode_uint32(self.frame_duration_ms)
        data += encoder.encode_uint16(len(self.pilot_slots))
        for slot in self.pilot_slots:
            data += encoder.encode_uint32(slot)
        data += encoder.encode_bytes(self.training_pattern)
        return data

    @staticmethod
    def unpack(data: bytes) -> 'PilotPlan':
        """反序列化"""
        decoder = TLVDecoder(data)
        frame_duration_ms = decoder.decode_uint32()
        num_slots = decoder.decode_uint16()
        pilot_slots = [decoder.decode_uint32() for _ in range(num_slots)]
        training_pattern = decoder.decode_bytes()

        return PilotPlan(
            frame_duration_ms=frame_duration_ms,
            pilot_slots=pilot_slots,
            training_pattern=training_pattern
        )


@dataclass
class FeatureConfig:
    """特征参数配置"""

    # 配置版本
    version: int                  # 配置版本号
    config_id: bytes              # 配置唯一标识(16字节)

    # 导频计划
    pilot_plan: PilotPlan         # TDD导频时隙配置

    # 特征采集参数
    measurement_window_ms: int    # 测量窗口时长(ms)
    sample_count: int             # 采样帧数M，默认6

    # 子载波选择
    subcarrier_seed: bytes        # 子载波选择种子(8字节)
    subcarrier_count: int         # 选择的子载波数量

    # 量化参数
    quantization_alpha: float     # 量化门限系数α, 默认0.8

    # 一致性摘要
    digest: bytes                 # SHA256(所有参数), 32字节

    def compute_digest(self) -> bytes:
        """
        计算配置摘要

        Returns:
            SHA256摘要 (32字节)
        """
        h = hashlib.sha256()

        # 按顺序加入所有参数
        h.update(self.version.to_bytes(4, 'big'))
        h.update(self.config_id)
        h.update(self.pilot_plan.pack())
        h.update(self.measurement_window_ms.to_bytes(4, 'big'))
        h.update(self.sample_count.to_bytes(4, 'big'))
        h.update(self.subcarrier_seed)
        h.update(self.subcarrier_count.to_bytes(4, 'big'))
        h.update(str(self.quantization_alpha).encode('utf-8'))

        return h.digest()

    def select_subcarriers(self, total: int) -> List[int]:
        """
        根据seed选择子载波索引

        Args:
            total: 总子载波数量

        Returns:
            选中的子载波索引列表
        """
        # 使用种子初始化随机数生成器
        rng = np.random.RandomState(
            int.from_bytes(self.subcarrier_seed, 'big') % (2**32)
        )

        # 随机选择subcarrier_count个子载波
        indices = rng.choice(total, self.subcarrier_count, replace=False)
        return sorted(indices.tolist())

    def pack(self) -> bytes:
        """序列化"""
        encoder = TLVEncoder()

        data = encoder.encode_uint32(self.version)
        data += encoder.encode_bytes_fixed(self.config_id, 16)
        data += encoder.encode_bytes(self.pilot_plan.pack())
        data += encoder.encode_uint32(self.measurement_window_ms)
        data += encoder.encode_uint32(self.sample_count)
        data += encoder.encode_bytes_fixed(self.subcarrier_seed, 8)
        data += encoder.encode_uint32(self.subcarrier_count)
        data += encoder.encode_float(self.quantization_alpha)
        data += encoder.encode_bytes_fixed(self.digest, 32)

        return data

    @staticmethod
    def unpack(data: bytes) -> 'FeatureConfig':
        """反序列化"""
        decoder = TLVDecoder(data)

        version = decoder.decode_uint32()
        config_id = decoder.decode_bytes_fixed(16)
        pilot_plan_data = decoder.decode_bytes()
        pilot_plan = PilotPlan.unpack(pilot_plan_data)
        measurement_window_ms = decoder.decode_uint32()
        sample_count = decoder.decode_uint32()
        subcarrier_seed = decoder.decode_bytes_fixed(8)
        subcarrier_count = decoder.decode_uint32()
        quantization_alpha = decoder.decode_float()
        digest = decoder.decode_bytes_fixed(32)

        return FeatureConfig(
            version=version,
            config_id=config_id,
            pilot_plan=pilot_plan,
            measurement_window_ms=measurement_window_ms,
            sample_count=sample_count,
            subcarrier_seed=subcarrier_seed,
            subcarrier_count=subcarrier_count,
            quantization_alpha=quantization_alpha,
            digest=digest
        )

    @staticmethod
    def create_default() -> 'FeatureConfig':
        """创建默认配置"""
        pilot_plan = PilotPlan(
            frame_duration_ms=10,
            pilot_slots=[0, 5],
            training_pattern=b'\x00' * 16
        )

        config = FeatureConfig(
            version=1,
            config_id=secrets.token_bytes(16),
            pilot_plan=pilot_plan,
            measurement_window_ms=200,
            sample_count=6,
            subcarrier_seed=secrets.token_bytes(8),
            subcarrier_count=64,
            quantization_alpha=0.8,
            digest=b''
        )

        # 计算摘要
        config.digest = config.compute_digest()

        return config
