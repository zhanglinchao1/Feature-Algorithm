"""测试完全相同的CSI特征（无噪声）"""
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'feature-encryption'))

from src.quantizer import FeatureQuantizer
from src.config import FeatureEncryptionConfig

def create_identical_csi(seed=100, M=6, D=256):
    """
    创建完全相同的CSI特征:
    - 每个维度所有帧都是完全相同的值
    - NO noise at all
    """
    np.random.seed(seed)

    # 生成一个基准向量
    base_vector = np.random.randn(D) * 2  # Range: roughly [-6, 6]

    # 所有帧都使用相同的向量
    frames = np.tile(base_vector, (M, 1))

    return frames

config = FeatureEncryptionConfig()
quantizer = FeatureQuantizer(config)

print("=" * 80)
print("IDENTICAL CSI FEATURE TESTING (Zero Noise)")
print(f"Target: {config.TARGET_BITS} bits")
print("=" * 80)

Z_frames = create_identical_csi(seed=100, M=6, D=256)

print(f"\nZ_frames shape: {Z_frames.shape}")

# 验证所有帧确实相同
for d in range(5):  # Check first 5 dimensions
    values = Z_frames[:, d]
    print(f"  Dim {d} values across frames: {values[:3]}... (all same: {np.allclose(values, values[0])})")

print(f"\nComputing thresholds...")
theta_L, theta_H = quantizer.compute_thresholds(Z_frames)

# 检查阈值
print(f"\nThreshold analysis (first 5 dims):")
for d in range(5):
    z_val = Z_frames[0, d]  # All frames have same value
    print(f"  Dim {d}: Z={z_val:.4f}, theta_L={theta_L[d]:.4f}, theta_H={theta_H[d]:.4f}")
    print(f"    theta_L == theta_H? {theta_L[d] == theta_H[d]}")
    print(f"    Z == theta_L? {z_val == theta_L[d]}")

print(f"\nQuantizing...")
Q_frames = quantizer.quantize_frames(Z_frames, theta_L, theta_H)

print(f"\nQ_frames statistics:")
unique_vals = np.unique(Q_frames)
print(f"  Unique values: {unique_vals}")
for val in unique_vals:
    count = np.sum(Q_frames == val)
    print(f"  Count of {val}: {count} ({count/Q_frames.size*100:.1f}%)")

# 检查几个维度
print(f"\nDimension analysis (first 5):")
for d in range(5):
    q_vals = Q_frames[:, d]
    print(f"  Dim {d}: {q_vals} (unique: {np.unique(q_vals)})")

print(f"\nMajority vote...")
r_bits, selected_dims = quantizer.majority_vote(Q_frames)

print(f"\nResults:")
print(f"  Majority vote: {len(r_bits)} bits from {len(selected_dims)} dimensions")
padding_needed = max(0, config.TARGET_BITS - len(r_bits))
print(f"  Random padding needed: {padding_needed} bits")

if len(r_bits) >= config.TARGET_BITS:
    print(f"  ✓✓✓ SUCCESS!")
else:
    print(f"  ✗ FAILED")

print("\n" + "=" * 80)
