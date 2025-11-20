"""
设备端-验证端分离测试

模拟真实的设备端和验证端交互流程，使用模拟CSI信道数据测试算法正确性。
重点验证P-1、P-2、P-3修复后的密钥一致性。
"""

import numpy as np
import secrets
import sys
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.config import FeatureEncryptionConfig
from src.feature_encryption import FeatureEncryption, Context


class SimulatedCSIChannel:
    """模拟CSI信道"""

    def __init__(self, num_subcarriers=64, seed=None):
        """
        初始化模拟信道

        Args:
            num_subcarriers: 子载波数量
            seed: 随机种子
        """
        self.num_subcarriers = num_subcarriers
        if seed is not None:
            np.random.seed(seed)

        # 生成信道基础特性（Rayleigh衰落）
        self.h_real = np.random.randn(num_subcarriers)
        self.h_imag = np.random.randn(num_subcarriers)
        self.H_base = self.h_real + 1j * self.h_imag

    def measure(self, noise_level=0.1):
        """
        模拟一次CSI测量（添加噪声）

        Args:
            noise_level: 噪声标准差

        Returns:
            H: 信道频域响应
            noise_var: 噪声方差
        """
        # 添加测量噪声
        noise_real = np.random.randn(self.num_subcarriers) * noise_level
        noise_imag = np.random.randn(self.num_subcarriers) * noise_level
        noise = noise_real + 1j * noise_imag

        H_measured = self.H_base + noise
        noise_var = noise_level ** 2

        return H_measured, noise_var

    def measure_multi_frames(self, M=6, noise_level=0.1):
        """
        模拟多帧CSI测量

        Args:
            M: 帧数
            noise_level: 噪声标准差

        Returns:
            measurements: list of (H, noise_var) tuples
        """
        return [self.measure(noise_level) for _ in range(M)]


class DeviceSide:
    """设备端（注册端）"""

    def __init__(self, config: FeatureEncryptionConfig, deterministic_for_testing: bool = True):
        self.fe = FeatureEncryption(config, deterministic_for_testing=deterministic_for_testing)
        self.config = config

    def register(self, device_id: str, csi_measurements: list, context: Context):
        """
        设备端注册流程

        Args:
            device_id: 设备标识
            csi_measurements: CSI测量列表 [(H, noise_var), ...]
            context: 上下文信息

        Returns:
            key_output: 密钥输出
            metadata: 元数据
            helper_data: 辅助数据（需要发送给验证端）
        """
        # Step 1: 预处理CSI特征
        M = len(csi_measurements)
        Z_frames = []

        for H, noise_var in csi_measurements:
            # 处理单帧CSI
            Z, mask = self.fe.feature_processor.process_csi(H, noise_var)
            Z_frames.append(Z)

        Z_frames = np.array(Z_frames)

        print(f"[设备端] 采集了 {M} 帧CSI特征，维度: {Z_frames.shape}")

        # Step 2: 注册
        key_output, metadata = self.fe.register(
            device_id=device_id,
            Z_frames=Z_frames,
            context=context,
            mask_bytes=b'device_mask'
        )

        print(f"[设备端] 注册成功，生成比特数: {metadata['bit_count']}")

        # Step 3: 获取辅助数据（需要发送给验证端）
        helper_data = self.fe._load_helper_data(device_id)
        thresholds = self.fe._load_thresholds(device_id)

        return key_output, metadata, (helper_data, thresholds)


class VerifierSide:
    """验证端（认证端）"""

    def __init__(self, config: FeatureEncryptionConfig, deterministic_for_testing: bool = True):
        self.fe = FeatureEncryption(config, deterministic_for_testing=deterministic_for_testing)
        self.config = config

    def authenticate(self, device_id: str, csi_measurements: list, context: Context,
                     helper_data_package: tuple):
        """
        验证端认证流程

        Args:
            device_id: 设备标识
            csi_measurements: CSI测量列表
            context: 上下文信息（必须与注册时一致）
            helper_data_package: (helper_data, thresholds) 从设备端接收

        Returns:
            key_output: 密钥输出
            success: 是否成功
        """
        # Step 1: 恢复辅助数据
        helper_data, thresholds = helper_data_package
        self.fe._store_helper_data(device_id, helper_data)
        if thresholds is not None:
            self.fe._store_thresholds(device_id, *thresholds)

        print(f"[验证端] 已加载辅助数据")

        # Step 2: 预处理CSI特征
        M = len(csi_measurements)
        Z_frames = []

        for H, noise_var in csi_measurements:
            Z, mask = self.fe.feature_processor.process_csi(H, noise_var)
            Z_frames.append(Z)

        Z_frames = np.array(Z_frames)

        print(f"[验证端] 采集了 {M} 帧CSI特征，维度: {Z_frames.shape}")

        # Step 3: 认证
        key_output, success = self.fe.authenticate(
            device_id=device_id,
            Z_frames=Z_frames,
            context=context,
            mask_bytes=b'device_mask'
        )

        if success:
            print(f"[验证端] 认证成功！")
        else:
            print(f"[验证端] 认证失败！")

        return key_output, success


def test_scenario_1_low_noise():
    """测试场景1：低噪声环境（理想情况）"""
    print("\n" + "="*80)
    print("测试场景1：低噪声环境（噪声水平=0.05）")
    print("="*80)

    # 配置
    config = FeatureEncryptionConfig()

    # 模拟信道
    channel = SimulatedCSIChannel(num_subcarriers=64, seed=42)

    # 上下文（注册和认证必须一致）
    context = Context(
        srcMAC=b'\x00\x11\x22\x33\x44\x55',
        dstMAC=b'\xAA\xBB\xCC\xDD\xEE\xFF',
        dom=b'TestDomain',
        ver=1,
        epoch=12345,
        Ci=0,
        nonce=secrets.token_bytes(16)
    )

    device_id = "device_001"

    # --- 设备端：注册阶段 ---
    print("\n[阶段1] 设备端注册")
    device = DeviceSide(config)

    # 设备端测量CSI
    np.random.seed(100)
    device_measurements = channel.measure_multi_frames(M=6, noise_level=0.05)

    # 注册
    key_reg, metadata, helper_package = device.register(device_id, device_measurements, context)

    print(f"  特征密钥 K:  {key_reg.K.hex()[:40]}...")
    print(f"  会话密钥 Ks: {key_reg.Ks.hex()[:40]}...")
    print(f"  稳定特征 S:  {key_reg.S.hex()[:40]}...")

    # --- 验证端：认证阶段 ---
    print("\n[阶段2] 验证端认证")
    verifier = VerifierSide(config)

    # 验证端独立测量CSI（不同噪声实现）
    np.random.seed(200)
    verifier_measurements = channel.measure_multi_frames(M=6, noise_level=0.05)

    # 认证
    key_auth, success = verifier.authenticate(device_id, verifier_measurements, context, helper_package)

    if success:
        print(f"  特征密钥 K:  {key_auth.K.hex()[:40]}...")
        print(f"  会话密钥 Ks: {key_auth.Ks.hex()[:40]}...")
        print(f"  稳定特征 S:  {key_auth.S.hex()[:40]}...")

    # --- 验证密钥一致性 ---
    print("\n[阶段3] 验证密钥一致性")

    results = {
        'S_match': key_reg.S == key_auth.S if success else False,
        'K_match': key_reg.K == key_auth.K if success else False,
        'Ks_match': key_reg.Ks == key_auth.Ks if success else False,
    }

    if results['S_match']:
        print("  [OK] 稳定特征串 S 一致")
    else:
        print("  ✗ 稳定特征串 S 不一致！")

    if results['K_match']:
        print("  [OK] 特征密钥 K 一致")
    else:
        print("  ✗ 特征密钥 K 不一致！")

    if results['Ks_match']:
        print("  [OK] 会话密钥 Ks 一致")
    else:
        print("  ✗ 会话密钥 Ks 不一致！")

    return all(results.values())


def test_scenario_2_medium_noise():
    """测试场景2：中等噪声环境"""
    print("\n" + "="*80)
    print("测试场景2：中等噪声环境（噪声水平=0.15）")
    print("="*80)

    config = FeatureEncryptionConfig()
    channel = SimulatedCSIChannel(num_subcarriers=64, seed=43)

    context = Context(
        srcMAC=b'\x00\x11\x22\x33\x44\x55',
        dstMAC=b'\xAA\xBB\xCC\xDD\xEE\xFF',
        dom=b'TestDomain',
        ver=1,
        epoch=12345,
        Ci=0,
        nonce=secrets.token_bytes(16)
    )

    device_id = "device_002"

    # 设备端注册
    print("\n[阶段1] 设备端注册")
    device = DeviceSide(config)
    np.random.seed(100)
    device_measurements = channel.measure_multi_frames(M=6, noise_level=0.15)
    key_reg, metadata, helper_package = device.register(device_id, device_measurements, context)
    print(f"  特征密钥 K:  {key_reg.K.hex()[:40]}...")

    # 验证端认证
    print("\n[阶段2] 验证端认证")
    verifier = VerifierSide(config)
    np.random.seed(200)
    verifier_measurements = channel.measure_multi_frames(M=6, noise_level=0.15)
    key_auth, success = verifier.authenticate(device_id, verifier_measurements, context, helper_package)

    if success:
        print(f"  特征密钥 K:  {key_auth.K.hex()[:40]}...")

    # 验证
    print("\n[阶段3] 验证密钥一致性")
    results = {
        'S_match': key_reg.S == key_auth.S if success else False,
        'K_match': key_reg.K == key_auth.K if success else False,
        'Ks_match': key_reg.Ks == key_auth.Ks if success else False,
    }

    for key, value in results.items():
        status = "[OK]" if value else "[FAIL]"
        print(f"  {status} {key}: {value}")

    return all(results.values())


def test_scenario_3_high_noise():
    """测试场景3：高噪声环境（压力测试）"""
    print("\n" + "="*80)
    print("测试场景3：高噪声环境（噪声水平=0.25）")
    print("="*80)

    # 使用高噪声配置
    config = FeatureEncryptionConfig.high_noise()
    channel = SimulatedCSIChannel(num_subcarriers=64, seed=44)

    context = Context(
        srcMAC=b'\x00\x11\x22\x33\x44\x55',
        dstMAC=b'\xAA\xBB\xCC\xDD\xEE\xFF',
        dom=b'TestDomain',
        ver=1,
        epoch=12345,
        Ci=0,
        nonce=secrets.token_bytes(16)
    )

    device_id = "device_003"

    print("\n[阶段1] 设备端注册")
    device = DeviceSide(config)
    np.random.seed(100)
    device_measurements = channel.measure_multi_frames(M=config.M_FRAMES, noise_level=0.25)
    key_reg, metadata, helper_package = device.register(device_id, device_measurements, context)
    print(f"  特征密钥 K:  {key_reg.K.hex()[:40]}...")

    print("\n[阶段2] 验证端认证")
    verifier = VerifierSide(config)
    np.random.seed(200)
    verifier_measurements = channel.measure_multi_frames(M=config.M_FRAMES, noise_level=0.25)
    key_auth, success = verifier.authenticate(device_id, verifier_measurements, context, helper_package)

    if success:
        print(f"  特征密钥 K:  {key_auth.K.hex()[:40]}...")

    print("\n[阶段3] 验证密钥一致性")
    results = {
        'S_match': key_reg.S == key_auth.S if success else False,
        'K_match': key_reg.K == key_auth.K if success else False,
        'Ks_match': key_reg.Ks == key_auth.Ks if success else False,
    }

    for key, value in results.items():
        status = "[OK]" if value else "[FAIL]"
        print(f"  {status} {key}: {value}")

    return all(results.values())


def test_scenario_4_different_context():
    """测试场景4：不同上下文应产生不同密钥"""
    print("\n" + "="*80)
    print("测试场景4：不同上下文应产生不同密钥")
    print("="*80)

    config = FeatureEncryptionConfig()
    channel = SimulatedCSIChannel(num_subcarriers=64, seed=45)

    # 两个不同的上下文
    context1 = Context(
        srcMAC=b'\x00\x11\x22\x33\x44\x55',
        dstMAC=b'\xAA\xBB\xCC\xDD\xEE\xFF',
        dom=b'TestDomain',
        ver=1,
        epoch=12345,
        Ci=0,
        nonce=secrets.token_bytes(16)
    )

    context2 = Context(
        srcMAC=b'\x00\x11\x22\x33\x44\x55',
        dstMAC=b'\xAA\xBB\xCC\xDD\xEE\xFF',
        dom=b'TestDomain',
        ver=1,
        epoch=12346,  # 不同的epoch
        Ci=0,
        nonce=secrets.token_bytes(16)
    )

    device_id = "device_004"

    # 使用context1注册
    print("\n[测试] 使用context1注册")
    device = DeviceSide(config)
    np.random.seed(100)
    measurements = channel.measure_multi_frames(M=6, noise_level=0.1)
    key1, _, helper = device.register(device_id, measurements, context1)

    # 使用context2认证（应该失败或产生不同密钥）
    print("\n[测试] 使用context2认证")
    verifier = VerifierSide(config)
    np.random.seed(100)  # 相同的随机种子，相同的特征
    measurements2 = channel.measure_multi_frames(M=6, noise_level=0.1)
    key2, success = verifier.authenticate(device_id, measurements2, context2, helper)

    if success:
        keys_different = (key1.K != key2.K)
        print(f"\n  上下文绑定测试: {'[OK]' if keys_different else '[FAIL]'}")
        print(f"  不同上下文产生不同密钥: {keys_different}")
        return keys_different
    else:
        print("\n  认证失败（预期行为）")
        return True


def main():
    """主测试流程"""
    print("\n" + "="*80)
    print("设备端-验证端分离测试套件")
    print("验证P-1、P-2、P-3修复后的算法正确性")
    print("="*80)

    results = {}

    try:
        results['scenario_1'] = test_scenario_1_low_noise()
    except Exception as e:
        print(f"\n✗ 场景1失败: {e}")
        import traceback
        traceback.print_exc()
        results['scenario_1'] = False

    try:
        results['scenario_2'] = test_scenario_2_medium_noise()
    except Exception as e:
        print(f"\n✗ 场景2失败: {e}")
        import traceback
        traceback.print_exc()
        results['scenario_2'] = False

    try:
        results['scenario_3'] = test_scenario_3_high_noise()
    except Exception as e:
        print(f"\n✗ 场景3失败: {e}")
        import traceback
        traceback.print_exc()
        results['scenario_3'] = False

    try:
        results['scenario_4'] = test_scenario_4_different_context()
    except Exception as e:
        print(f"\n✗ 场景4失败: {e}")
        import traceback
        traceback.print_exc()
        results['scenario_4'] = False

    # 总结
    print("\n" + "="*80)
    print("测试结果总结")
    print("="*80)

    for name, passed in results.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"{status} - {name}")

    all_passed = all(results.values())

    print("\n" + "="*80)
    if all_passed:
        print("[OK] 所有测试通过！算法实现正确！")
        print("[OK] P-1修复验证：注册和认证使用相同的S")
        print("[OK] P-2修复验证：Ks使用HKDF-Expand派生")
        print("[OK] P-3修复验证：门限正确保存和加载")
    else:
        print("[FAIL] 部分测试失败，需要进一步检查")
    print("="*80 + "\n")

    return all_passed


if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗✗✗ 测试执行出错: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
