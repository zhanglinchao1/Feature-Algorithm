"""
简单的三模块集成测试

测试3.3模块使用真实的3.1接口
"""

import sys
import numpy as np
import secrets
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

from feature_synchronization.core.epoch_state import EpochState
from feature_synchronization.sync.key_rotation import KeyRotationManager


def test_key_rotation_with_real_fe():
    """测试使用真实FE适配器的密钥轮换"""
    print("=" * 80)
    print("测试3.3模块使用真实3.1接口")
    print("=" * 80)
    print()

    # 1. 初始化epoch状态
    print("[步骤1] 初始化EpochState...")
    import time
    epoch_state = EpochState(
        current_epoch=0,
        epoch_start_time=int(time.time() * 1000),
        epoch_duration=30000  # 30秒
    )
    print("✓ EpochState初始化成功")
    print()

    # 2. 初始化密钥轮换管理器（启用真实FE）
    print("[步骤2] 初始化KeyRotationManager（使用真实FE适配器）...")
    key_rotation = KeyRotationManager(
        epoch_state=epoch_state,
        domain="TestDomain",
        use_real_fe=True,
        deterministic_for_testing=True  # 启用确定性测试模式
    )
    print("✓ KeyRotationManager初始化成功")
    print()

    # 3. 准备测试数据
    print("[步骤3] 准备测试数据...")
    device_mac = bytes.fromhex('001122334455')
    validator_mac = bytes.fromhex('AABBCCDDEEFF')
    epoch = 0
    nonce = secrets.token_bytes(16)

    # 生成测试CSI数据
    np.random.seed(42)
    feature_vector = np.random.randn(6, 62)  # M=6帧，D=62维
    print(f"  device_mac:   {device_mac.hex()}")
    print(f"  validator_mac: {validator_mac.hex()}")
    print(f"  epoch:        {epoch}")
    print(f"  feature_vector shape: {feature_vector.shape}")
    print("✓ 测试数据准备完成")
    print()

    # 4. 生成密钥材料（注册）
    print("[步骤4] 生成密钥材料（使用真实3.1接口）...")
    key_material1 = key_rotation.generate_key_material(
        device_mac=device_mac,
        validator_mac=validator_mac,
        epoch=epoch,
        feature_vector=feature_vector,
        nonce=nonce
    )
    print("✓ 密钥材料生成成功")
    print(f"  feature_key: {key_material1.feature_key.hex()[:32]}...")
    print(f"  session_key: {key_material1.session_key.hex()[:32]}...")
    print(f"  pseudonym:   {key_material1.pseudonym.hex()}")
    print(f"  epoch:       {key_material1.epoch}")
    print()

    # 5. 再次生成（认证）- 使用相同CSI
    print("[步骤5] 再次生成密钥材料（使用相同CSI）...")
    key_material2 = key_rotation.generate_key_material(
        device_mac=device_mac,
        validator_mac=validator_mac,
        epoch=epoch,
        feature_vector=feature_vector,
        nonce=nonce
    )
    print("✓ 密钥材料生成成功")
    print()

    # 6. 验证密钥一致性
    print("[步骤6] 验证密钥一致性...")
    assert key_material1.feature_key == key_material2.feature_key, "feature_key应该一致"
    assert key_material1.session_key == key_material2.session_key, "session_key应该一致"
    assert key_material1.pseudonym == key_material2.pseudonym, "pseudonym应该一致"
    print("✓ 所有密钥一致！")
    print(f"  feature_key match: True")
    print(f"  session_key match: True")
    print(f"  pseudonym match:   True")
    print()

    # 7. 测试不同epoch产生不同密钥
    print("[步骤7] 测试不同epoch产生不同密钥...")
    key_material_epoch1 = key_rotation.generate_key_material(
        device_mac=device_mac,
        validator_mac=validator_mac,
        epoch=1,  # 不同的epoch
        feature_vector=feature_vector,
        nonce=nonce
    )
    print("✓ epoch=1 密钥材料生成成功")
    assert key_material1.feature_key != key_material_epoch1.feature_key, "不同epoch应产生不同feature_key"
    assert key_material1.session_key != key_material_epoch1.session_key, "不同epoch应产生不同session_key"
    assert key_material1.pseudonym != key_material_epoch1.pseudonym, "不同epoch应产生不同pseudonym"
    print("✓ 验证通过：不同epoch产生不同密钥")
    print(f"  epoch=0 feature_key: {key_material1.feature_key.hex()[:32]}...")
    print(f"  epoch=1 feature_key: {key_material_epoch1.feature_key.hex()[:32]}...")
    print(f"  epoch=0 pseudonym:   {key_material1.pseudonym.hex()}")
    print(f"  epoch=1 pseudonym:   {key_material_epoch1.pseudonym.hex()}")
    print()

    # 8. 测试密钥轮换
    print("[步骤8] 测试密钥轮换...")
    rotated_key = key_rotation.rotate_keys_on_epoch_change(
        device_mac=device_mac,
        validator_mac=validator_mac,
        new_epoch=2,
        feature_vector=feature_vector
    )
    print("✓ 密钥轮换成功")
    print(f"  new epoch:      {rotated_key.epoch}")
    print(f"  new feature_key: {rotated_key.feature_key.hex()[:32]}...")
    print(f"  new pseudonym:   {rotated_key.pseudonym.hex()}")
    print()

    print("=" * 80)
    print("✓✓✓ 所有测试通过！3.3模块成功使用真实3.1接口")
    print("=" * 80)


def test_key_rotation_with_mock_fallback():
    """测试Mock降级功能"""
    print()
    print("=" * 80)
    print("测试Mock降级功能")
    print("=" * 80)
    print()

    import time
    epoch_state = EpochState(
        current_epoch=0,
        epoch_start_time=int(time.time() * 1000),
        epoch_duration=30000
    )

    print("[测试] 不提供feature_vector时使用Mock...")
    key_rotation = KeyRotationManager(
        epoch_state=epoch_state,
        domain="TestDomain",
        use_real_fe=True,
        deterministic_for_testing=True
    )

    device_mac = bytes.fromhex('001122334455')
    validator_mac = bytes.fromhex('AABBCCDDEEFF')
    nonce = secrets.token_bytes(16)

    # 不提供feature_vector
    key_material = key_rotation.generate_key_material(
        device_mac=device_mac,
        validator_mac=validator_mac,
        epoch=0,
        feature_vector=None,  # 不提供CSI数据
        nonce=nonce
    )

    print("✓ Mock降级成功")
    print(f"  feature_key: {key_material.feature_key.hex()[:32]}...")
    print(f"  session_key: {key_material.session_key.hex()[:32]}...")
    print()


if __name__ == '__main__':
    try:
        test_key_rotation_with_real_fe()
        test_key_rotation_with_mock_fallback()
        print("\n" + "=" * 80)
        print("✓✓✓ 集成测试全部通过！")
        print("=" * 80)
    except AssertionError as e:
        print(f"\n✗✗✗ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗✗✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
