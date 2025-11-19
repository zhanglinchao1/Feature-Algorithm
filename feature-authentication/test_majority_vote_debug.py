"""调试majority vote为何产生0比特"""
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'feature-encryption'))

from src.quantizer import FeatureQuantizer
from src.config import FeatureEncryptionConfig

def simulate_csi(seed=100, noise=0.01, M=6, D=128):
    np.random.seed(seed)
    base = np.random.randn(D)
    frames = np.zeros((M, D))
    for i in range(M):
        frames[i] = base + np.random.randn(D) * noise
    return frames

config = FeatureEncryptionConfig()
quantizer = FeatureQuantizer(config)

Z_frames = simulate_csi(seed=100, noise=0.01, M=6, D=128)

print("=" * 80)
print("MAJORITY VOTE DEBUG")
print("=" * 80)

theta_L, theta_H = quantizer.compute_thresholds(Z_frames)
Q_frames = quantizer.quantize_frames(Z_frames, theta_L, theta_H)

print(f"\nQ_frames shape: {Q_frames.shape}")
print(f"Q_frames unique values: {np.unique(Q_frames)}")

# 统计每个维度的量化值分布
for val in [-1, 0, 1]:
    count = np.sum(Q_frames == val)
    print(f"Count of {val}: {count} ({count/(Q_frames.size)*100:.1f}%)")

# 检查几个维度的详细情况
print("\n" + "=" * 80)
print("DIMENSION ANALYSIS (first 10 dimensions)")
print("=" * 80)

for d in range(min(10, Q_frames.shape[1])):
    q_vals = Q_frames[:, d]
    unique_vals = np.unique(q_vals)

    print(f"\nDim {d}:")
    print(f"  Quantized values across frames: {q_vals}")
    print(f"  Unique values: {unique_vals}")

    # 检查majority vote条件
    if -1 in unique_vals:
        print(f"  ✗ Contains -1 (erased) - REJECTED by majority vote")
    else:
        # 检查是否所有值相同
        if len(unique_vals) == 1:
            print(f"  ✓ All values same: {unique_vals[0]} - ACCEPTED")
        else:
            print(f"  ✗ Mixed values - REJECTED by majority vote")

# 调用majority_vote看实际结果
r_bits, selected_dims = quantizer.majority_vote(Q_frames)
print("\n" + "=" * 80)
print(f"Majority vote result: {len(r_bits)} bits from {len(selected_dims)} dimensions")
print("=" * 80)

# 检查配置中的阈值参数
print(f"\nQuantizer configuration:")
print(f"  alpha = {config.QUANTIZATION_ALPHA}")
print(f"  M (frames) = {Q_frames.shape[0]}")

# 计算理论上的theta_L和theta_H
print(f"\nThreshold statistics:")
print(f"  theta_L mean: {np.mean(theta_L):.4f}, std: {np.std(theta_L):.4f}")
print(f"  theta_H mean: {np.mean(theta_H):.4f}, std: {np.std(theta_H):.4f}")
print(f"  theta_H - theta_L mean: {np.mean(theta_H - theta_L):.4f}")

# 检查实际Z值分布
print(f"\nZ_frames statistics:")
print(f"  Mean: {np.mean(Z_frames):.4f}")
print(f"  Std: {np.std(Z_frames):.4f}")
print(f"  Min: {np.min(Z_frames):.4f}")
print(f"  Max: {np.max(Z_frames):.4f}")
