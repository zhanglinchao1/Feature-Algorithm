"""测试增加帧数M"""
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'feature-encryption'))

from src.quantizer import FeatureQuantizer
from src.config import FeatureEncryptionConfig

def create_csi_large_M(seed=100, M=20, D=256):
    """
    创建M=20帧的CSI:
    - 每个维度：15帧为HIGH或LOW，5帧为相反值
    - 确保15帧超过vote_threshold
    """
    np.random.seed(seed)
    frames = np.zeros((M, D))

    for d in range(D):
        if np.random.rand() > 0.5:
            main_value = 10.0  # 15 frames
            minor_value = -10.0  # 5 frames
        else:
            main_value = -10.0  # 15 frames
            minor_value = 10.0  # 5 frames

        for m in range(M):
            if m < 15:
                frames[m, d] = main_value
            else:
                frames[m, d] = minor_value

    return frames

# 创建新配置with M=20
config = FeatureEncryptionConfig()
config.M_FRAMES = 20
config.VOTE_THRESHOLD = 11  # > 20/2

quantizer = FeatureQuantizer(config)

print("=" * 80)
print("LARGE M (M=20) CSI TESTING")
print(f"M_FRAMES: {config.M_FRAMES}")
print(f"Target: {config.TARGET_BITS} bits")
print(f"Vote threshold: {config.VOTE_THRESHOLD}")
print("=" * 80)

Z_frames = create_csi_large_M(seed=100, M=20, D=256)

# 检查一个维度
print("\nSample dimension 0:")
vals = Z_frames[:, 0]
print(f"  Values: {vals}")

print("\nComputing thresholds...")
theta_L, theta_H = quantizer.compute_thresholds(Z_frames, method='percentile')

sorted_vals = np.sort(vals)
print(f"  Sorted: {sorted_vals}")
print(f"  theta_L: {theta_L[0]:.4f}, theta_H: {theta_H[0]:.4f}")

Q_frames = quantizer.quantize_frames(Z_frames, theta_L, theta_H)

print(f"\nDim 0 quantized: {Q_frames[:, 0]}")
count_0 = np.sum(Q_frames[:, 0] == 0)
count_1 = np.sum(Q_frames[:, 0] == 1)
count_neg1 = np.sum(Q_frames[:, 0] == -1)
print(f"  count_0={count_0}, count_1={count_1}, count_-1={count_neg1}")

if count_0 >= config.VOTE_THRESHOLD:
    print(f"  ✓ PASS with bit=0")
elif count_1 >= config.VOTE_THRESHOLD:
    print(f"  ✓ PASS with bit=1")
else:
    print(f"  ✗ REJECT")

print("\nOverall Q_frames statistics:")
unique_vals = np.unique(Q_frames)
print(f"  Unique values: {unique_vals}")
for val in unique_vals:
    count = np.sum(Q_frames == val)
    print(f"    Count of {val}: {count} ({count/Q_frames.size*100:.1f}%)")

print("\nMajority vote...")
r_bits, selected_dims = quantizer.majority_vote(Q_frames)

padding_needed = max(0, config.TARGET_BITS - len(r_bits))
print(f"\nResults:")
print(f"  Majority vote: {len(r_bits)} bits from {len(selected_dims)} dimensions")
print(f"  Random padding needed: {padding_needed} bits")

if len(r_bits) >= config.TARGET_BITS:
    print(f"  ✓✓✓ SUCCESS! No random padding needed!")
elif padding_needed <= 50:
    print(f"  ✓ Acceptable (minimal padding)")
else:
    print(f"  ✗ Failed")

print("\n" + "=" * 80)
