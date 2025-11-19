"""
快速测试BCH编解码修复
"""
import secrets
from src.config import FeatureEncryptionConfig
from src.fuzzy_extractor import FuzzyExtractor

print("测试BCH编解码循环...")

config = FeatureEncryptionConfig()
extractor = FuzzyExtractor(config)

print(f"BCH参数: n={config.BCH_N}, k={config.BCH_K}, t={config.BCH_T}")
print(f"bch.ecc_bytes: {extractor.bch.ecc_bytes}")
print(f"bch.n: {extractor.bch.n}")
print(f"bch.t: {extractor.bch.t}")

# 测试1: 无噪声
print("\n测试1: 无噪声（r' = r）")
r = [secrets.randbelow(2) for _ in range(config.TARGET_BITS)]
P = extractor.generate_helper_data(r)
S, success = extractor.extract_stable_key(r, P)

print(f"  成功: {success}")
print(f"  r == S: {r == S}")
if r != S:
    diff_count = sum(1 for i in range(len(r)) if r[i] != S[i])
    print(f"  不同位数: {diff_count}/{len(r)}")

# 测试2: 少量噪声
print("\n测试2: 5位错误")
import numpy as np
r2 = [secrets.randbelow(2) for _ in range(config.TARGET_BITS)]
P2 = extractor.generate_helper_data(r2)

r2_noisy = r2.copy()
error_positions = np.random.choice(len(r2), size=5, replace=False)
for pos in error_positions:
    r2_noisy[pos] = 1 - r2_noisy[pos]

S2, success2 = extractor.extract_stable_key(r2_noisy, P2)
print(f"  成功: {success2}")
print(f"  r == S: {r2 == S2}")
if r2 != S2:
    diff_count = sum(1 for i in range(len(r2)) if r2[i] != S2[i])
    print(f"  不同位数: {diff_count}/{len(r2)}")

print("\n" + "="*50)
if success and r == S:
    print("✓ 测试通过！BCH编解码正常工作")
else:
    print("✗ 测试失败！需要继续调试")

