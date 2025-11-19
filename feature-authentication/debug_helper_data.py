"""
调试helper data机制
"""
import sys
import secrets
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'feature-encryption'))

from src.feature_encryption import FeatureEncryption, Context as FEContext
from src.config import FeatureEncryptionConfig as FEConfig

def simulate_csi(seed=42, noise=0):
    np.random.seed(seed)
    base = np.random.randn(64)
    frames = np.zeros((6, 64))
    for i in range(6):
        frames[i] = base + np.random.randn(64) * noise
    return frames

print("="*80)
print("DEBUG: Helper Data Mechanism")
print("="*80)

# 创建共享FE实例
fe_config = FEConfig()
fe = FeatureEncryption(fe_config)

dev_id = "001122334455"
nonce = secrets.token_bytes(16)

context = FEContext(
    srcMAC=bytes.fromhex('001122334455'),
    dstMAC=bytes.fromhex('AABBCCDDEEFF'),
    dom=b'FeatureAuth',
    ver=1,
    epoch=12345,
    Ci=0,
    nonce=nonce
)

# 生成完全相同的特征
Z_frames = simulate_csi(seed=100, noise=0)

print("\n1. DEVICE SIDE: Calling register()")
print("-" * 60)

# 先看看量化结果
r_register, theta_L_reg, theta_H_reg = fe.quantizer.process_multi_frames(Z_frames)
print(f"  Quantized r (register) length: {len(r_register)} bits")
print(f"  First 20 bits of r: {r_register[:20]}")
print(f"  theta_L shape: {theta_L_reg.shape}, theta_H shape: {theta_H_reg.shape}")

try:
    key_output1, metadata1 = fe.register(
        device_id=dev_id,
        Z_frames=Z_frames,
        context=context,
        mask_bytes=b'device_mask'
    )
    print(f"✓ register() success")
    print(f"  K: {key_output1.K.hex()[:40]}...")
    print(f"  Ks: {key_output1.Ks.hex()[:40]}...")
    print(f"  Helper data stored for device: {dev_id}")
except Exception as e:
    print(f"✗ register() failed: {e}")
    import traceback
    traceback.print_exc()

# 检查helper data是否存在
print("\n2. CHECK: Helper data存储状态")
print("-" * 60)
print(f"  Helper data store keys: {list(fe._helper_data_store.keys())}")
if dev_id in fe._helper_data_store:
    P = fe._helper_data_store[dev_id]
    print(f"  ✓ Helper data found for {dev_id}: {len(P)} bytes")
else:
    print(f"  ✗ No helper data for {dev_id}")

print("\n3. VERIFIER SIDE: Calling authenticate() with SAME Z_frames")
print("-" * 60)

# 先检查量化结果
r_prime, theta_L, theta_H = fe.quantizer.process_multi_frames(Z_frames)
print(f"  Quantized r_prime (authenticate) length: {len(r_prime)} bits")
print(f"  First 20 bits of r_prime: {r_prime[:20]}")

# 比较r和r_prime
if len(r_prime) == len(r_register):
    hamming_dist = sum(r_prime[i] != r_register[i] for i in range(len(r_prime)))
    print(f"\n  Hamming distance between r and r_prime: {hamming_dist} / {len(r_prime)}")
    if hamming_dist == 0:
        print(f"  ✓ r and r_prime are IDENTICAL")
    else:
        print(f"  ✗ r and r_prime differ in {hamming_dist} bits")

# 加载helper data
P = fe._load_helper_data(dev_id)
if P:
    print(f"  Loaded helper data: {len(P)} bytes")

    # 尝试BCH解码
    print(f"\n  Attempting BCH decode...")
    try:
        S_bits, decode_success = fe.fuzzy_extractor.extract_stable_key(r_prime, P)
        if decode_success:
            print(f"  ✓ BCH decode success!")
            print(f"    S_bits length: {len(S_bits)}")
        else:
            print(f"  ✗ BCH decode failed - returned success=False")
    except Exception as e:
        print(f"  ✗ BCH decode exception: {e}")
        import traceback
        traceback.print_exc()
else:
    print(f"  ✗ No helper data found")

print(f"\n  Now calling full authenticate()...")
try:
    key_output2, success = fe.authenticate(
        device_id=dev_id,
        Z_frames=Z_frames,  # 完全相同的特征
        context=context,
        mask_bytes=b'device_mask'
    )
    if success:
        print(f"✓ authenticate() success")
        print(f"  K: {key_output2.K.hex()[:40]}...")
        print(f"  Ks: {key_output2.Ks.hex()[:40]}...")

        # 比较密钥
        if key_output1.K == key_output2.K:
            print(f"  ✓✓✓ K matches!")
        else:
            print(f"  ✗ K mismatch!")

        if key_output1.Ks == key_output2.Ks:
            print(f"  ✓✓✓ Ks matches!")
        else:
            print(f"  ✗ Ks mismatch!")
    else:
        print(f"✗ authenticate() failed - success=False")
except Exception as e:
    print(f"✗ authenticate() failed with exception: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("DEBUG COMPLETE")
print("="*80)
