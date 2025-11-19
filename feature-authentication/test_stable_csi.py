"""创建稳定的CSI特征用于测试"""
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'feature-encryption'))

from src.quantizer import FeatureQuantizer
from src.config import FeatureEncryptionConfig

def create_stable_csi_v1(seed=100, M=6, D=256):
    """
    创建稳定的CSI特征:
    - 每个维度生成一个基准值
    - 所有帧在该维度使用相同的基准值 + 很小的噪声
    - 确保量化结果一致
    """
    np.random.seed(seed)

    # 为每个维度生成基准值，范围 [-3, 3]
    base_values = np.random.randn(D) * 2

    frames = np.zeros((M, D))
    for m in range(M):
        # 添加极小的噪声，保证量化一致性
        frames[m] = base_values + np.random.randn(D) * 0.001

    return frames

def create_stable_csi_v2(seed=100, M=6, D=256):
    """
    创建稳定的CSI特征（方法2）:
    - 使用两个聚类中心（高/低）
    - 每个维度选择一个中心
    - 所有帧都接近该中心
    """
    np.random.seed(seed)

    frames = np.zeros((M, D))

    for d in range(D):
        # 随机选择高值或低值中心
        if np.random.rand() > 0.5:
            center = 2.0  # 高值中心
        else:
            center = -2.0  # 低值中心

        # 所有帧都接近该中心
        for m in range(M):
            frames[m, d] = center + np.random.randn() * 0.001

    return frames

config = FeatureEncryptionConfig()
quantizer = FeatureQuantizer(config)

print("=" * 80)
print("STABLE CSI FEATURE TESTING")
print(f"Target: {config.TARGET_BITS} bits")
print("=" * 80)

for name, generator in [("V1-Same-Value", create_stable_csi_v1),
                         ("V2-Two-Centers", create_stable_csi_v2)]:
    print(f"\n{name}:")
    print("-" * 80)

    Z_frames = generator(seed=100, M=6, D=256)

    theta_L, theta_H = quantizer.compute_thresholds(Z_frames)
    Q_frames = quantizer.quantize_frames(Z_frames, theta_L, theta_H)

    # 检查每个维度的量化值一致性
    dims_with_erasure = 0
    dims_consistent = 0

    for d in range(Q_frames.shape[1]):
        q_vals = Q_frames[:, d]
        unique_vals = np.unique(q_vals)

        if -1 in unique_vals:
            dims_with_erasure += 1
        elif len(unique_vals) == 1:
            dims_consistent += 1

    print(f"  Dimensions with erasure (-1): {dims_with_erasure}/{Q_frames.shape[1]}")
    print(f"  Dimensions with consistent values: {dims_consistent}/{Q_frames.shape[1]}")

    r_bits, selected_dims = quantizer.majority_vote(Q_frames)
    padding_needed = max(0, config.TARGET_BITS - len(r_bits))

    print(f"  Majority vote: {len(r_bits)} bits from {len(selected_dims)} dimensions")
    print(f"  Random padding needed: {padding_needed} bits")

    if len(r_bits) >= config.TARGET_BITS:
        print(f"  ✓✓✓ SUCCESS! No random padding needed!")
    elif padding_needed <= 50:
        print(f"  ✓ Acceptable (minimal padding)")
    else:
        print(f"  ✗ Too much padding required")

print("\n" + "=" * 80)
