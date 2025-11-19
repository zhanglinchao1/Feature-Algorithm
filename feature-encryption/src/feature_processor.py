"""
特征处理模块

实现CSI和RFF特征的提取、预处理和规整。
"""

import numpy as np
from typing import Tuple, List, Dict, Any
import json

from .config import FeatureEncryptionConfig


class FeatureProcessor:
    """特征处理器"""

    def __init__(self, config: FeatureEncryptionConfig):
        """
        初始化特征处理器

        Args:
            config: 算法配置
        """
        self.config = config

    def process_csi(
        self,
        H: np.ndarray,
        noise_variance: float
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        处理CSI特征

        Args:
            H: 信道估计，shape (N_subcarrier,)，复数数组
            noise_variance: 噪声功率

        Returns:
            Z: 实值特征向量，shape (D,)
            mask: 特征掩码信息
        """
        N_total = self.config.N_SUBCARRIER_TOTAL
        N_select = self.config.N_SUBCARRIER_SELECTED

        # 验证输入
        if H.shape[0] != N_total:
            raise ValueError(
                f"Expected H shape ({N_total},), got {H.shape}"
            )

        # Step 1: 计算SNR并选择子载波
        snr = np.abs(H) ** 2 / (noise_variance + 1e-10)
        indices = np.argsort(snr)[::-1][:N_select]  # SNR最高的N_select个
        indices_sorted = np.sort(indices)  # 保持频域顺序

        # Step 2: 提取选中的子载波
        H_selected = H[indices_sorted]

        # Step 3: 计算幅度差分特征 (N_select - 1维)
        amp = np.abs(H_selected)
        amp_diff = amp[1:] - amp[:-1]  # shape: (N_select-1,)

        # Step 4: 计算相位差分特征 (N_select - 1维)
        phase = np.angle(H_selected)
        phase_diff = phase[1:] - phase[:-1]
        # 相位展开到[-π, π]
        phase_diff = np.mod(phase_diff + np.pi, 2 * np.pi) - np.pi

        # Step 5: 拼接特征向量
        Z = np.concatenate([amp_diff, phase_diff])  # shape: (2*(N_select-1),)

        # Step 6: 如果需要扩展到目标维度，补充统计特征
        target_dim = self.config.get_feature_dim('CSI')
        if Z.shape[0] < target_dim:
            # 补充统计特征：均值和标准差
            mean_amp = np.mean(amp)
            std_amp = np.std(amp)
            Z = np.concatenate([Z, [mean_amp, std_amp]])

        # 截断到目标维度
        Z = Z[:target_dim]

        # 生成掩码
        mask = {
            'mode': 'CSI',
            'indices': indices_sorted.tolist(),
            'N_selected': N_select,
            'noise_variance': float(noise_variance)
        }

        return Z, mask

    def process_rff(
        self,
        raw_features: np.ndarray,
        history_stats: Dict[str, np.ndarray] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        处理RFF特征

        Args:
            raw_features: 原始射频特征，shape (D_rff,)
            history_stats: 历史统计信息，包含'mean'和'std'

        Returns:
            Z: 标准化特征向量，shape (D_rff,)
            mask: 特征掩码信息
        """
        D_rff = self.config.FEATURE_DIM_RFF

        # 验证输入
        if raw_features.shape[0] != D_rff:
            raise ValueError(
                f"Expected raw_features shape ({D_rff},), got {raw_features.shape}"
            )

        # Z-score标准化
        if history_stats is not None:
            mean = history_stats.get('mean', np.zeros(D_rff))
            std = history_stats.get('std', np.ones(D_rff))
        else:
            # 如果没有历史统计，使用当前数据的统计（仅用于测试）
            mean = raw_features
            std = np.ones(D_rff)

        epsilon = 1e-8  # 防止除零
        Z = (raw_features - mean) / (std + epsilon)

        # 生成掩码
        mask = {
            'mode': 'RFF',
            'feature_ids': list(range(D_rff)),
            'mean': mean.tolist(),
            'std': std.tolist()
        }

        return Z, mask

    def process_feature(
        self,
        data: np.ndarray,
        mode: str,
        **kwargs
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        统一的特征处理接口

        Args:
            data: 原始数据
            mode: 'CSI' or 'RFF'
            **kwargs: 额外参数

        Returns:
            Z: 特征向量
            mask: 特征掩码
        """
        mode = mode.upper()

        if mode == 'CSI':
            noise_variance = kwargs.get('noise_variance', 0.01)
            return self.process_csi(data, noise_variance)
        elif mode == 'RFF':
            history_stats = kwargs.get('history_stats', None)
            return self.process_rff(data, history_stats)
        else:
            raise ValueError(f"Unknown mode: {mode}, expected 'CSI' or 'RFF'")

    @staticmethod
    def serialize_mask(mask: Dict[str, Any]) -> bytes:
        """
        序列化特征掩码

        Args:
            mask: 特征掩码字典

        Returns:
            bytes: 序列化后的字节串
        """
        json_str = json.dumps(mask, sort_keys=True)
        return json_str.encode('utf-8')

    @staticmethod
    def deserialize_mask(mask_bytes: bytes) -> Dict[str, Any]:
        """
        反序列化特征掩码

        Args:
            mask_bytes: 序列化的字节串

        Returns:
            Dict: 特征掩码字典
        """
        json_str = mask_bytes.decode('utf-8')
        return json.loads(json_str)

    def select_high_snr_subcarriers(
        self,
        H: np.ndarray,
        noise_variance: float,
        n_select: int = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        选择高SNR子载波

        Args:
            H: 信道估计
            noise_variance: 噪声功率
            n_select: 选择数量，默认使用配置中的值

        Returns:
            indices: 选中的子载波索引，已排序
            snr: 对应的SNR值
        """
        if n_select is None:
            n_select = self.config.N_SUBCARRIER_SELECTED

        # 计算SNR
        snr = np.abs(H) ** 2 / (noise_variance + 1e-10)

        # 选择SNR最高的n_select个
        indices = np.argsort(snr)[::-1][:n_select]

        # 保持频域顺序
        indices_sorted = np.sort(indices)
        snr_selected = snr[indices_sorted]

        return indices_sorted, snr_selected

    def compute_csi_features(
        self,
        H_selected: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        计算CSI的幅度和相位差分特征

        Args:
            H_selected: 选中的子载波信道估计

        Returns:
            amp_diff: 幅度差分特征
            phase_diff: 相位差分特征
        """
        # 幅度差分
        amp = np.abs(H_selected)
        amp_diff = amp[1:] - amp[:-1]

        # 相位差分（展开到[-π, π]）
        phase = np.angle(H_selected)
        phase_diff = phase[1:] - phase[:-1]
        phase_diff = np.mod(phase_diff + np.pi, 2 * np.pi) - np.pi

        return amp_diff, phase_diff


# 导出
__all__ = ['FeatureProcessor']
