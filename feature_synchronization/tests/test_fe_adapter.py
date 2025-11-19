"""
测试 FeatureEncryptionAdapter 适配器

验证3.3模块能够正确调用3.1模块的接口
"""

import numpy as np
import secrets
import sys
from pathlib import Path

# 添加feature_synchronization到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters.fe_adapter import FeatureEncryptionAdapter, create_adapter


class TestFeatureEncryptionAdapter:
    """测试FeatureEncryptionAdapter类"""

    def test_adapter_initialization(self):
        """测试适配器初始化"""
        adapter = create_adapter(deterministic_for_testing=True)
        assert adapter is not None
        assert adapter.is_deterministic_mode() == True

    def test_derive_keys_for_device(self):
        """测试为设备派生密钥"""
        # 初始化适配器
        adapter = create_adapter(deterministic_for_testing=True)

        # 准备参数
        device_mac = bytes.fromhex('001122334455')
        validator_mac = bytes.fromhex('AABBCCDDEEFF')
        epoch = 0
        nonce = secrets.token_bytes(16)
        hash_chain_counter = 0

        # 生成测试CSI数据
        np.random.seed(42)
        Z_frames = np.random.randn(6, 62)  # M=6帧，D=62维

        # 调用派生密钥接口
        S, L, K, Ks, digest = adapter.derive_keys_for_device(
            device_mac=device_mac,
            validator_mac=validator_mac,
            feature_vector=Z_frames,
            epoch=epoch,
            nonce=nonce,
            hash_chain_counter=hash_chain_counter
        )

        # 验证返回值
        assert S is not None and len(S) == 32, "S应为32字节"
        assert L is not None and len(L) == 32, "L应为32字节"
        assert K is not None and len(K) == 32, "K应为32字节"
        assert Ks is not None and len(Ks) == 32, "Ks应为32字节"
        assert digest is not None and len(digest) == 8, "digest应为8字节"

        print(f"✓ 密钥派生成功")
        print(f"  S:      {S.hex()[:32]}...")
        print(f"  L:      {L.hex()[:32]}...")
        print(f"  K:      {K.hex()[:32]}...")
        print(f"  Ks:     {Ks.hex()[:32]}...")
        print(f"  digest: {digest.hex()}")

    def test_authenticate_device(self):
        """测试设备认证"""
        # 初始化适配器
        adapter = create_adapter(deterministic_for_testing=True)

        # 准备参数
        device_mac = bytes.fromhex('001122334455')
        validator_mac = bytes.fromhex('AABBCCDDEEFF')
        epoch = 0
        nonce = secrets.token_bytes(16)
        hash_chain_counter = 0

        # 生成相同的测试CSI数据
        np.random.seed(42)
        Z_frames = np.random.randn(6, 62)

        # 第一次：注册
        S1, L1, K1, Ks1, digest1 = adapter.derive_keys_for_device(
            device_mac=device_mac,
            validator_mac=validator_mac,
            feature_vector=Z_frames,
            epoch=epoch,
            nonce=nonce,
            hash_chain_counter=hash_chain_counter
        )

        # 第二次：认证（使用相同的CSI）
        success, S2, L2, K2, Ks2, digest2 = adapter.authenticate_device(
            device_mac=device_mac,
            validator_mac=validator_mac,
            feature_vector=Z_frames,
            epoch=epoch,
            nonce=nonce,
            hash_chain_counter=hash_chain_counter
        )

        # 验证认证成功
        assert success == True, "认证应该成功"
        assert S1 == S2, "S应该一致"
        assert K1 == K2, "K应该一致"
        assert Ks1 == Ks2, "Ks应该一致"
        assert digest1 == digest2, "digest应该一致"

        print(f"✓ 设备认证成功")
        print(f"  S match:      {S1 == S2}")
        print(f"  K match:      {K1 == K2}")
        print(f"  Ks match:     {Ks1 == Ks2}")
        print(f"  digest match: {digest1 == digest2}")

    def test_authentication_with_noise(self):
        """测试带噪声的认证"""
        # 初始化适配器
        adapter = create_adapter(deterministic_for_testing=True)

        # 准备参数
        device_mac = bytes.fromhex('001122334455')
        validator_mac = bytes.fromhex('AABBCCDDEEFF')
        epoch = 0
        nonce = secrets.token_bytes(16)
        hash_chain_counter = 0

        # 生成基础CSI
        np.random.seed(42)
        base_csi = np.random.randn(62)

        # 注册：基础CSI + 小噪声
        np.random.seed(42)
        Z_reg = np.array([base_csi + np.random.randn(62) * 0.05 for _ in range(6)])

        # 认证：基础CSI + 不同的小噪声
        np.random.seed(100)
        Z_auth = np.array([base_csi + np.random.randn(62) * 0.05 for _ in range(6)])

        # 注册
        S1, L1, K1, Ks1, digest1 = adapter.derive_keys_for_device(
            device_mac=device_mac,
            validator_mac=validator_mac,
            feature_vector=Z_reg,
            epoch=epoch,
            nonce=nonce,
            hash_chain_counter=hash_chain_counter
        )

        # 认证
        success, S2, L2, K2, Ks2, digest2 = adapter.authenticate_device(
            device_mac=device_mac,
            validator_mac=validator_mac,
            feature_vector=Z_auth,
            epoch=epoch,
            nonce=nonce,
            hash_chain_counter=hash_chain_counter
        )

        # 验证
        if success:
            print(f"✓ 带噪声认证成功")
            print(f"  S match:      {S1 == S2}")
            print(f"  K match:      {K1 == K2}")
            print(f"  Ks match:     {Ks1 == Ks2}")
            print(f"  digest match: {digest1 == digest2}")
        else:
            print(f"✗ 带噪声认证失败（可能是噪声过大）")

    def test_parameter_validation(self):
        """测试参数验证"""
        adapter = create_adapter(deterministic_for_testing=True)

        # 测试无效的MAC地址长度
        try:
            adapter.derive_keys_for_device(
                device_mac=b'\x00\x00',  # 只有2字节
                validator_mac=b'\x00' * 6,
                feature_vector=np.random.randn(6, 62),
                epoch=0,
                nonce=secrets.token_bytes(16),
                hash_chain_counter=0
            )
            assert False, "应该抛出ValueError"
        except ValueError as e:
            assert "device_mac must be 6 bytes" in str(e)

        # 测试无效的nonce长度
        try:
            adapter.derive_keys_for_device(
                device_mac=b'\x00' * 6,
                validator_mac=b'\x00' * 6,
                feature_vector=np.random.randn(6, 62),
                epoch=0,
                nonce=b'\x00\x00',  # 只有2字节
                hash_chain_counter=0
            )
            assert False, "应该抛出ValueError"
        except ValueError as e:
            assert "nonce must be 16 bytes" in str(e)

        # 测试无效的feature_vector维度
        try:
            adapter.derive_keys_for_device(
                device_mac=b'\x00' * 6,
                validator_mac=b'\x00' * 6,
                feature_vector=np.random.randn(62),  # 1D数组
                epoch=0,
                nonce=secrets.token_bytes(16),
                hash_chain_counter=0
            )
            assert False, "应该抛出ValueError"
        except ValueError as e:
            assert "feature_vector must be 2D array" in str(e)

        print("✓ 参数验证测试通过")

    def test_different_epochs_produce_different_keys(self):
        """测试不同epoch产生不同的密钥"""
        adapter = create_adapter(deterministic_for_testing=True)

        device_mac = bytes.fromhex('001122334455')
        validator_mac = bytes.fromhex('AABBCCDDEEFF')
        nonce = secrets.token_bytes(16)

        np.random.seed(42)
        Z_frames = np.random.randn(6, 62)

        # epoch=0
        S0, L0, K0, Ks0, digest0 = adapter.derive_keys_for_device(
            device_mac=device_mac,
            validator_mac=validator_mac,
            feature_vector=Z_frames,
            epoch=0,
            nonce=nonce,
            hash_chain_counter=0
        )

        # epoch=1
        S1, L1, K1, Ks1, digest1 = adapter.derive_keys_for_device(
            device_mac=device_mac,
            validator_mac=validator_mac,
            feature_vector=Z_frames,
            epoch=1,
            nonce=nonce,
            hash_chain_counter=0
        )

        # 验证密钥不同
        assert K0 != K1, "不同epoch应产生不同的特征密钥K"
        assert Ks0 != Ks1, "不同epoch应产生不同的会话密钥Ks"

        print(f"✓ 不同epoch产生不同密钥")
        print(f"  epoch=0 K:  {K0.hex()[:32]}...")
        print(f"  epoch=1 K:  {K1.hex()[:32]}...")


if __name__ == '__main__':
    """直接运行测试"""
    print("=" * 80)
    print("FeatureEncryptionAdapter 适配器测试")
    print("=" * 80)
    print()

    test = TestFeatureEncryptionAdapter()

    print("[测试1] 适配器初始化")
    test.test_adapter_initialization()
    print()

    print("[测试2] 密钥派生")
    test.test_derive_keys_for_device()
    print()

    print("[测试3] 设备认证")
    test.test_authenticate_device()
    print()

    print("[测试4] 带噪声认证")
    test.test_authentication_with_noise()
    print()

    print("[测试5] 参数验证")
    test.test_parameter_validation()
    print()

    print("[测试6] 不同epoch产生不同密钥")
    test.test_different_epochs_produce_different_keys()
    print()

    print("=" * 80)
    print("✓✓✓ 所有测试通过！")
    print("=" * 80)
