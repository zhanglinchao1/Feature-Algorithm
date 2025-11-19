"""测试平衡的极端值分布"""
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'feature-encryption'))

from src.quantizer import FeatureQuantizer
from src.config import FeatureEncryptionConfig

def create_balanced_csi(seed=100, M=6, D=256):
    """
    创建平衡分布的CSI:
    - 每个维度：4帧HIGH(+10), 2帧LOW(-10)
    - 这样4帧会通过vote_threshold=4
    """
    np.random.seed(seed)
    frames = np.zeros((M, D))

    for d in range(D):
        # 随机选择主值(4帧)和次值(2帧)
        if np.random.rand() > 0.5:
            main_value = 10.0  # 4 frames
            minor_value = -10.0  # 2 frames
        else:
            main_value = -10.0  # 4 frames
            minor_value = 10.0  # 2 frames

        # 4 frames = main, 2 frames = minor
        for m in range(M):
            if m < 4:
                frames[m, d] = main_value
            else:
                frames[m, d] = minor_value

    return frames

config = FeatureEncryptionConfig()
quantizer = FeatureQuantizer(config)

print("=" * 80)
print("BALANCED EXTREME VALUE CSI TESTING")
print(f"Target: {config.TARGET_BITS} bits")
print(f"Vote threshold: {config.VOTE_THRESHOLD}")
print("=" * 80)

Z_frames = create_balanced_csi(seed=100, M=6, D=256)

# 检查几个维度
print("\nSample dimensions:")
for d in range(3):
    vals = Z_frames[:, d]
    print(f"  Dim {d}: {vals}")

print("\nComputing thresholds...")
theta_L, theta_H = quantizer.compute_thresholds(Z_frames, method='percentile')

print("\nSample dimension analysis:")
for d in range(3):
    vals = Z_frames[:, d]
    sorted_vals = np.sort(vals)
    print(f"  Dim {d}:")
    print(f"    Values: {vals}")
    print(f"    Sorted: {sorted_vals}")
    print(f"    theta_L: {theta_L[d]:.4f}, theta_H: {theta_H[d]:.4f}")

Q_frames = quantizer.quantize_frames(Z_frames, theta_L, theta_H)

print("\nQuantized sample dimensions:")
for d in range(3):
    q_vals = Q_frames[:, d]
    count_0 = np.sum(q_vals == 0)
    count_1 = np.sum(q_vals == 1)
    count_neg1 = np.sum(q_vals == -1)
    print(f"  Dim {d}: {q_vals}")
    print(f"    count_0={count_0}, count_1={count_1}, count_-1={count_neg1}")
    if count_0 >= config.VOTE_THRESHOLD:
        print(f"    ✓ PASS with bit=0")
    elif count_1 >= config.VOTE_THRESHOLD:
        print(f"    ✓ PASS with bit=1")
    else:
        print(f"    ✗ REJECT")

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
