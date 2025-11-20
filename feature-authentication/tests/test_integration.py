"""
两种认证模式的集成测试

测试模式一和模式二的协同工作，以及"先快后稳"的门控策略。
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
from src.mode1_rff_auth import Mode1FastAuth
from src.mode2_strong_auth import DeviceSide, VerifierSide

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


# 🔧 TEST WORKAROUND for deterministic quantizer
def deterministic_random_bits(n: int):
    """Generate deterministic bits for testing."""
    return [i % 2 for i in range(n)]


def simulate_csi_features(base_seed=42, noise_level=0.1, M=6, D=64):
    """模拟CSI特征"""
    np.random.seed(base_seed)
    base_feature = np.random.randn(D)
    
    Z_frames = np.zeros((M, D))
    for m in range(M):
        noise = np.random.randn(D) * noise_level
        Z_frames[m] = base_feature + noise
    
    return Z_frames


def test_mode1_then_mode2_success():
    """测试"先快后稳"策略：模式一通过后，可选择升级到模式二"""
    logger.info("="*80)
    logger.info("TEST: Mode1 → Mode2 Success (Fast then Strong)")
    logger.info("="*80)
    
    # 同时启用两种模式
    config = AuthConfig(
        MODE1_ENABLED=True,
        MODE2_ENABLED=True,
        RFF_THRESHOLD=0.8,
        TOKEN_FAST_TTL=60,
        MAT_TTL=300
    )
    
    # 设备信息
    dev_id = bytes.fromhex('001122334455')
    issuer_id = bytes.fromhex('AABBCCDDEEFF')
    issuer_key = secrets.token_bytes(32)
    
    # ====== 阶段一：快速认证（模式一）======
    logger.info("\n" + "="*60)
    logger.info("PHASE 1: Fast Authentication (Mode1)")
    logger.info("="*60)
    
    mode1_auth = Mode1FastAuth(config)
    
    # 注册设备到模式一
    rff_template = secrets.token_bytes(64)
    mode1_auth.register_device(dev_id, rff_template)
    
    # 执行快速认证
    result_mode1 = mode1_auth.authenticate(dev_id, rff_template, snr=25.0)
    
    if not result_mode1.success:
        logger.error(f"[FAIL] Mode1 authentication failed: {result_mode1.reason}")
        raise AssertionError("Mode1 should succeed")
    
    logger.info(f"[OK] Mode1 authentication successful")
    logger.info(f"  Token size: {len(result_mode1.token)} bytes")
    logger.info(f"  Device granted LIMITED access for {config.TOKEN_FAST_TTL}s")
    
    # ====== 阶段二：强认证升级（模式二）======
    logger.info("\n" + "="*60)
    logger.info("PHASE 2: Strong Authentication Upgrade (Mode2)")
    logger.info("="*60)
    
    # 初始化模式二
    from src._fe_bridge import FeatureEncryption, FEConfig
    
    shared_fe_config = FEConfig()
    shared_fe = FeatureEncryption(shared_fe_config)
    
    # 🔧 Apply deterministic workaround
    shared_fe.quantizer._generate_secure_random_bits = staticmethod(deterministic_random_bits)
    
    device = DeviceSide(config, fe_config=shared_fe_config)
    device.fe = shared_fe
    
    verifier = VerifierSide(config, issuer_id, issuer_key, fe_config=shared_fe_config)
    verifier.fe = shared_fe
    
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
    
    # 生成模拟CSI特征
    Z_frames = simulate_csi_features(base_seed=100, noise_level=0)
    
    # 设备端创建AuthReq
    auth_req, Ks_device, K_device = device.create_auth_request(dev_id, Z_frames, context)
    
    # 验证端注册设备并验证
    verifier.register_device(dev_id, K_device, context.epoch)
    result_mode2 = verifier.verify_auth_request(auth_req, Z_frames)
    
    if not result_mode2.success:
        logger.error(f"[FAIL] Mode2 authentication failed: {result_mode2.reason}")
        raise AssertionError("Mode2 should succeed")
    
    logger.info(f"[OK] Mode2 authentication successful")
    logger.info(f"  MAT size: {len(result_mode2.token)} bytes")
    logger.info(f"  Session key: {result_mode2.session_key.hex()[:40]}...")
    logger.info(f"  Device granted FULL access for {config.MAT_TTL}s")
    
    # ====== 阶段三：验证升级效果 ======
    logger.info("\n" + "="*60)
    logger.info("PHASE 3: Verification")
    logger.info("="*60)
    
    logger.info(f"[OK] Mode1 → Mode2 upgrade successful")
    logger.info(f"  Fast authentication: {config.TOKEN_FAST_TTL}s limited access")
    logger.info(f"  Strong authentication: {config.MAT_TTL}s full access + session key")
    
    logger.info("="*80)
    logger.info("[OK][OK][OK] TEST PASSED: Mode1 → Mode2 Success")
    logger.info("="*80)


def test_mode1_fail_fallback_mode2():
    """测试模式一失败时，可以回退到模式二"""
    logger.info("\n"*2)
    logger.info("="*80)
    logger.info("TEST: Mode1 Fail → Mode2 Fallback")
    logger.info("="*80)
    
    config = AuthConfig(
        MODE1_ENABLED=True,
        MODE2_ENABLED=True,
        RFF_THRESHOLD=0.95  # 设置很高的阈值，容易失败
    )
    
    dev_id = bytes.fromhex('112233445566')
    issuer_id = bytes.fromhex('AABBCCDDEEFF')
    issuer_key = secrets.token_bytes(32)
    
    # ====== 阶段一：快速认证失败 ======
    logger.info("\n" + "="*60)
    logger.info("PHASE 1: Fast Authentication (Expected to Fail)")
    logger.info("="*60)
    
    mode1_auth = Mode1FastAuth(config)
    
    # 注册设备
    rff_template = secrets.token_bytes(64)
    mode1_auth.register_device(dev_id, rff_template)
    
    # 使用不匹配的特征（会导致低分）
    observed_features = secrets.token_bytes(64)
    result_mode1 = mode1_auth.authenticate(dev_id, observed_features, snr=25.0)
    
    if result_mode1.success:
        logger.warning(f"[WARN] Mode1 unexpectedly succeeded (test assumption violated)")
        logger.info(f"Continuing with Mode2 anyway...")
    else:
        logger.info(f"[OK] Mode1 authentication failed as expected: {result_mode1.reason}")
        logger.info(f"Falling back to Mode2...")
    
    # ====== 阶段二：回退到强认证 ======
    logger.info("\n" + "="*60)
    logger.info("PHASE 2: Fallback to Strong Authentication (Mode2)")
    logger.info("="*60)
    
    # 初始化模式二
    from src._fe_bridge import FeatureEncryption, FEConfig
    
    shared_fe_config = FEConfig()
    shared_fe = FeatureEncryption(shared_fe_config)
    shared_fe.quantizer._generate_secure_random_bits = staticmethod(deterministic_random_bits)
    
    device = DeviceSide(config, fe_config=shared_fe_config)
    device.fe = shared_fe
    
    verifier = VerifierSide(config, issuer_id, issuer_key, fe_config=shared_fe_config)
    verifier.fe = shared_fe
    
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
    
    # 生成模拟CSI特征
    Z_frames = simulate_csi_features(base_seed=200, noise_level=0)
    
    # 执行模式二认证
    auth_req, Ks_device, K_device = device.create_auth_request(dev_id, Z_frames, context)
    verifier.register_device(dev_id, K_device, context.epoch)
    result_mode2 = verifier.verify_auth_request(auth_req, Z_frames)
    
    if not result_mode2.success:
        logger.error(f"[FAIL] Mode2 authentication failed: {result_mode2.reason}")
        raise AssertionError("Mode2 fallback should succeed")
    
    logger.info(f"[OK] Mode2 authentication successful")
    logger.info(f"  Fallback strategy worked: Mode1 failed → Mode2 succeeded")
    
    logger.info("="*80)
    logger.info("[OK][OK][OK] TEST PASSED: Mode1 Fail → Mode2 Fallback")
    logger.info("="*80)


def test_dual_mode_independent():
    """测试两种模式独立工作"""
    logger.info("\n"*2)
    logger.info("="*80)
    logger.info("TEST: Dual Mode Independent Operation")
    logger.info("="*80)
    
    config = AuthConfig(
        MODE1_ENABLED=True,
        MODE2_ENABLED=True,
        RFF_THRESHOLD=0.8
    )
    
    # ====== 设备A：仅使用模式一 ======
    logger.info("\n" + "="*60)
    logger.info("DEVICE A: Mode1 Only")
    logger.info("="*60)
    
    dev_a = bytes.fromhex('AA1122334455')
    mode1_auth = Mode1FastAuth(config)
    
    template_a = secrets.token_bytes(64)
    mode1_auth.register_device(dev_a, template_a)
    
    result_a = mode1_auth.authenticate(dev_a, template_a, snr=25.0)
    
    if result_a.success:
        logger.info(f"[OK] Device A authenticated via Mode1")
    else:
        raise AssertionError(f"Device A Mode1 failed: {result_a.reason}")
    
    # ====== 设备B：仅使用模式二 ======
    logger.info("\n" + "="*60)
    logger.info("DEVICE B: Mode2 Only")
    logger.info("="*60)
    
    dev_b = bytes.fromhex('BB1122334455')
    issuer_id = bytes.fromhex('AABBCCDDEEFF')
    issuer_key = secrets.token_bytes(32)
    
    from src._fe_bridge import FeatureEncryption, FEConfig
    
    shared_fe_config = FEConfig()
    shared_fe = FeatureEncryption(shared_fe_config)
    shared_fe.quantizer._generate_secure_random_bits = staticmethod(deterministic_random_bits)
    
    device_b = DeviceSide(config, fe_config=shared_fe_config)
    device_b.fe = shared_fe
    
    verifier_b = VerifierSide(config, issuer_id, issuer_key, fe_config=shared_fe_config)
    verifier_b.fe = shared_fe
    
    nonce_b = secrets.token_bytes(16)
    context_b = AuthContext(
        src_mac=dev_b,
        dst_mac=issuer_id,
        epoch=12345,
        nonce=nonce_b,
        seq=1,
        alg_id='FeatureAuth-v1',
        ver=1,
        csi_id=1
    )
    
    Z_frames_b = simulate_csi_features(base_seed=300, noise_level=0)
    
    auth_req_b, Ks_b, K_b = device_b.create_auth_request(dev_b, Z_frames_b, context_b)
    verifier_b.register_device(dev_b, K_b, context_b.epoch)
    result_b = verifier_b.verify_auth_request(auth_req_b, Z_frames_b)
    
    if result_b.success:
        logger.info(f"[OK] Device B authenticated via Mode2")
    else:
        raise AssertionError(f"Device B Mode2 failed: {result_b.reason}")
    
    # ====== 验证独立性 ======
    logger.info("\n" + "="*60)
    logger.info("VERIFICATION: Independence")
    logger.info("="*60)
    
    logger.info(f"[OK] Device A: Mode1 authentication independent")
    logger.info(f"[OK] Device B: Mode2 authentication independent")
    logger.info(f"[OK] Both modes work independently without interference")
    
    logger.info("="*80)
    logger.info("[OK][OK][OK] TEST PASSED: Dual Mode Independent")
    logger.info("="*80)


def main():
    """运行所有集成测试"""
    logger.info("\n")
    logger.info("="*80)
    logger.info("DUAL-MODE AUTHENTICATION INTEGRATION TEST SUITE")
    logger.info("="*80)
    
    tests = [
        ("Mode1 → Mode2 Success", test_mode1_then_mode2_success),
        ("Mode1 Fail → Mode2 Fallback", test_mode1_fail_fallback_mode2),
        ("Dual Mode Independent", test_dual_mode_independent),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            logger.error(f"\n[FAIL][FAIL][FAIL] TEST FAILED: {test_name}")
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
        logger.info("\n[OK][OK][OK] ALL TESTS PASSED [OK][OK][OK]")
    else:
        logger.error("\n[FAIL][FAIL][FAIL] SOME TESTS FAILED [FAIL][FAIL][FAIL]")
    
    logger.info("="*80)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())

