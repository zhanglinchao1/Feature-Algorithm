"""
基于特征的MAC身份认证API使用示例

演示如何使用统一的认证API进行设备认证。
"""

import secrets
import numpy as np
from authentication_api import FeatureBasedAuthenticationAPI


def example_basic_authentication():
    """示例1: 基本认证流程"""
    print("=" * 80)
    print("示例1: 基本设备认证流程")
    print("=" * 80)
    print()

    # ========== 配置参数 ==========
    device_mac = bytes.fromhex('001122334455')
    gateway_mac = bytes.fromhex('AABBCCDDEEFF')
    gateway_key = secrets.token_bytes(32)

    # ========== 步骤1: 创建设备端API ==========
    print("[步骤1] 创建设备端API...")
    device_api = FeatureBasedAuthenticationAPI.create_device(
        device_mac=device_mac,
        gateway_mac=gateway_mac,
        epoch_period_ms=30000,  # 30秒epoch
        deterministic=True  # 测试模式
    )
    print("✓ 设备端API已创建")
    print()

    # ========== 步骤2: 创建网关端API ==========
    print("[步骤2] 创建网关端API...")
    gateway_api = FeatureBasedAuthenticationAPI.create_gateway(
        gateway_mac=gateway_mac,
        gateway_key=gateway_key,
        epoch_period_ms=30000,
        beacon_interval_ms=5000,
        deterministic=True  # 测试模式
    )
    print("✓ 网关端API已创建")
    print()

    # ========== 步骤3: 模拟CSI测量 ==========
    print("[步骤3] 模拟物理层特征（CSI）测量...")
    # 注意：实际应用中，CSI数据应从无线网卡获取
    np.random.seed(42)
    device_csi = np.random.randn(6, 62)  # 6帧，62维特征
    gateway_csi = device_csi.copy()  # 完美信道互惠性
    print(f"✓ CSI数据准备完成 (shape: {device_csi.shape})")
    print()

    # ========== 步骤4: 设备端生成认证请求 ==========
    print("[步骤4] 设备端生成认证请求...")
    auth_request_bytes, device_response = device_api.authenticate(device_csi)

    if device_response.success:
        print("✓ 认证请求生成成功")
        print(f"  设备ID: {device_response.device_id.hex()}")
        print(f"  Epoch: {device_response.epoch}")
        print(f"  Session key: {device_response.session_key.hex()[:32]}...")
        print(f"  延迟: {device_response.latency_ms:.2f}ms")
        print(f"  请求大小: {len(auth_request_bytes)} bytes")
    else:
        print(f"✗ 认证请求生成失败: {device_response.reason}")
        return
    print()

    # ========== 步骤5: 网关注册设备（首次认证需要） ==========
    print("[步骤5] 网关注册设备...")
    # 注意：实际部署中，feature_key应通过安全的带外渠道获取
    # 这里为了演示，我们从设备响应中获取（仅用于测试）
    # 需要先运行一次设备认证获取feature_key
    # 在实际应用中，这个密钥应该在设备注册时预先共享

    # 为了演示，我们需要从设备认证过程获取feature_key
    # 实际中应该通过安全渠道预先注册
    from feature_synchronization.sync.synchronization_service import SynchronizationService
    temp_sync = SynchronizationService('device', device_mac, delta_t=30000,
                                      domain="FeatureAuth", deterministic_for_testing=True)
    temp_km = temp_sync.generate_or_get_key_material(
        device_mac=device_mac,
        epoch=0,
        feature_vector=device_csi,
        nonce=bytes(16),
        validator_mac=gateway_mac
    )
    feature_key = temp_km.feature_key

    success = gateway_api.register_device(
        device_mac=device_mac,
        feature_key=feature_key,
        epoch=0
    )
    if success:
        print("✓ 设备注册成功")
    else:
        print("✗ 设备注册失败")
        return
    print()

    # ========== 步骤6: 网关验证认证请求 ==========
    print("[步骤6] 网关验证认证请求...")
    gateway_response = gateway_api.verify(auth_request_bytes, gateway_csi)

    if gateway_response.success:
        print("✓✓✓ 认证成功！")
        print(f"  设备ID: {gateway_response.device_id.hex()}")
        print(f"  Epoch: {gateway_response.epoch}")
        print(f"  Session key: {gateway_response.session_key.hex()[:32]}...")
        print(f"  MAT token大小: {len(gateway_response.token) if gateway_response.token else 0} bytes")
        print(f"  延迟: {gateway_response.latency_ms:.2f}ms")

        # 验证session key是否匹配
        if device_response.session_key == gateway_response.session_key:
            print("  ✓ Session key匹配")
        else:
            print("  ✗ Session key不匹配")
    else:
        print(f"✗✗✗ 认证失败！")
        print(f"  原因: {gateway_response.reason}")
    print()

    print("=" * 80)
    print()


def example_multiple_devices():
    """示例2: 多设备认证"""
    print("=" * 80)
    print("示例2: 多设备认证")
    print("=" * 80)
    print()

    # 网关配置
    gateway_mac = bytes.fromhex('AABBCCDDEEFF')
    gateway_key = secrets.token_bytes(32)

    # 创建网关API
    gateway_api = FeatureBasedAuthenticationAPI.create_gateway(
        gateway_mac=gateway_mac,
        gateway_key=gateway_key,
        deterministic=True
    )

    # 设备列表
    devices = [
        bytes.fromhex('001122334455'),
        bytes.fromhex('112233445566'),
        bytes.fromhex('223344556677'),
    ]

    print(f"网关已初始化，准备认证{len(devices)}个设备...")
    print()

    success_count = 0

    for i, device_mac in enumerate(devices, 1):
        print(f"--- 设备 {i}: {device_mac.hex()} ---")

        # 创建设备API
        device_api = FeatureBasedAuthenticationAPI.create_device(
            device_mac=device_mac,
            gateway_mac=gateway_mac,
            deterministic=True
        )

        # 模拟CSI（每个设备使用不同的CSI）
        np.random.seed(42 + i)
        device_csi = np.random.randn(6, 62)
        gateway_csi = device_csi.copy()

        # 设备认证
        auth_request_bytes, device_response = device_api.authenticate(device_csi)

        if not device_response.success:
            print(f"  ✗ 认证请求生成失败: {device_response.reason}")
            continue

        # 注册设备（实际中应预先注册）
        from feature_synchronization.sync.synchronization_service import SynchronizationService
        temp_sync = SynchronizationService('device', device_mac, delta_t=30000,
                                          domain="FeatureAuth", deterministic_for_testing=True)
        temp_km = temp_sync.generate_or_get_key_material(
            device_mac=device_mac,
            epoch=0,
            feature_vector=device_csi,
            nonce=bytes(16),
            validator_mac=gateway_mac
        )
        gateway_api.register_device(device_mac, temp_km.feature_key, 0)

        # 网关验证
        gateway_response = gateway_api.verify(auth_request_bytes, gateway_csi)

        if gateway_response.success:
            print(f"  ✓ 认证成功")
            print(f"    Session key: {gateway_response.session_key.hex()[:24]}...")
            success_count += 1
        else:
            print(f"  ✗ 认证失败: {gateway_response.reason}")

        print()

    print("=" * 80)
    print(f"认证完成: {success_count}/{len(devices)} 成功 ({100*success_count/len(devices):.0f}%)")
    print("=" * 80)
    print()


def example_error_handling():
    """示例3: 错误处理"""
    print("=" * 80)
    print("示例3: 错误处理示例")
    print("=" * 80)
    print()

    # 场景1: MAC地址长度错误
    print("[场景1] MAC地址长度错误")
    try:
        device_api = FeatureBasedAuthenticationAPI.create_device(
            device_mac=b'\x00\x11\x22',  # 只有3字节
            gateway_mac=bytes.fromhex('AABBCCDDEEFF')
        )
        print("✗ 应该抛出异常")
    except ValueError as e:
        print(f"✓ 正确捕获异常: {e}")
    print()

    # 场景2: CSI数据格式错误
    print("[场景2] CSI数据格式错误")
    device_api = FeatureBasedAuthenticationAPI.create_device(
        device_mac=bytes.fromhex('001122334455'),
        gateway_mac=bytes.fromhex('AABBCCDDEEFF'),
        deterministic=True
    )

    try:
        # 错误的CSI格式（1D数组）
        wrong_csi = np.random.randn(62)
        auth_request_bytes, response = device_api.authenticate(wrong_csi)
        print("✗ 应该抛出异常")
    except ValueError as e:
        print(f"✓ 正确捕获异常: {e}")
    print()

    # 场景3: 未注册的设备认证
    print("[场景3] 未注册的设备")
    gateway_api = FeatureBasedAuthenticationAPI.create_gateway(
        gateway_mac=bytes.fromhex('AABBCCDDEEFF'),
        gateway_key=secrets.token_bytes(32),
        deterministic=True
    )

    device_mac = bytes.fromhex('998877665544')
    device_api = FeatureBasedAuthenticationAPI.create_device(
        device_mac=device_mac,
        gateway_mac=bytes.fromhex('AABBCCDDEEFF'),
        deterministic=True
    )

    csi = np.random.randn(6, 62)
    auth_request_bytes, _ = device_api.authenticate(csi)

    # 不注册设备，直接验证
    response = gateway_api.verify(auth_request_bytes, csi)
    if not response.success:
        print(f"✓ 正确拒绝未注册设备: {response.reason}")
    else:
        print("✗ 不应该认证成功")
    print()

    print("=" * 80)
    print()


def main():
    """运行所有示例"""
    print("\n")
    print("*" * 80)
    print(" 基于特征的MAC身份认证API - 使用示例")
    print("*" * 80)
    print()

    # 运行示例
    example_basic_authentication()
    example_multiple_devices()
    example_error_handling()

    print("*" * 80)
    print(" 所有示例运行完成")
    print("*" * 80)
    print()


if __name__ == "__main__":
    main()
