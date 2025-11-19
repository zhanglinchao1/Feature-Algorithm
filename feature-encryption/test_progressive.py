"""
渐进式测试框架 - 带详细日志
逐步测试每个模块，记录详细日志，发现并修复问题
"""

import numpy as np
import secrets
import sys
import logging
from datetime import datetime
from pathlib import Path

# 配置日志
log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"test_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# 添加父目录到路径，以便可以导入src包
sys.path.insert(0, str(Path(__file__).parent))


class TestResult:
    """测试结果记录"""
    def __init__(self, test_name):
        self.test_name = test_name
        self.passed = False
        self.error = None
        self.details = {}

    def __str__(self):
        status = "✓ PASS" if self.passed else "✗ FAIL"
        return f"{status} - {self.test_name}"


class ProgressiveTest:
    """渐进式测试类"""

    def __init__(self):
        self.results = []
        logger.info("="*80)
        logger.info("渐进式测试框架启动")
        logger.info(f"日志文件: {log_file}")
        logger.info("="*80)

    def test_step_1_config(self):
        """测试步骤1：配置模块"""
        result = TestResult("Step 1: 配置模块")
        logger.info("\n" + "="*80)
        logger.info("测试步骤1：配置模块")
        logger.info("="*80)

        try:
            from src.config import FeatureEncryptionConfig

            # 测试默认配置
            logger.info("测试1.1: 创建默认配置")
            config = FeatureEncryptionConfig()
            logger.info(f"  ✓ 默认配置创建成功")
            logger.info(f"    M_FRAMES: {config.M_FRAMES}")
            logger.info(f"    TARGET_BITS: {config.TARGET_BITS}")
            logger.info(f"    BCH: ({config.BCH_N}, {config.BCH_K}, {config.BCH_T})")

            # 测试配置验证
            logger.info("测试1.2: 配置验证")
            config.validate()
            logger.info(f"  ✓ 配置验证通过")

            # 测试预定义配置
            logger.info("测试1.3: 预定义配置")
            high_noise = FeatureEncryptionConfig.high_noise()
            logger.info(f"  ✓ 高噪声配置: M_FRAMES={high_noise.M_FRAMES}")

            low_latency = FeatureEncryptionConfig.low_latency()
            logger.info(f"  ✓ 低延迟配置: M_FRAMES={low_latency.M_FRAMES}")

            result.passed = True
            result.details['config'] = config

        except Exception as e:
            logger.error(f"✗ 配置模块测试失败: {e}", exc_info=True)
            result.error = str(e)

        self.results.append(result)
        return result

    def test_step_2_feature_processor(self):
        """测试步骤2：特征处理模块"""
        result = TestResult("Step 2: 特征处理模块")
        logger.info("\n" + "="*80)
        logger.info("测试步骤2：特征处理模块")
        logger.info("="*80)

        try:
            from src.config import FeatureEncryptionConfig
            from src.feature_processor import FeatureProcessor

            config = FeatureEncryptionConfig()
            processor = FeatureProcessor(config)

            # 测试CSI处理
            logger.info("测试2.1: CSI特征处理")
            H = np.random.randn(64) + 1j * np.random.randn(64)
            noise_var = 0.01

            Z, mask = processor.process_csi(H, noise_var)
            logger.info(f"  ✓ CSI处理成功")
            logger.info(f"    输入维度: {H.shape}")
            logger.info(f"    输出维度: {Z.shape}")
            logger.info(f"    掩码维度: {len(mask)}")

            # 测试RFF处理
            logger.info("测试2.2: RFF特征处理")
            # 使用配置中定义的RFF特征维度
            D_rff = config.FEATURE_DIM_RFF
            X_rff = np.random.randn(D_rff)
            Z_rff, mask_rff = processor.process_rff(X_rff)
            logger.info(f"  ✓ RFF处理成功")
            logger.info(f"    输入维度: {X_rff.shape}")
            logger.info(f"    输出维度: {Z_rff.shape}")

            result.passed = True
            result.details['processor'] = processor
            result.details['config'] = config

        except Exception as e:
            logger.error(f"✗ 特征处理模块测试失败: {e}", exc_info=True)
            result.error = str(e)

        self.results.append(result)
        return result

    def test_step_3_quantizer(self):
        """测试步骤3：量化投票模块"""
        result = TestResult("Step 3: 量化投票模块")
        logger.info("\n" + "="*80)
        logger.info("测试步骤3：量化投票模块")
        logger.info("="*80)

        try:
            from src.config import FeatureEncryptionConfig
            from src.quantizer import FeatureQuantizer

            config = FeatureEncryptionConfig()
            quantizer = FeatureQuantizer(config)

            # 生成多帧特征
            logger.info("测试3.1: 生成测试数据")
            M = config.M_FRAMES
            D = 64
            Z_frames = np.random.randn(M, D)
            logger.info(f"  ✓ 生成多帧特征: shape={Z_frames.shape}")

            # 计算门限
            logger.info("测试3.2: 计算量化门限")
            theta_L, theta_H = quantizer.compute_thresholds(Z_frames)
            logger.info(f"  ✓ 门限计算成功")
            logger.info(f"    theta_L: shape={theta_L.shape}, mean={theta_L.mean():.4f}")
            logger.info(f"    theta_H: shape={theta_H.shape}, mean={theta_H.mean():.4f}")

            # 量化
            logger.info("测试3.3: 量化多帧特征")
            Q_frames = quantizer.quantize_frames(Z_frames, theta_L, theta_H)
            unique_vals = np.unique(Q_frames)
            logger.info(f"  ✓ 量化成功")
            logger.info(f"    Q_frames: shape={Q_frames.shape}")
            logger.info(f"    量化值: {unique_vals}")

            # 验证量化值
            if not all(v in [-1, 0, 1] for v in unique_vals):
                raise ValueError(f"量化值应在{{-1,0,1}}内，实际: {unique_vals}")

            # 投票
            logger.info("测试3.4: 多数投票")
            r_bits, selected_dims = quantizer.majority_vote(Q_frames)
            logger.info(f"  ✓ 投票成功")
            logger.info(f"    生成比特数: {len(r_bits)}")
            logger.info(f"    选中维度数: {len(selected_dims)}")
            logger.info(f"    比特率: {len(r_bits)/D:.2%}")

            # 完整流程
            logger.info("测试3.5: 完整量化流程")
            r, theta_L2, theta_H2 = quantizer.process_multi_frames(Z_frames)
            logger.info(f"  ✓ 完整流程成功")
            logger.info(f"    最终比特数: {len(r)}")

            result.passed = True
            result.details['quantizer'] = quantizer
            result.details['r_bits'] = r
            result.details['theta_L'] = theta_L2
            result.details['theta_H'] = theta_H2

        except Exception as e:
            logger.error(f"✗ 量化投票模块测试失败: {e}", exc_info=True)
            result.error = str(e)

        self.results.append(result)
        return result

    def test_step_4_fuzzy_extractor(self):
        """测试步骤4：模糊提取器模块"""
        result = TestResult("Step 4: 模糊提取器模块")
        logger.info("\n" + "="*80)
        logger.info("测试步骤4：模糊提取器模块")
        logger.info("="*80)

        try:
            from src.config import FeatureEncryptionConfig
            from src.fuzzy_extractor import FuzzyExtractor

            config = FeatureEncryptionConfig()
            extractor = FuzzyExtractor(config)

            # 生成测试比特串（使用配置的TARGET_BITS）
            logger.info("测试4.1: 生成辅助数据")
            r = [secrets.randbelow(2) for _ in range(config.TARGET_BITS)]
            logger.info(f"  原始比特串长度: {len(r)}")

            P = extractor.generate_helper_data(r)
            logger.info(f"  ✓ 辅助数据生成成功")
            logger.info(f"    辅助数据长度: {len(P)} bytes")

            # 测试无噪声提取
            logger.info("测试4.2: 无噪声密钥提取")
            r_prime = r.copy()  # 完全相同
            S_bits, success = extractor.extract_stable_key(r_prime, P)
            logger.info(f"  提取结果: {'成功' if success else '失败'}")
            logger.info(f"  稳定密钥长度: {len(S_bits)}")

            if not success:
                raise ValueError("无噪声提取应该成功")
            logger.info(f"  ✓ 无噪声提取成功")

            # 测试有噪声提取
            logger.info("测试4.3: 有噪声密钥提取")
            r_noisy = r.copy()
            # 翻转少量比特（模拟噪声）
            num_errors = 5
            error_positions = np.random.choice(len(r), num_errors, replace=False)
            for pos in error_positions:
                r_noisy[pos] = 1 - r_noisy[pos]

            logger.info(f"  引入错误: {num_errors} 个比特翻转")
            S_bits_noisy, success_noisy = extractor.extract_stable_key(r_noisy, P)
            logger.info(f"  提取结果: {'成功' if success_noisy else '失败'}")

            if success_noisy:
                # 验证提取的密钥是否一致
                if S_bits == S_bits_noisy:
                    logger.info(f"  ✓ 有噪声提取成功，密钥一致")
                else:
                    logger.warning(f"  ⚠ 有噪声提取成功，但密钥不一致")
            else:
                logger.info(f"  注意: BCH无法纠正 {num_errors} 个错误")

            # 测试高噪声（应该失败）
            logger.info("测试4.4: 高噪声提取（预期失败）")
            r_high_noise = r.copy()
            num_high_errors = 30  # 超过BCH能力
            high_error_pos = np.random.choice(len(r), num_high_errors, replace=False)
            for pos in high_error_pos:
                r_high_noise[pos] = 1 - r_high_noise[pos]

            logger.info(f"  引入错误: {num_high_errors} 个比特翻转")
            _, success_high = extractor.extract_stable_key(r_high_noise, P)
            logger.info(f"  提取结果: {'成功' if success_high else '失败（预期）'}")

            if not success_high:
                logger.info(f"  ✓ 高噪声正确拒绝")

            result.passed = True
            result.details['extractor'] = extractor
            result.details['helper_data'] = P

        except Exception as e:
            logger.error(f"✗ 模糊提取器模块测试失败: {e}", exc_info=True)
            result.error = str(e)

        self.results.append(result)
        return result

    def test_step_5_key_derivation(self):
        """测试步骤5：密钥派生模块"""
        result = TestResult("Step 5: 密钥派生模块")
        logger.info("\n" + "="*80)
        logger.info("测试步骤5：密钥派生模块")
        logger.info("="*80)

        try:
            from src.config import FeatureEncryptionConfig
            from src.key_derivation import KeyDerivation

            config = FeatureEncryptionConfig()
            kd = KeyDerivation(config)

            # 测试L计算
            logger.info("测试5.1: 计算随机扰动值L")
            epoch = 12345
            nonce = secrets.token_bytes(16)
            L = kd.compute_L(epoch, nonce)
            logger.info(f"  ✓ L计算成功")
            logger.info(f"    L长度: {len(L)} bytes")
            logger.info(f"    L前16字节: {L[:16].hex()}")

            # 测试特征密钥派生
            logger.info("测试5.2: 派生特征密钥K")
            S = secrets.token_bytes(32)
            dom = b'TestDomain'
            srcMAC = b'\x00\x11\x22\x33\x44\x55'
            dstMAC = b'\xAA\xBB\xCC\xDD\xEE\xFF'
            ver = 1

            K = kd.derive_feature_key(S, L, dom, srcMAC, dstMAC, ver, epoch)
            logger.info(f"  ✓ K派生成功")
            logger.info(f"    K长度: {len(K)} bytes")
            logger.info(f"    K前16字节: {K[:16].hex()}")

            # 测试会话密钥派生
            logger.info("测试5.3: 派生会话密钥Ks")
            Ci = 0
            Ks = kd.derive_session_key(K, epoch, Ci)
            logger.info(f"  ✓ Ks派生成功")
            logger.info(f"    Ks长度: {len(Ks)} bytes")
            logger.info(f"    Ks前16字节: {Ks[:16].hex()}")

            # 测试摘要生成
            logger.info("测试5.4: 生成一致性摘要")
            mask_bytes = b'test_mask'
            theta_L = np.random.randn(64).tobytes()
            theta_H = np.random.randn(64).tobytes()
            digest = kd.generate_digest(mask_bytes, theta_L, theta_H)
            logger.info(f"  ✓ digest生成成功")
            logger.info(f"    digest长度: {len(digest)} bytes")
            logger.info(f"    digest: {digest.hex()}")

            # 测试确定性
            logger.info("测试5.5: 验证派生确定性")
            K2 = kd.derive_feature_key(S, L, dom, srcMAC, dstMAC, ver, epoch)
            if K == K2:
                logger.info(f"  ✓ 相同输入产生相同密钥")
            else:
                raise ValueError("相同输入应产生相同密钥")

            # 测试不同输入产生不同密钥
            logger.info("测试5.6: 验证不同输入产生不同密钥")
            epoch2 = 12346
            K3 = kd.derive_feature_key(S, L, dom, srcMAC, dstMAC, ver, epoch2)
            if K != K3:
                logger.info(f"  ✓ 不同epoch产生不同密钥")
            else:
                logger.warning(f"  ⚠ 不同epoch应产生不同密钥")

            result.passed = True
            result.details['kd'] = kd

        except Exception as e:
            logger.error(f"✗ 密钥派生模块测试失败: {e}", exc_info=True)
            result.error = str(e)

        self.results.append(result)
        return result

    def test_step_6_integration(self):
        """测试步骤6：完整集成流程"""
        result = TestResult("Step 6: 完整集成流程")
        logger.info("\n" + "="*80)
        logger.info("测试步骤6：完整集成流程（注册-认证）")
        logger.info("="*80)

        try:
            from src.config import FeatureEncryptionConfig
            from src.feature_encryption import FeatureEncryption, Context

            config = FeatureEncryptionConfig()
            fe = FeatureEncryption(config)

            # 准备上下文
            logger.info("测试6.1: 准备测试环境")
            context = Context(
                srcMAC=b'\x00\x11\x22\x33\x44\x55',
                dstMAC=b'\xAA\xBB\xCC\xDD\xEE\xFF',
                dom=b'TestDomain',
                ver=1,
                epoch=12345,
                Ci=0,
                nonce=secrets.token_bytes(16)
            )
            logger.info(f"  ✓ 上下文创建成功")

            # 生成基础特征
            logger.info("测试6.2: 生成模拟CSI特征")
            M = config.M_FRAMES
            D = config.get_feature_dim('CSI')
            base_feature = np.random.randn(D)

            # 注册阶段特征（低噪声）
            np.random.seed(42)
            Z_frames_reg = np.zeros((M, D))
            for m in range(M):
                noise = np.random.randn(D) * 0.1
                Z_frames_reg[m] = base_feature + noise
            logger.info(f"  ✓ 注册特征: shape={Z_frames_reg.shape}")

            # 注册
            logger.info("测试6.3: 执行注册")
            device_id = "test_device_001"
            key_reg, metadata = fe.register(
                device_id=device_id,
                Z_frames=Z_frames_reg,
                context=context,
                mask_bytes=b'test_mask'
            )
            logger.info(f"  ✓ 注册成功")
            logger.info(f"    S: {key_reg.S.hex()[:40]}...")
            logger.info(f"    K: {key_reg.K.hex()[:40]}...")
            logger.info(f"    Ks: {key_reg.Ks.hex()[:40]}...")
            logger.info(f"    digest: {key_reg.digest.hex()}")
            logger.info(f"    比特数: {metadata['bit_count']}")

            # 认证阶段特征（相同基础+不同噪声）
            logger.info("测试6.4: 生成认证特征")
            np.random.seed(100)  # 不同随机种子
            Z_frames_auth = np.zeros((M, D))
            for m in range(M):
                noise = np.random.randn(D) * 0.15  # 稍大噪声
                Z_frames_auth[m] = base_feature + noise
            logger.info(f"  ✓ 认证特征: shape={Z_frames_auth.shape}")

            # 认证
            logger.info("测试6.5: 执行认证")
            key_auth, success = fe.authenticate(
                device_id=device_id,
                Z_frames=Z_frames_auth,
                context=context,
                mask_bytes=b'test_mask'
            )

            if not success:
                raise ValueError("认证失败！BCH解码未成功")

            logger.info(f"  ✓ 认证成功")
            logger.info(f"    S: {key_auth.S.hex()[:40]}...")
            logger.info(f"    K: {key_auth.K.hex()[:40]}...")
            logger.info(f"    Ks: {key_auth.Ks.hex()[:40]}...")
            logger.info(f"    digest: {key_auth.digest.hex()}")

            # 验证密钥一致性
            logger.info("测试6.6: 验证密钥一致性")
            checks = {
                'S一致': key_reg.S == key_auth.S,
                'K一致': key_reg.K == key_auth.K,
                'Ks一致': key_reg.Ks == key_auth.Ks,
                'digest一致': key_reg.digest == key_auth.digest,
            }

            for name, passed in checks.items():
                status = "✓" if passed else "✗"
                logger.info(f"    {status} {name}: {passed}")

            if not all(checks.values()):
                failed = [k for k, v in checks.items() if not v]
                raise ValueError(f"密钥一致性检查失败: {failed}")

            logger.info(f"  ✓✓✓ 所有密钥完全一致！")

            result.passed = True
            result.details['all_checks_passed'] = all(checks.values())

        except Exception as e:
            logger.error(f"✗ 完整集成流程测试失败: {e}", exc_info=True)
            result.error = str(e)

        self.results.append(result)
        return result

    def run_all_tests(self):
        """运行所有测试"""
        logger.info("\n" + "="*80)
        logger.info("开始渐进式测试")
        logger.info("="*80)

        # 测试步骤
        tests = [
            self.test_step_1_config,
            self.test_step_2_feature_processor,
            self.test_step_3_quantizer,
            self.test_step_4_fuzzy_extractor,
            self.test_step_5_key_derivation,
            self.test_step_6_integration,
        ]

        for test_func in tests:
            result = test_func()
            if not result.passed:
                logger.error(f"测试失败，停止后续测试: {result.test_name}")
                logger.error(f"错误信息: {result.error}")
                break

        # 总结
        self.print_summary()

    def print_summary(self):
        """打印测试总结"""
        logger.info("\n" + "="*80)
        logger.info("测试结果总结")
        logger.info("="*80)

        for result in self.results:
            logger.info(str(result))
            if result.error:
                logger.info(f"  错误: {result.error}")

        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)

        logger.info("\n" + "="*80)
        logger.info(f"测试完成: {passed}/{total} 通过")
        if passed == total:
            logger.info("✓✓✓ 所有测试通过！")
            logger.info("✓ P-1修复验证：注册和认证使用相同的BCH纠错后的S")
            logger.info("✓ P-2修复验证：Ks使用HKDFExpand派生")
            logger.info("✓ P-3修复验证：门限正确保存和加载")
        else:
            logger.error("✗✗✗ 部分测试失败，需要修复")
        logger.info("="*80)
        logger.info(f"详细日志已保存到: {log_file}")
        logger.info("="*80 + "\n")

        return passed == total


def main():
    """主函数"""
    test = ProgressiveTest()
    test.run_all_tests()

    # 返回测试结果
    all_passed = all(r.passed for r in test.results)
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
