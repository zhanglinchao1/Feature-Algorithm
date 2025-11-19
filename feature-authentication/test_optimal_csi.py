"""找到最优的CSI模拟参数以产生足够的量化比特"""
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'feature-encryption'))

from src.quantizer import FeatureQuantizer
from src.config import FeatureEncryptionConfig

def simulate_csi(seed=100, noise=0.01, M=6, D=128):
    """模拟CSI特征，带有小幅噪声以产生方差"""
    np.random.seed(seed)
    base = np.random.randn(D)
    frames = np.zeros((M, D))
    for i in range(M):
        frames[i] = base + np.random.randn(D) * noise
    return frames

config = FeatureEncryptionConfig()
quantizer = FeatureQuantizer(config)

print("=" * 80)
print("OPTIMAL CSI PARAMETERS SEARCH")
print(f"Target: {config.TARGET_BITS} bits")
print("=" * 80)

# 测试不同的维度和噪声组合
test_configs = [
    # (D, noise_level)
    (64, 0.01),
    (96, 0.01),
    (128, 0.01),
    (192, 0.01),
    (256, 0.01),
    (128, 0.005),
    (128, 0.02),
    (128, 0.05),
]

for D, noise in test_configs:
    print(f"\nD={D}, noise={noise}:")
    Z_frames = simulate_csi(seed=100, noise=noise, M=6, D=D)

    # 检查方差
    variance = np.var(Z_frames, axis=0)
    non_zero_var = np.sum(variance > 0)

    theta_L, theta_H = quantizer.compute_thresholds(Z_frames)
    Q_frames = quantizer.quantize_frames(Z_frames, theta_L, theta_H)
    r_bits, selected_dims = quantizer.majority_vote(Q_frames)

    padding_needed = max(0, config.TARGET_BITS - len(r_bits))

    print(f"  Non-zero variance dims: {non_zero_var}/{D}")
    print(f"  Majority vote: {len(r_bits)} bits from {len(selected_dims)} dimensions")
    print(f"  Random padding needed: {padding_needed} bits")

    if len(r_bits) >= config.TARGET_BITS:
        print(f"  ✓✓✓ NO random padding needed! This config works!")
    elif padding_needed <= 50:
        print(f"  ✓ Minimal padding (acceptable for testing)")
    else:
        print(f"  ✗ Too much padding required")

print("\n" + "=" * 80)
