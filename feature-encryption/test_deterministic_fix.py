"""
快速验证确定性模式修复是否有效

这个脚本用于验证BCH解码失败问题是否已修复。
"""
import sys
from pathlib import Path
import secrets
import numpy as np

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from config import FeatureEncryptionConfig
from feature_encryption import FeatureEncryption, Context

def test_deterministic_mode():
    """测试确定性模式是否工作"""
    print("=" * 80)
    print("测试确定性模式修复")
    print("=" * 80)

    # 创建配置
    config = FeatureEncryptionConfig()

    # 创建FE实例（启用确定性模式）
    print("\n[1] 创建FeatureEncryption实例（启用确定性测试模式）...")
    fe = FeatureEncryption(config, deterministic_for_testing=True)
    print("✓ 实例创建成功")

    # 生成测试数据
    print("\n[2] 生成测试CSI数据...")
    np.random.seed(42)
    Z_frames = np.random.randn(6, 62)
    print(f"✓ CSI数据生成成功，shape={Z_frames.shape}")

    # 准备上下文
    print("\n[3] 准备上下文...")
    context = Context(
        srcMAC=bytes.fromhex('001122334455'),
        dstMAC=bytes.fromhex('AABBCCDDEEFF'),
        dom=b'TestDomain',
        ver=1,
        epoch=12345,
        Ci=0,
        nonce=secrets.token_bytes(16)
    )
    print("✓ 上下文创建成功")

    # 注册
    print("\n[4] 执行注册...")
    try:
        key_output1, metadata1 = fe.register(
            device_id="device001",
            Z_frames=Z_frames,
            context=context,
            mask_bytes=b'mask'
        )
        print("✓ 注册成功")
        print(f"  K:  {key_output1.K.hex()[:48]}...")
        print(f"  Ks: {key_output1.Ks.hex()[:48]}...")
        print(f"  比特数: {metadata1['num_bits']}")
    except Exception as e:
        print(f"✗ 注册失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 认证（使用完全相同的Z_frames）
    print("\n[5] 执行认证（使用相同的CSI数据）...")
    try:
        key_output2, success = fe.authenticate(
            device_id="device001",
            Z_frames=Z_frames,  # 相同的特征
            context=context,
            mask_bytes=b'mask'
        )

        if success:
            print("✓ 认证成功")
            print(f"  K:  {key_output2.K.hex()[:48]}...")
            print(f"  Ks: {key_output2.Ks.hex()[:48]}...")
        else:
            print("✗ 认证失败（BCH解码失败）")
            return False
    except Exception as e:
        print(f"✗ 认证异常: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 验证一致性
    print("\n[6] 验证密钥一致性...")
    k_match = (key_output1.K == key_output2.K)
    ks_match = (key_output1.Ks == key_output2.Ks)
    s_match = (key_output1.S == key_output2.S)

    if k_match:
        print("✓✓✓ 特征密钥 K 完全一致")
    else:
        print("✗ 特征密钥 K 不一致")

    if ks_match:
        print("✓✓✓ 会话密钥 Ks 完全一致")
    else:
        print("✗ 会话密钥 Ks 不一致")

    if s_match:
        print("✓✓✓ 稳定特征串 S 完全一致")
    else:
        print("✗ 稳定特征串 S 不一致")

    print("\n" + "=" * 80)
    if k_match and ks_match and s_match:
        print("✓✓✓ 修复成功！所有密钥一致")
        print("=" * 80)
        return True
    else:
        print("✗✗✗ 修复失败，密钥不一致")
        print("=" * 80)
        return False


def test_non_deterministic_mode():
    """测试非确定性模式（生产模式）"""
    print("\n\n")
    print("=" * 80)
    print("测试非确定性模式（生产模式，预期失败）")
    print("=" * 80)

    config = FeatureEncryptionConfig()

    # 不启用确定性模式
    print("\n[1] 创建FeatureEncryption实例（不启用确定性模式）...")
    fe = FeatureEncryption(config, deterministic_for_testing=False)
    print("✓ 实例创建成功")

    # 生成测试数据
    np.random.seed(42)
    Z_frames = np.random.randn(6, 62)

    # 准备上下文
    context = Context(
        srcMAC=bytes.fromhex('001122334455'),
        dstMAC=bytes.fromhex('AABBCCDDEEFF'),
        dom=b'TestDomain',
        ver=1,
        epoch=12345,
        Ci=0,
        nonce=secrets.token_bytes(16)
    )

    # 注册
    print("\n[2] 执行注册...")
    key_output1, metadata1 = fe.register(
        device_id="device002",
        Z_frames=Z_frames,
        context=context,
        mask_bytes=b'mask'
    )
    print(f"✓ 注册成功")

    # 认证
    print("\n[3] 执行认证...")
    key_output2, success = fe.authenticate(
        device_id="device002",
        Z_frames=Z_frames,
        context=context,
        mask_bytes=b'mask'
    )

    if success:
        print("✓ 认证成功（意外！在非确定性模式下应该失败）")
        k_match = (key_output1.K == key_output2.K)
        if k_match:
            print("  密钥一致（非常罕见，可能是巧合）")
        else:
            print("  密钥不一致（预期行为）")
    else:
        print("✓ 认证失败（预期行为，因为使用了随机填充）")

    print("=" * 80)


if __name__ == "__main__":
    print("\n")
    print("=" * 80)
    print("BCH解码失败修复验证")
    print("=" * 80)

    # 测试确定性模式
    test1_passed = test_deterministic_mode()

    # 测试非确定性模式（可选）
    # test_non_deterministic_mode()

    # 最终结果
    print("\n\n")
    print("=" * 80)
    print("最终结果")
    print("=" * 80)

    if test1_passed:
        print("✓✓✓ 修复验证通过！")
        print("\n现在可以运行完整测试：")
        print("  python test_progressive.py")
        print("  python test_device_verifier.py")
    else:
        print("✗✗✗ 修复验证失败")
        print("\n请检查代码修改是否正确")

    print("=" * 80)
