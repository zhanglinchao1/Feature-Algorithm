"""找出实际可获得的比特数"""
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'feature-encryption'))

from src.quantizer import FeatureQuantizer
from src.config import FeatureEncryptionConfig

def create_varied_csi(seed=100, M=6, D=512):
    """
    创建变化丰富的CSI:
    - 每个维度的M个值都不同
    - 使用正态分布但每帧加不同偏移
    """
    np.random.seed(seed)
    frames = np.zeros((M, D))

    # 每个维度生成基准值
    base = np.random.randn(D) * 3

    # 每帧加不同的偏移
    for m in range(M):
        offset = (m - M/2) * 1.5  # 生成 -3.75, -2.25, -0.75, 0.75, 2.25, 3.75
        frames[m] = base + offset

    return frames

config = FeatureEncryptionConfig()
quantizer = FeatureQuantizer(config)

print("=" * 80)
print("FINDING ACHIEVABLE BITS")
print("=" * 80)

for D in [256, 384, 512, 768, 1024]:
    print(f"\nD={D} dimensions:")
    Z_frames = create_varied_csi(seed=100, M=6, D=D)

    theta_L, theta_H = quantizer.compute_thresholds(Z_frames)
    Q_frames = quantizer.quantize_frames(Z_frames, theta_L, theta_H)
    r_bits, selected_dims = quantizer.majority_vote(Q_frames)

    print(f"  Majority vote: {len(r_bits)} bits from {len(selected_dims)} dimensions")
    print(f"  Success rate: {len(selected_dims)/D*100:.1f}%")

    if len(r_bits) >= 256:
        print(f"  ✓ Achieves TARGET_BITS=256!")
    elif len(r_bits) >= 128:
        print(f"  ✓ Could use TARGET_BITS=128")
    elif len(r_bits) >= 64:
        print(f"  ✓ Could use TARGET_BITS=64")

print("\n" + "=" * 80)
