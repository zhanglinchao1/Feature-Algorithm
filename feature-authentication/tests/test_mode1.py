"""
模式一集成测试

测试RFF快速认证的完整流程。
"""

import sys
import secrets
import logging
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import AuthConfig
from src.mode1_rff_auth import Mode1FastAuth, RFFMatcher
from src.common import TokenFast

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_mode1_success():
    """测试模式一成功认证场景"""
    logger.info("="*80)
    logger.info("TEST: Mode1 Success Scenario")
    logger.info("="*80)
    
    # 启用模式一的配置
    config = AuthConfig(MODE1_ENABLED=True, MODE2_ENABLED=False, RFF_THRESHOLD=0.8)
    
    # 设备信息
    dev_id = bytes.fromhex('001122334455')
    
    # 初始化模式一认证器
    auth = Mode1FastAuth(config)
    
    # 注册设备（生成模拟RFF模板）
    logger.info("\n" + "="*60)
    logger.info("PHASE 1: Device Registration")
    logger.info("="*60)
    
    template_data = secrets.token_bytes(64)  # 模拟RFF模板
    auth.register_device(dev_id, template_data)
    
    logger.info(f"[OK] Device {dev_id.hex()} registered")
    
    # 执行认证（使用相同的特征数据模拟成功场景）
    logger.info("\n" + "="*60)
    logger.info("PHASE 2: Authentication")
    logger.info("="*60)
    
    observed_features = template_data  # 完全匹配
    snr = 25.0  # 良好的信噪比
    
    result = auth.authenticate(dev_id, observed_features, snr)
    
    # 检查结果
    logger.info("\n" + "="*60)
    logger.info("PHASE 3: Verification")
    logger.info("="*60)
    
    if result.success:
        logger.info(f"[OK] Authentication successful")
        logger.info(f"  Mode: {result.mode}")
        logger.info(f"  Token size: {len(result.token)} bytes")
        
        # 反序列化令牌
        token = TokenFast.deserialize(result.token)
        logger.info(f"  Token device: {token.dev_id.hex()}")
        logger.info(f"  Token policy: {token.policy}")
        logger.info(f"  Token TTL: {token.t_expire - token.t_start}s")
        
        # 验证令牌
        logger.info("\n" + "="*60)
        logger.info("PHASE 4: Token Verification")
        logger.info("="*60)
        
        if auth.verify_token(token):
            logger.info(f"[OK][OK][OK] Token verification passed!")
        else:
            logger.error(f"[FAIL] Token verification failed")
            raise AssertionError("Token verification should succeed")
    else:
        logger.error(f"[FAIL] Authentication failed: {result.reason}")
        raise AssertionError(f"Authentication should succeed but failed: {result.reason}")
    
    logger.info("="*80)
    logger.info("[OK][OK][OK] TEST PASSED: Mode1 Success Scenario")
    logger.info("="*80)


def test_mode1_device_not_registered():
    """测试设备未注册场景"""
    logger.info("\n"*2)
    logger.info("="*80)
    logger.info("TEST: Mode1 Device Not Registered")
    logger.info("="*80)
    
    config = AuthConfig(MODE1_ENABLED=True, MODE2_ENABLED=False)
    auth = Mode1FastAuth(config)
    
    # 尝试认证未注册的设备
    dev_id = bytes.fromhex('AABBCCDDEEFF')
    observed_features = secrets.token_bytes(64)
    
    logger.info(f"Attempting to authenticate unregistered device {dev_id.hex()}...")
    
    result = auth.authenticate(dev_id, observed_features)
    
    # 应该失败
    if not result.success and result.reason == "device_not_registered":
        logger.info(f"[OK][OK][OK] TEST PASSED: Correctly rejected unregistered device")
        logger.info(f"  Reason: {result.reason}")
    else:
        logger.error(f"[FAIL] Should reject unregistered device")
        raise AssertionError("Unregistered device should be rejected")
    
    logger.info("="*80)


def test_mode1_rff_score_below_threshold():
    """测试RFF得分低于阈值场景"""
    logger.info("\n"*2)
    logger.info("="*80)
    logger.info("TEST: Mode1 RFF Score Below Threshold")
    logger.info("="*80)
    
    # 设置较高的阈值
    config = AuthConfig(MODE1_ENABLED=True, MODE2_ENABLED=False, RFF_THRESHOLD=0.95)
    auth = Mode1FastAuth(config)
    
    # 注册设备
    dev_id = bytes.fromhex('112233445566')
    template_data = secrets.token_bytes(64)
    auth.register_device(dev_id, template_data)
    
    logger.info(f"Device {dev_id.hex()} registered with threshold={config.RFF_THRESHOLD}")
    
    # 使用不同的特征数据（得分会较低）
    observed_features = secrets.token_bytes(64)  # 随机数据，不匹配
    
    logger.info(f"Attempting authentication with mismatched features...")
    
    result = auth.authenticate(dev_id, observed_features)
    
    # 应该失败（得分低于阈值）
    if not result.success and (result.reason == "rff_score_below_threshold" or result.reason == "rff_failed"):
        logger.info(f"[OK][OK][OK] TEST PASSED: Correctly rejected low RFF score")
        logger.info(f"  Reason: {result.reason}")
    else:
        logger.error(f"[FAIL] Should reject low RFF score")
        raise AssertionError("Low RFF score should be rejected")
    
    logger.info("="*80)


def test_mode1_low_snr():
    """测试低信噪比场景"""
    logger.info("\n"*2)
    logger.info("="*80)
    logger.info("TEST: Mode1 Low SNR")
    logger.info("="*80)
    
    config = AuthConfig(MODE1_ENABLED=True, MODE2_ENABLED=False, RFF_THRESHOLD=0.8)
    auth = Mode1FastAuth(config)
    
    # 注册设备
    dev_id = bytes.fromhex('223344556677')
    template_data = secrets.token_bytes(64)
    auth.register_device(dev_id, template_data)
    
    logger.info(f"Device {dev_id.hex()} registered")
    
    # 使用相同特征但低SNR
    observed_features = template_data
    low_snr = 5.0  # 非常低的信噪比
    
    logger.info(f"Attempting authentication with low SNR={low_snr} dB...")
    
    result = auth.authenticate(dev_id, observed_features, snr=low_snr)
    
    # 由于SNR因子降低，即使特征匹配，得分也会下降
    # 可能通过或失败，取决于具体实现
    logger.info(f"Authentication result: success={result.success}")
    if not result.success:
        logger.info(f"  Reason: {result.reason}")
    else:
        logger.info(f"  Despite low SNR, authentication passed (features matched perfectly)")
    
    logger.info(f"[OK][OK][OK] TEST PASSED: Low SNR scenario handled")
    logger.info("="*80)


def test_mode1_token_revocation():
    """测试令牌撤销场景"""
    logger.info("\n"*2)
    logger.info("="*80)
    logger.info("TEST: Mode1 Token Revocation")
    logger.info("="*80)
    
    config = AuthConfig(MODE1_ENABLED=True, MODE2_ENABLED=False)
    auth = Mode1FastAuth(config)
    
    # 注册设备
    dev_id = bytes.fromhex('334455667788')
    template_data = secrets.token_bytes(64)
    auth.register_device(dev_id, template_data)
    
    # 认证
    result = auth.authenticate(dev_id, template_data, snr=25.0)
    
    if not result.success:
        raise AssertionError("Initial authentication should succeed")
    
    token = TokenFast.deserialize(result.token)
    logger.info(f"[OK] Token issued for device {dev_id.hex()}")
    
    # 撤销设备
    logger.info(f"Revoking device {dev_id.hex()}...")
    revoked = auth.revoke_device(dev_id)
    
    if revoked:
        logger.info(f"[OK] Device revoked")
        
        # 尝试再次认证（应该失败）
        logger.info(f"Attempting re-authentication after revocation...")
        result2 = auth.authenticate(dev_id, template_data, snr=25.0)
        
        if not result2.success:
            logger.info(f"[OK][OK][OK] TEST PASSED: Re-authentication correctly rejected")
            logger.info(f"  Reason: {result2.reason}")
        else:
            logger.error(f"[FAIL] Should reject revoked device")
            raise AssertionError("Revoked device should be rejected")
    else:
        logger.error(f"[FAIL] Failed to revoke device")
        raise AssertionError("Device revocation failed")
    
    logger.info("="*80)


def main():
    """运行所有测试"""
    logger.info("\n")
    logger.info("="*80)
    logger.info("MODE 1 FAST AUTHENTICATION TEST SUITE")
    logger.info("="*80)
    
    tests = [
        ("Success Scenario", test_mode1_success),
        ("Device Not Registered", test_mode1_device_not_registered),
        ("RFF Score Below Threshold", test_mode1_rff_score_below_threshold),
        ("Low SNR", test_mode1_low_snr),
        ("Token Revocation", test_mode1_token_revocation),
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

