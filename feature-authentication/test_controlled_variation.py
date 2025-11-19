"""测试有控制变化的CSI特征"""
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'feature-encryption'))

from src.quantizer import FeatureQuantizer
from src.config import FeatureEncryptionConfig

def create_controlled_csi(seed=100, M=6, D=256):
    """
    创建有控制变化的CSI特征:
    - 每个维度随机选择高值(+2)或低值(-2)作为主值
    - M-1 帧使用主值
    - 1帧使用主值的相反方向（创建variation但保持majority）
    """
    np.random.seed(seed)

    frames = np.zeros((M, D))

    for d in range(D):
        # 随机选择这个维度的主值（高或低）
        if np.random.rand() > 0.5:
            main_value = 2.0  # High
            outlier_value = -2.0  # Low outlier
        else:
            main_value = -2.0  # Low
            outlier_value = 2.0  # High outlier

        # M-1 frames use main value, 1 frame uses outlier
        for m in range(M):
            if m == 0:  # First frame is outlier
                frames[m, d] = outlier_value
            else:  # Rest use main value
                frames[m, d] = main_value

    return frames

def create_majority_csi(seed=100, M=6, D=256):
    """
    创建majority-based CSI:
    - 每个维度M个值中，5个相同（majority），1个不同
    - 确保majority vote能选出主要值
    """
    np.random.seed(seed)
    frames = np.zeros((M, D))

    for d in range(D):
        # 为每个维度生成基准值
        base = np.random.randn() * 2

        # 5帧接近base（会量化为同一值）
        # 1帧远离base（会量化为不同值）
        for m in range(M):
            if m < M - 1:  # M-1 frames near base
                frames[m, d] = base
            else:  # 1 frame far from base
                frames[m, d] = base + 4.0 * np.sign(base)  # Move far away

    return frames

config = FeatureEncryptionConfig()
quantizer = FeatureQuantizer(config)

print("=" * 80)
print("CONTROLLED VARIATION CSI TESTING")
print(f"Target: {config.TARGET_BITS} bits")
print("=" * 80)

for name, generator in [
    ("Controlled-Bimodal", create_controlled_csi),
    ("Majority-5-of-6", create_majority_csi)
]:
    print(f"\n{name}:")
    print("-" * 80)

    Z_frames = generator(seed=100, M=6, D=256)

    # 检查第一个维度的值
    print(f"  Dim 0 values across frames: {Z_frames[:, 0]}")

    theta_L, theta_H = quantizer.compute_thresholds(Z_frames)
    print(f"  Dim 0: theta_L={theta_L[0]:.4f}, theta_H={theta_H[0]:.4f}")

    Q_frames = quantizer.quantize_frames(Z_frames, theta_L, theta_H)

    print(f"  Dim 0 quantized: {Q_frames[:, 0]}")

    # 统计
    unique_vals = np.unique(Q_frames)
    print(f"\n  Q_frames unique values: {unique_vals}")
    for val in unique_vals:
        count = np.sum(Q_frames == val)
        print(f"    Count of {val}: {count} ({count/Q_frames.size*100:.1f}%)")

    # Majority vote
    r_bits, selected_dims = quantizer.majority_vote(Q_frames)

    padding_needed = max(0, config.TARGET_BITS - len(r_bits))
    print(f"\n  Majority vote: {len(r_bits)} bits from {len(selected_dims)} dimensions")
    print(f"  Random padding needed: {padding_needed} bits")

    if len(r_bits) >= config.TARGET_BITS:
        print(f"  ✓✓✓ SUCCESS! No random padding needed!")
    elif padding_needed <= 50:
        print(f"  ✓ Acceptable (minimal padding)")
    else:
        print(f"  ✗ Too much padding required")

print("\n" + "=" * 80)
