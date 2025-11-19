"""
量化与投票模块

实现多帧特征的稳健量化和多数投票机制。
"""

import numpy as np
from typing import List, Tuple, Optional
import secrets

from .config import FeatureEncryptionConfig


class FeatureQuantizer:
    """特征量化器"""

    def __init__(self, config: FeatureEncryptionConfig):
        """
        初始化量化器

        Args:
            config: 算法配置
        """
        self.config = config

    def compute_thresholds(
        self,
        Z_frames: np.ndarray,
        method: str = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        计算量化门限

        Args:
            Z_frames: 多帧特征，shape (M, D)
            method: 门限计算方法，'percentile' or 'fixed'，默认使用配置

        Returns:
            theta_L: 下门限，shape (D,)
            theta_H: 上门限，shape (D,)
        """
        if method is None:
            method = self.config.QUANTIZE_METHOD

        M, D = Z_frames.shape

        if method == 'percentile':
            # 基于分位数的门限
            theta_L = np.percentile(
                Z_frames,
                self.config.THETA_L_PERCENTILE * 100,
                axis=0
            )  # shape: (D,)
            theta_H = np.percentile(
                Z_frames,
                self.config.THETA_H_PERCENTILE * 100,
                axis=0
            )

        elif method == 'fixed':
            # 基于均值±标准差的固定倍数
            mean = np.mean(Z_frames, axis=0)  # shape: (D,)
            std = np.std(Z_frames, axis=0)

            theta_L = mean - 0.5 * std
            theta_H = mean + 0.5 * std

        else:
            raise ValueError(f"Unknown method: {method}")

        return theta_L, theta_H

    def quantize_frame(
        self,
        Z: np.ndarray,
        theta_L: np.ndarray,
        theta_H: np.ndarray
    ) -> np.ndarray:
        """
        将单帧特征量化为三值{0, 1, -1}

        Args:
            Z: 特征向量，shape (D,)
            theta_L: 下门限，shape (D,)
            theta_H: 上门限，shape (D,)

        Returns:
            Q: 量化结果，shape (D,)，值为{0, 1, -1}，其中-1表示擦除
        """
        Q = np.zeros_like(Z, dtype=np.int8)

        # 高于上门限 → 1
        Q[Z > theta_H] = 1

        # 低于下门限 → 0
        Q[Z < theta_L] = 0

        # 介于两者之间 → -1（擦除）
        Q[(Z >= theta_L) & (Z <= theta_H)] = -1

        return Q

    def quantize_frames(
        self,
        Z_frames: np.ndarray,
        theta_L: np.ndarray,
        theta_H: np.ndarray
    ) -> np.ndarray:
        """
        量化多帧特征

        Args:
            Z_frames: 多帧特征，shape (M, D)
            theta_L: 下门限，shape (D,)
            theta_H: 上门限，shape (D,)

        Returns:
            Q_frames: 量化结果，shape (M, D)
        """
        M, D = Z_frames.shape
        Q_frames = np.zeros((M, D), dtype=np.int8)

        for m in range(M):
            Q_frames[m] = self.quantize_frame(Z_frames[m], theta_L, theta_H)

        return Q_frames

    def majority_vote(
        self,
        Q_frames: np.ndarray,
        vote_threshold: int = None
    ) -> Tuple[List[int], List[int]]:
        """
        多数投票得到稳定比特串

        Args:
            Q_frames: 量化后的多帧特征，shape (M, D)
            vote_threshold: 投票通过阈值，默认使用配置

        Returns:
            r_bits: 投票得到的比特列表
            selected_dims: 选中的维度列表
        """
        if vote_threshold is None:
            vote_threshold = self.config.VOTE_THRESHOLD

        M, D = Q_frames.shape
        r_bits = []
        selected_dims = []

        for d in range(D):
            votes_d = Q_frames[:, d]  # shape: (M,)

            # 统计0和1的票数（忽略-1）
            count_0 = np.sum(votes_d == 0)
            count_1 = np.sum(votes_d == 1)

            # 投票决策
            if count_1 >= vote_threshold:
                r_bits.append(1)
                selected_dims.append(d)
            elif count_0 >= vote_threshold:
                r_bits.append(0)
                selected_dims.append(d)
            # else: 票数不足，丢弃该维度

        return r_bits, selected_dims

    def pad_bits_to_target(
        self,
        r_bits: List[int],
        selected_dims: List[int],
        Z_frames: np.ndarray,
        Q_frames: np.ndarray,
        target_bits: int = None
    ) -> List[int]:
        """
        将比特串补齐到目标长度

        Args:
            r_bits: 当前比特列表
            selected_dims: 已选中的维度
            Z_frames: 原始特征帧，shape (M, D)
            Q_frames: 量化特征帧，shape (M, D)
            target_bits: 目标比特数，默认使用配置

        Returns:
            r: 补齐后的比特列表
        """
        if target_bits is None:
            target_bits = self.config.TARGET_BITS

        r = r_bits.copy()
        used_dims = set(selected_dims)
        M, D = Z_frames.shape

        # 如果已经足够，直接截断
        if len(r) >= target_bits:
            return r[:target_bits]

        # 需要补充的比特数
        needed = target_bits - len(r)

        # 策略1：从未使用的维度中，选择SNR最高的
        unused_dims = [d for d in range(D) if d not in used_dims]

        if unused_dims:
            # 计算每个维度的"稳定性"（方差的倒数作为SNR的代理）
            stability = np.zeros(len(unused_dims))
            for i, d in enumerate(unused_dims):
                # 使用标准差的倒数作为稳定性指标
                std = np.std(Z_frames[:, d])
                stability[i] = 1.0 / (std + 1e-8)

            # 按稳定性排序
            sorted_indices = np.argsort(stability)[::-1]

            # 依次添加维度
            for idx in sorted_indices[:needed]:
                d = unused_dims[idx]
                # 简单多数投票
                votes = Q_frames[:, d]
                count_0 = np.sum(votes == 0)
                count_1 = np.sum(votes == 1)

                bit = 1 if count_1 >= count_0 else 0
                r.append(bit)
                used_dims.add(d)

                if len(r) >= target_bits:
                    break

        # 策略2：如果还不够，使用安全随机数填充
        if len(r) < target_bits:
            random_bits = self._generate_secure_random_bits(target_bits - len(r))
            r.extend(random_bits)

        return r[:target_bits]

    @staticmethod
    def _generate_secure_random_bits(n: int) -> List[int]:
        """
        生成安全的随机比特

        Args:
            n: 需要的比特数

        Returns:
            List[int]: 随机比特列表
        """
        # 使用secrets模块生成密码学安全的随机数
        random_bytes = secrets.token_bytes((n + 7) // 8)
        bits = []
        for byte in random_bytes:
            for i in range(8):
                if len(bits) >= n:
                    break
                bits.append((byte >> i) & 1)
            if len(bits) >= n:
                break
        return bits[:n]

    def process_multi_frames(
        self,
        Z_frames: np.ndarray
    ) -> Tuple[List[int], np.ndarray, np.ndarray]:
        """
        处理多帧特征，得到稳定比特串

        Args:
            Z_frames: 多帧特征，shape (M, D)

        Returns:
            r: 比特串
            theta_L: 下门限
            theta_H: 上门限
        """
        # 计算门限
        theta_L, theta_H = self.compute_thresholds(Z_frames)

        # 量化
        Q_frames = self.quantize_frames(Z_frames, theta_L, theta_H)

        # 投票
        r_bits, selected_dims = self.majority_vote(Q_frames)

        # 补齐到目标长度
        r = self.pad_bits_to_target(r_bits, selected_dims, Z_frames, Q_frames)

        return r, theta_L, theta_H

    def compute_bit_stability(self, Q_frames: np.ndarray) -> np.ndarray:
        """
        计算每个维度的比特稳定性

        Args:
            Q_frames: 量化后的多帧特征，shape (M, D)

        Returns:
            stability: 每个维度的稳定性分数，shape (D,)
        """
        M, D = Q_frames.shape
        stability = np.zeros(D)

        for d in range(D):
            votes = Q_frames[:, d]

            # 去除擦除标记
            valid_votes = votes[votes != -1]

            if len(valid_votes) == 0:
                stability[d] = 0.0
                continue

            # 计算一致性：同一值的票数占比
            count_0 = np.sum(valid_votes == 0)
            count_1 = np.sum(valid_votes == 1)
            max_count = max(count_0, count_1)

            stability[d] = max_count / len(valid_votes)

        return stability


# 导出
__all__ = ['FeatureQuantizer']
