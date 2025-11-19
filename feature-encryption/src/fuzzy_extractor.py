"""
模糊提取器模块

使用BCH纠错码实现码偏移式模糊提取器。
"""

import numpy as np
from typing import List, Tuple
import importlib
import sys

from .config import FeatureEncryptionConfig


class FuzzyExtractor:
    """模糊提取器（基于BCH码）"""

    def __init__(self, config: FeatureEncryptionConfig):
        """
        初始化模糊提取器

        Args:
            config: 算法配置
        """
        self.config = config

        # 延迟导入bchlib，避免模块级别的编码问题
        try:
            # 尝试使用importlib动态导入，处理可能的编码问题
            if 'bchlib' not in sys.modules:
                importlib.import_module('bchlib')
            import bchlib
        except (ImportError, UnicodeDecodeError, Exception) as e:
            raise ImportError(
                f"bchlib is not installed or has encoding issues. "
                f"Please reinstall it: pip uninstall bchlib && pip install bchlib. "
                f"Error: {e}"
            )

        # 初始化BCH编解码器
        self.bch = bchlib.BCH(
            self.config.BCH_T,  # 纠错能力
            prim_poly=self.config.BCH_POLY  # 生成多项式
        )

        # BCH参数
        self.n = self.config.BCH_N  # 码字长度
        self.k = self.config.BCH_K  # 消息长度
        self.t = self.config.BCH_T  # 纠错能力

    def generate_helper_data(self, r: List[int]) -> bytes:
        """
        生成辅助数据（注册阶段）

        Args:
            r: 比特串，长度为TARGET_BITS

        Returns:
            P: 辅助数据（helper data）
        """
        target_bits = self.config.TARGET_BITS
        blocks = self.config.BCH_BLOCKS

        # 验证输入长度
        if len(r) != target_bits:
            raise ValueError(
                f"Expected r length {target_bits}, got {len(r)}"
            )

        # 计算每块的大小
        block_size = target_bits // blocks

        P_blocks = []

        for j in range(blocks):
            # 提取该块的比特
            start = j * block_size
            end = min((j + 1) * block_size, target_bits)
            r_block = r[start:end]

            # 补齐到k位（如果需要）
            if len(r_block) < self.k:
                r_block = r_block + [0] * (self.k - len(r_block))
            else:
                r_block = r_block[:self.k]

            # 转换为字节
            msg_bytes = self._bits_to_bytes(r_block)

            # BCH编码
            ecc_bytes = self.bch.encode(msg_bytes)

            # 码字 = 消息 + ECC
            codeword_bytes = msg_bytes + ecc_bytes

            # 转换为比特
            codeword_bits = self._bytes_to_bits(codeword_bytes, self.n)

            # 计算辅助串：helper = codeword XOR r_padded
            r_padded = r_block + [0] * (self.n - len(r_block))
            helper_bits = [c ^ r_b for c, r_b in zip(codeword_bits, r_padded)]

            # 转换为字节
            helper_bytes = self._bits_to_bytes(helper_bits)

            P_blocks.append(helper_bytes)

        # 拼接所有块
        P = b''.join(P_blocks)

        return P

    def extract_stable_key(
        self,
        r_prime: List[int],
        P: bytes
    ) -> Tuple[List[int], bool]:
        """
        提取稳定密钥（认证阶段）

        Args:
            r_prime: 含噪比特串
            P: 辅助数据

        Returns:
            S: 稳定特征串
            success: 是否成功解码
        """
        target_bits = self.config.TARGET_BITS
        blocks = self.config.BCH_BLOCKS
        block_size = target_bits // blocks

        # 验证输入长度
        if len(r_prime) != target_bits:
            raise ValueError(
                f"Expected r_prime length {target_bits}, got {len(r_prime)}"
            )

        S_blocks = []
        success = True

        # 计算每块的辅助数据大小
        helper_byte_size = (self.n + 7) // 8

        for j in range(blocks):
            # 提取该块的r'
            start = j * block_size
            end = min((j + 1) * block_size, target_bits)
            r_prime_block = r_prime[start:end]

            # 补齐到n位
            r_prime_padded = r_prime_block + [0] * (self.n - len(r_prime_block))

            # 提取该块的辅助数据
            helper_start = j * helper_byte_size
            helper_end = (j + 1) * helper_byte_size
            helper_bytes = P[helper_start:helper_end]

            # 转换为比特
            helper_bits = self._bytes_to_bits(helper_bytes, self.n)

            # 恢复码字：codeword = helper XOR r_padded
            noisy_codeword_bits = [h ^ r for h, r in zip(helper_bits, r_prime_padded)]

            # 转换为字节 - 注意这里转换的是n位（255位），会补齐到256位（32字节）
            noisy_codeword_bytes = self._bits_to_bytes(noisy_codeword_bits)

            # 分离消息和ECC - 使用bch.ecc_bytes确定ECC长度
            msg_byte_size = (self.k + 7) // 8  # 消息字节数
            ecc_byte_size = self.bch.ecc_bytes  # ECC字节数（从BCH库获取）
            
            # 确保我们有足够的字节
            total_needed = msg_byte_size + ecc_byte_size
            if len(noisy_codeword_bytes) < total_needed:
                # 补齐（不应该发生，但防御性编程）
                noisy_codeword_bytes += b'\x00' * (total_needed - len(noisy_codeword_bytes))
            
            noisy_msg = noisy_codeword_bytes[:msg_byte_size]
            ecc_bytes = noisy_codeword_bytes[msg_byte_size:msg_byte_size + ecc_byte_size]

            # BCH解码
            try:
                bit_flips = self.bch.decode(noisy_msg, ecc_bytes)
                if bit_flips < 0:
                    # 解码失败
                    success = False
                    # 仍然返回未纠错的消息
                    corrected_msg = noisy_msg
                else:
                    # 解码成功，应用纠错
                    corrected_msg = bytearray(noisy_msg)
                    self.bch.correct(corrected_msg, ecc_bytes)
                    corrected_msg = bytes(corrected_msg)
            except Exception as e:
                # BCH解码异常
                success = False
                corrected_msg = noisy_msg

            # 转换为比特
            corrected_bits = self._bytes_to_bits(corrected_msg, self.k)

            # 取前block_size位
            S_blocks.append(corrected_bits[:block_size])

        # 拼接所有块
        S = []
        for block in S_blocks:
            S.extend(block)

        # 截断到target_bits
        S = S[:target_bits]

        return S, success

    @staticmethod
    def _bits_to_bytes(bits: List[int]) -> bytes:
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

    @staticmethod
    def _bytes_to_bits(data: bytes, length: int = None) -> List[int]:
        """
        将字节串转换为比特列表

        Args:
            data: 字节串
            length: 输出长度，默认为8*len(data)

        Returns:
            List[int]: 比特列表
        """
        bits = []
        for byte in data:
            for i in range(8):
                bits.append((byte >> i) & 1)

        if length is not None:
            bits = bits[:length]

        return bits

    def test_error_correction(
        self,
        r: List[int],
        num_errors: int
    ) -> Tuple[List[int], bool, int]:
        """
        测试纠错能力

        Args:
            r: 原始比特串
            num_errors: 人为引入的错误数

        Returns:
            S: 恢复的比特串
            success: 是否成功
            actual_errors: 实际纠正的错误数
        """
        # 生成辅助数据
        P = self.generate_helper_data(r)

        # 人为引入错误
        r_prime = r.copy()
        error_positions = np.random.choice(
            len(r),
            size=min(num_errors, len(r)),
            replace=False
        )
        for pos in error_positions:
            r_prime[pos] = 1 - r_prime[pos]  # 翻转比特

        # 提取稳定密钥
        S, success = self.extract_stable_key(r_prime, P)

        # 计算实际纠正的错误数
        actual_errors = sum([1 for i in range(len(r)) if r[i] != r_prime[i]])

        return S, success, actual_errors


# 导出
__all__ = ['FuzzyExtractor']
