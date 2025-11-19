"""测试使用'fixed'阈值方法"""
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'feature-encryption'))

from src.quantizer import FeatureQuantizer
from src.config import FeatureEncryptionConfig

def create_majority_csi(seed=100, M=6, D=256):
    """创建5/6 majority的CSI特征"""
    np.random.seed(seed)
    frames = np.zeros((M, D))

    for d in range(D):
        base = np.random.randn() * 2

        for m in range(M):
            if m < 5:  # 5 frames at base
                frames[m, d] = base
            else:  # 1 frame away from base
                frames[m, d] = base + 4.0 * (1 if base > 0 else -1)

    return frames

config = FeatureEncryptionConfig()
quantizer = FeatureQuantizer(config)

print("=" * 80)
print("FIXED THRESHOLD METHOD TESTING")
print(f"Target: {config.TARGET_BITS} bits")
print("=" * 80)

Z_frames = create_majority_csi(seed=100, M=6, D=256)

for method in ['percentile', 'fixed']:
    print(f"\nMethod: {method}")
    print("-" * 80)

    theta_L, theta_H = quantizer.compute_thresholds(Z_frames, method=method)

    # 检查第一个维度
    print(f"  Dim 0 values: {Z_frames[:, 0]}")
    print(f"  Dim 0: mean={np.mean(Z_frames[:, 0]):.4f}, std={np.std(Z_frames[:, 0]):.4f}")
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
        break  # Found a working method
    elif padding_needed <= 50:
        print(f"  ✓ Acceptable (minimal padding)")
    else:
        print(f"  ✗ Failed")

print("\n" + "=" * 80)
