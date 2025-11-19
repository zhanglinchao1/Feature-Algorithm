"""
模式二集成测试

测试设备端和验证端的完整认证流程。
"""

import sys
import secrets
import logging
import numpy as np
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import AuthConfig
from src.common import AuthContext
from src.mode2_strong_auth import DeviceSide, VerifierSide

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def simulate_csi_features(base_seed=42, noise_level=0.1, M=6, D=64):
    """模拟CSI特征

    Args:
        base_seed: 基础随机种子
        noise_level: 噪声水平
        M: 帧数
        D: 特征维度

    Returns:
        np.ndarray: M x D的特征矩阵
    """
    np.random.seed(base_seed)
    base_feature = np.random.randn(D)

    Z_frames = np.zeros((M, D))
    for m in range(M):
        noise = np.random.randn(D) * noise_level
        Z_frames[m] = base_feature + noise

    return Z_frames


def test_mode2_success():
    """测试模式二成功认证场景"""
    logger.info("="*80)
    logger.info("TEST: Mode2 Success Scenario")
    logger.info("="*80)

    # 配置
    config = AuthConfig.default()

    # 设备信息
    dev_id = bytes.fromhex('001122334455')
    issuer_id = bytes.fromhex('AABBCCDDEEFF')
    issuer_key = secrets.token_bytes(32)

    # 初始化设备端和验证端
    device = DeviceSide(config)
    verifier = VerifierSide(config, issuer_id, issuer_key)

    # 准备上下文
    nonce = secrets.token_bytes(16)
    context = AuthContext(
        src_mac=dev_id,
        dst_mac=issuer_id,
        epoch=12345,
        nonce=nonce,
        seq=1,
        alg_id='FeatureAuth-v1',
        ver=1,
        csi_id=1
    )

    # 生成模拟特征
    logger.info("Generating simulated CSI features...")
    Z_frames_device = simulate_csi_features(base_seed=100, noise_level=0.05)
    Z_frames_verifier = simulate_csi_features(base_seed=200, noise_level=0.05)

    # 设备端：创建AuthReq
    logger.info("\n" + "="*60)
    logger.info("PHASE 1: Device Side - Creating AuthReq")
    logger.info("="*60)

    auth_req, Ks_device = device.create_auth_request(dev_id, Z_frames_device, context)

    logger.info(f"✓ AuthReq created")
    logger.info(f"  Size: {len(auth_req.serialize())} bytes")
    logger.info(f"  Ks (device): {Ks_device.hex()[:40]}...")

    # 验证端需要先注册设备（模拟）
    # 实际中应在设备注册时获取K
    logger.info("\n" + "="*60)
    logger.info("SETUP: Registering device on verifier side (simulation)")
    logger.info("="*60)

    # 为了测试，我们需要设备的K
    # 在实际部署中，验证端会在注册阶段获取并存储K
    # 这里我们通过重新调用FeatureKeyGen来获取K
    from src.feature_encryption import FeatureEncryption, Context as FEContext
    fe_temp = FeatureEncryption()
    fe_context_temp = FEContext(
        srcMAC=context.src_mac,
        dstMAC=context.dst_mac,
        dom=b'FeatureAuth',
        ver=context.ver,
        epoch=context.epoch,
        Ci=0,
        nonce=context.nonce
    )
    key_output_temp, _ = fe_temp.register(
        device_id=dev_id.hex(),
        Z_frames=Z_frames_device,
        context=fe_context_temp,
        mask_bytes=b'device_mask'
    )
    K_device = key_output_temp.K

    verifier.register_device(dev_id, K_device, context.epoch)
    logger.info(f"✓ Device registered with K={K_device.hex()[:40]}...")

    # 验证端：验证AuthReq
    logger.info("\n" + "="*60)
    logger.info("PHASE 2: Verifier Side - Verifying AuthReq")
    logger.info("="*60)

    result = verifier.verify_auth_request(auth_req, Z_frames_verifier)

    # 检查结果
    logger.info("\n" + "="*60)
    logger.info("PHASE 3: Verification Result")
    logger.info("="*60)

    logger.info(f"Success: {result.success}")
    logger.info(f"Mode: {result.mode}")

    if result.success:
        logger.info(f"✓ Authentication successful")
        logger.info(f"  Token size: {len(result.token)} bytes")
        logger.info(f"  Ks (verifier): {result.session_key.hex()[:40]}...")

        # 验证会话密钥是否一致
        if result.session_key == Ks_device:
            logger.info(f"✓✓✓ Session keys match! Authentication fully successful!")
        else:
            logger.error(f"✗ Session keys mismatch!")
            logger.error(f"  Device:   {Ks_device.hex()}")
            logger.error(f"  Verifier: {result.session_key.hex()}")
            raise AssertionError("Session key mismatch")
    else:
        logger.error(f"✗ Authentication failed")
        logger.error(f"  Reason: {result.reason}")
        raise AssertionError(f"Authentication should succeed but failed: {result.reason}")

    logger.info("="*80)
    logger.info("✓✓✓ TEST PASSED: Mode2 Success Scenario")
    logger.info("="*80)


def test_mode2_tag_mismatch():
    """测试Tag不匹配的场景"""
    logger.info("\n"*2)
    logger.info("="*80)
    logger.info("TEST: Mode2 Tag Mismatch Scenario")
    logger.info("="*80)

    config = AuthConfig.default()
    dev_id = bytes.fromhex('001122334455')
    issuer_id = bytes.fromhex('AABBCCDDEEFF')
    issuer_key = secrets.token_bytes(32)

    device = DeviceSide(config)
    verifier = VerifierSide(config, issuer_id, issuer_key)

    nonce = secrets.token_bytes(16)
    context = AuthContext(
        src_mac=dev_id,
        dst_mac=issuer_id,
        epoch=12345,
        nonce=nonce,
        seq=1,
        alg_id='FeatureAuth-v1',
        ver=1,
        csi_id=1
    )

    Z_frames_device = simulate_csi_features(base_seed=100)
    Z_frames_verifier = simulate_csi_features(base_seed=200)

    # 创建AuthReq
    auth_req, Ks_device = device.create_auth_request(dev_id, Z_frames_device, context)

    # 篡改Tag
    logger.info("Tampering with Tag...")
    auth_req.tag = secrets.token_bytes(16)
    logger.info(f"  New Tag: {auth_req.tag.hex()}")

    # 注册设备
    from src.feature_encryption import FeatureEncryption, Context as FEContext
    fe_temp = FeatureEncryption()
    fe_context_temp = FEContext(
        srcMAC=context.src_mac,
        dstMAC=context.dst_mac,
        dom=b'FeatureAuth',
        ver=context.ver,
        epoch=context.epoch,
        Ci=0,
        nonce=context.nonce
    )
    key_output_temp, _ = fe_temp.register(
        device_id=dev_id.hex(),
        Z_frames=Z_frames_device,
        context=fe_context_temp,
        mask_bytes=b'device_mask'
    )
    verifier.register_device(dev_id, key_output_temp.K, context.epoch)

    # 验证AuthReq（应该失败）
    logger.info("\nVerifying AuthReq (should fail)...")
    result = verifier.verify_auth_request(auth_req, Z_frames_verifier)

    # 检查结果
    if not result.success and result.reason == "tag_mismatch":
        logger.info(f"✓✓✓ TEST PASSED: Tag mismatch correctly detected")
        logger.info(f"  Reason: {result.reason}")
    else:
        logger.error(f"✗ TEST FAILED: Should reject tampered Tag")
        raise AssertionError("Tag mismatch not detected")

    logger.info("="*80)


def test_mode2_digest_mismatch():
    """测试digest不匹配的场景"""
    logger.info("\n"*2)
    logger.info("="*80)
    logger.info("TEST: Mode2 Digest Mismatch Scenario")
    logger.info("="*80)

    config = AuthConfig.default()
    dev_id = bytes.fromhex('001122334455')
    issuer_id = bytes.fromhex('AABBCCDDEEFF')
    issuer_key = secrets.token_bytes(32)

    device = DeviceSide(config)
    verifier = VerifierSide(config, issuer_id, issuer_key)

    nonce = secrets.token_bytes(16)
    context = AuthContext(
        src_mac=dev_id,
        dst_mac=issuer_id,
        epoch=12345,
        nonce=nonce,
        seq=1,
        alg_id='FeatureAuth-v1',
        ver=1,
        csi_id=1
    )

    Z_frames_device = simulate_csi_features(base_seed=100)
    Z_frames_verifier = simulate_csi_features(base_seed=200)

    # 创建AuthReq
    auth_req, Ks_device = device.create_auth_request(dev_id, Z_frames_device, context)

    # 篡改digest
    logger.info("Tampering with digest...")
    auth_req.digest = secrets.token_bytes(32)
    logger.info(f"  New digest: {auth_req.digest.hex()[:40]}...")

    # 注册设备
    from src.feature_encryption import FeatureEncryption, Context as FEContext
    fe_temp = FeatureEncryption()
    fe_context_temp = FEContext(
        srcMAC=context.src_mac,
        dstMAC=context.dst_mac,
        dom=b'FeatureAuth',
        ver=context.ver,
        epoch=context.epoch,
        Ci=0,
        nonce=context.nonce
    )
    key_output_temp, _ = fe_temp.register(
        device_id=dev_id.hex(),
        Z_frames=Z_frames_device,
        context=fe_context_temp,
        mask_bytes=b'device_mask'
    )
    verifier.register_device(dev_id, key_output_temp.K, context.epoch)

    # 验证AuthReq（应该失败）
    logger.info("\nVerifying AuthReq (should fail)...")
    result = verifier.verify_auth_request(auth_req, Z_frames_verifier)

    # 检查结果
    if not result.success and result.reason == "digest_mismatch":
        logger.info(f"✓✓✓ TEST PASSED: Digest mismatch correctly detected")
        logger.info(f"  Reason: {result.reason}")
    else:
        logger.error(f"✗ TEST FAILED: Should reject mismatched digest")
        raise AssertionError("Digest mismatch not detected")

    logger.info("="*80)


def main():
    """运行所有测试"""
    logger.info("\n")
    logger.info("="*80)
    logger.info("MODE 2 STRONG AUTHENTICATION TEST SUITE")
    logger.info("="*80)

    tests = [
        ("Success Scenario", test_mode2_success),
        ("Tag Mismatch", test_mode2_tag_mismatch),
        ("Digest Mismatch", test_mode2_digest_mismatch),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            logger.error(f"\n✗✗✗ TEST FAILED: {test_name}")
            logger.error(f"  Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    logger.info("\n")
    logger.info("="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)
    logger.info(f"Total: {len(tests)}")
    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {failed}")

    if failed == 0:
        logger.info("\n✓✓✓ ALL TESTS PASSED ✓✓✓")
    else:
        logger.error("\n✗✗✗ SOME TESTS FAILED ✗✗✗")

    logger.info("="*80)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())
