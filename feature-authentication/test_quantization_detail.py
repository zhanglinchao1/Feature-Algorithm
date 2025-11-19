"""详细测试量化过程"""
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'feature-encryption'))

from src.quantizer import FeatureQuantizer
from src.config import FeatureEncryptionConfig

def simulate_csi(seed=100, noise=0, M=6, D=64):
    np.random.seed(seed)
    base = np.random.randn(D)
    frames = np.zeros((M, D))
    for i in range(M):
        frames[i] = base + np.random.randn(D) * noise
    return frames

config = FeatureEncryptionConfig()
quantizer = FeatureQuantizer(config)

Z_frames = simulate_csi(seed=100, noise=0, M=6, D=64)

print("Z_frames shape:", Z_frames.shape)
print("First frame, first 5 values:", Z_frames[0, :5])
print("Variance across frames (first 5 dims):", np.var(Z_frames, axis=0)[:5])

theta_L, theta_H = quantizer.compute_thresholds(Z_frames)
print(f"\ntheta_L (first 5): {theta_L[:5]}")
print(f"theta_H (first 5): {theta_H[:5]}")

Q_frames = quantizer.quantize_frames(Z_frames, theta_L, theta_H)
print(f"\nQ_frames shape: {Q_frames.shape}")
print(f"Q_frames unique values: {np.unique(Q_frames)}")
print(f"Count of -1 (erased): {np.sum(Q_frames == -1)}")
print(f"Count of 0: {np.sum(Q_frames == 0)}")
print(f"Count of 1: {np.sum(Q_frames == 1)}")

# 检查一个维度的例子
dim = 0
print(f"\nDimension {dim}:")
print(f"  Values across frames: {Z_frames[:, dim]}")
print(f"  theta_L: {theta_L[dim]}, theta_H: {theta_H[dim]}")
print(f"  Quantized: {Q_frames[:, dim]}")
