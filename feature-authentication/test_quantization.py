"""测试量化器产生多少有效比特"""
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

print("="*80)
print("QUANTIZATION ANALYSIS")
print("="*80)

for D in [64, 96, 128, 192, 256]:
    print(f"\nTesting with D={D} dimensions:")
    Z_frames = simulate_csi(seed=100, noise=0, M=6, D=D)
    
    # 手动调用各步骤
    theta_L, theta_H = quantizer.compute_thresholds(Z_frames)
    Q_frames = quantizer.quantize_frames(Z_frames, theta_L, theta_H)
    r_bits, selected_dims = quantizer.majority_vote(Q_frames)
    
    print(f"  Majority vote: {len(r_bits)} bits from {len(selected_dims)} dimensions")
    print(f"  Target: {config.TARGET_BITS} bits")
    print(f"  Random padding needed: {max(0, config.TARGET_BITS - len(r_bits))} bits")
    
    if len(r_bits) >= config.TARGET_BITS:
        print(f"  ✓ NO random padding needed!")
    else:
        print(f"  ✗ Requires random padding")

print("\n" + "="*80)
