"""
集成测试
"""

import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import numpy as np
import secrets

# 绝对导入
import config
import feature_encryption
import quantizer

FeatureEncryption = feature_encryption.FeatureEncryption
Context = feature_encryption.Context


def test_full_workflow_csi():
    """测试完整的CSI模式工作流程"""
    print("\n=== 测试CSI模式完整工作流程 ===")

    # 1. 创建配置
    cfg = config.FeatureEncryptionConfig()
    print(f"✓ 配置创建成功: {cfg}")

    # 2. 创建加密实例
    fe = FeatureEncryption(cfg)
    print("✓ 特征加密实例创建成功")

    # 3. 准备上下文
    context = Context(
        srcMAC=b'\x00\x11\x22\x33\x44\x55',
        dstMAC=b'\xAA\xBB\xCC\xDD\xEE\xFF',
        dom=b'TestDomain',
        ver=1,
        epoch=12345,
        Ci=0,
        nonce=secrets.token_bytes(16)
    )
    print("✓ 上下文创建成功")

    # 4. 模拟CSI特征数据
    # 多帧特征：shape (M=6, D=64)
    M = cfg.M_FRAMES
    D = cfg.get_feature_dim('CSI')
    print(f"✓ 特征维度: M={M}, D={D}")

    # 生成基础特征
    base_feature = np.random.randn(D)

    # 生成多帧（添加少量噪声）
    Z_frames = np.zeros((M, D))
    for m in range(M):
        noise = np.random.randn(D) * 0.1  # 10%噪声
        Z_frames[m] = base_feature + noise

    print(f"✓ 生成多帧特征数据: shape={Z_frames.shape}")

    # 5. 注册阶段
    device_id = "test_device_001"
    key_output_register, metadata = fe.register(
        device_id=device_id,
        Z_frames=Z_frames,
        context=context,
        mask_bytes=b'test_mask'
    )

    print("\n--- 注册阶段输出 ---")
    print(f"✓ 稳定特征串 S: {key_output_register.S.hex()[:32]}...")
    print(f"✓ 随机扰动值 L: {key_output_register.L.hex()[:32]}...")
    print(f"✓ 特征密钥 K: {key_output_register.K.hex()[:32]}...")
    print(f"✓ 会话密钥 Ks: {key_output_register.Ks.hex()[:32]}...")
    print(f"✓ 一致性摘要: {key_output_register.digest.hex()}")
    print(f"✓ 比特数: {metadata['bit_count']}")

    # 6. 认证阶段（使用相似但含噪的特征）
    # 生成新的多帧特征（添加更大噪声模拟真实测量）
    Z_frames_auth = np.zeros((M, D))
    for m in range(M):
        noise = np.random.randn(D) * 0.15  # 15%噪声
        Z_frames_auth[m] = base_feature + noise

    key_output_auth, success = fe.authenticate(
        device_id=device_id,
        Z_frames=Z_frames_auth,
        context=context,
        mask_bytes=b'test_mask'
    )

    print("\n--- 认证阶段输出 ---")
    if success:
        print("✓ 认证成功！")
        print(f"✓ 特征密钥 K: {key_output_auth.K.hex()[:32]}...")
        print(f"✓ 会话密钥 Ks: {key_output_auth.Ks.hex()[:32]}...")

        # 7. 验证密钥一致性
        if key_output_register.K == key_output_auth.K:
            print("✓✓✓ 特征密钥K完全一致！算法正确！")
        else:
            print("✗✗✗ 特征密钥K不一致！可能存在问题。")

        if key_output_register.Ks == key_output_auth.Ks:
            print("✓✓✓ 会话密钥Ks完全一致！算法正确！")
        else:
            print("✗✗✗ 会话密钥Ks不一致！可能存在问题。")
    else:
        print("✗ 认证失败")

    print("\n=== 测试完成 ===\n")

    return success


def test_config_validation():
    """测试配置验证"""
    print("\n=== 测试配置验证 ===")

    # 测试有效配置
    try:
        cfg = config.FeatureEncryptionConfig()
        cfg.validate()
        print("✓ 默认配置验证通过")
    except Exception as e:
        print(f"✗ 默认配置验证失败: {e}")
        return False

    # 测试无效配置
    try:
        invalid_config = config.FeatureEncryptionConfig(M_FRAMES=2)  # 太小
        invalid_config.validate()
        print("✗ 应该拒绝无效配置（M_FRAMES=2）")
        return False
    except ValueError:
        print("✓ 正确拒绝无效配置（M_FRAMES=2）")

    # 测试投票阈值
    try:
        invalid_config = config.FeatureEncryptionConfig(VOTE_THRESHOLD=2, M_FRAMES=6)
        invalid_config.validate()
        print("✗ 应该拒绝无效配置（VOTE_THRESHOLD=2 < M_FRAMES//2+1）")
        return False
    except ValueError:
        print("✓ 正确拒绝无效配置（投票阈值过低）")

    print("=== 配置验证测试完成 ===\n")
    return True


def test_quantizer():
    """测试量化器"""
    print("\n=== 测试量化器 ===")

    cfg = config.FeatureEncryptionConfig()
    qtz = quantizer.FeatureQuantizer(cfg)

    # 生成测试数据
    M, D = 6, 64
    Z_frames = np.random.randn(M, D)

    # 测试门限计算
    theta_L, theta_H = qtz.compute_thresholds(Z_frames)
    print(f"✓ 门限计算成功: theta_L.shape={theta_L.shape}, theta_H.shape={theta_H.shape}")

    # 测试量化
    Q_frames = qtz.quantize_frames(Z_frames, theta_L, theta_H)
    print(f"✓ 量化成功: Q_frames.shape={Q_frames.shape}")

    # 验证量化值在{-1, 0, 1}范围内
    unique_values = np.unique(Q_frames)
    print(f"✓ 量化值: {unique_values}")
    assert all(v in [-1, 0, 1] for v in unique_values), "量化值应该在{-1,0,1}内"

    # 测试投票
    r_bits, selected_dims = qtz.majority_vote(Q_frames)
    print(f"✓ 投票成功: 得到 {len(r_bits)} 个比特")

    print("=== 量化器测试完成 ===\n")
    return True


if __name__ == "__main__":
    print("\n" + "="*60)
    print("特征加密算法 - 集成测试")
    print("="*60)

    # 运行测试
    all_passed = True

    try:
        all_passed &= test_config_validation()
    except Exception as e:
        print(f"✗ 配置验证测试失败: {e}")
        all_passed = False

    try:
        all_passed &= test_quantizer()
    except Exception as e:
        print(f"✗ 量化器测试失败: {e}")
        all_passed = False

    try:
        all_passed &= test_full_workflow_csi()
    except Exception as e:
        print(f"✗ 完整工作流程测试失败: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    # 输出总结
    print("\n" + "="*60)
    if all_passed:
        print("✓✓✓ 所有测试通过！")
    else:
        print("✗✗✗ 部分测试失败")
    print("="*60 + "\n")
