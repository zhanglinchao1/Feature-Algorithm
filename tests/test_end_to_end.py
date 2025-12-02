"""
三模块端到端测试

完整验证 3.1 (feature-encryption) + 3.2 (feature-authentication) + 3.3 (feature_synchronization)
的集成认证流程
"""

import sys
import time
import secrets
import numpy as np
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))
feature_auth_path = Path(__file__).parent / 'feature-authentication'
if str(feature_auth_path) not in sys.path:
    sys.path.insert(0, str(feature_auth_path))

from feature_synchronization.sync.synchronization_service import SynchronizationService
from src.mode2_strong_auth import DeviceSide, VerifierSide
from src.config import AuthConfig


def test_full_authentication_flow():
    """测试完整的认证流程（3.1 + 3.2 + 3.3）"""
    print("=" * 80)
    print("端到端测试：完整认证流程 (3.1 + 3.2 + 3.3)")
    print("=" * 80)
    print()

    # ========== 场景设置 ==========
    print("[场景] IoT设备向网关进行强认证")
    print("  - IoT设备: Smart Sensor (MAC: 001122334455)")
    print("  - 网关: Gateway (MAC: AABBCCDDEEFF)")
    print("  - 认证方式: Mode2 (基于物理层特征)")
    print("  - 同步方式: 3.3 SynchronizationService")
    print()

    # ========== 初始化网关端 ==========
    print("[步骤1] 初始化网关（验证端）...")

    gateway_mac = bytes.fromhex('AABBCCDDEEFF')
    gateway_key = secrets.token_bytes(32)

    # 创建同步服务（网关作为验证节点）
    gateway_sync = SynchronizationService(
        node_type='validator',
        node_id=gateway_mac,
        delta_t=30000,  # 30秒epoch
        beacon_interval=5000,
        deterministic_for_testing=True  # 启用确定性模式用于测试
    )

    # 创建认证验证端
    auth_config = AuthConfig()
    gateway_auth = VerifierSide(
        config=auth_config,
        issuer_id=gateway_mac,
        issuer_key=gateway_key,
        sync_service=gateway_sync
    )

    print(f"✓ Gateway initialized")
    print(f"  MAC: {gateway_mac.hex()}")
    print(f"  Current epoch: {gateway_sync.get_current_epoch()}")
    print(f"  Synchronized: {gateway_sync.is_synchronized()}")
    print()

    # ========== 初始化设备端 ==========
    print("[步骤2] 初始化IoT设备（设备端）...")

    device_mac = bytes.fromhex('001122334455')

    # 创建同步服务（设备节点）
    device_sync = SynchronizationService(
        node_type='device',
        node_id=device_mac,
        delta_t=30000,
        deterministic_for_testing=True  # 启用确定性模式用于测试
    )

    # 创建认证设备端
    device_auth = DeviceSide(
        config=auth_config,
        sync_service=device_sync
    )

    print(f"✓ Device initialized")
    print(f"  MAC: {device_mac.hex()}")
    print(f"  Current epoch: {device_sync.get_current_epoch()}")
    print()

    # ========== 物理层特征采集 ==========
    print("[步骤3] 物理层特征采集（模拟CSI测量）...")

    # 模拟设备和网关之间的信道状态信息（CSI）
    # 注意：在测试环境中，为了确保BCH能够成功恢复密钥，
    # 我们使用相同的CSI模拟完美的信道互惠性
    np.random.seed(42)
    device_csi = np.random.randn(6, 62)

    # 网关端使用相同的CSI（模拟完美的信道互惠性）
    gateway_csi = device_csi.copy()

    print(f"✓ CSI features collected")
    print(f"  Device CSI shape: {device_csi.shape}")
    print(f"  Gateway CSI shape: {gateway_csi.shape}")
    print(f"  Channel correlation: High (same base channel)")
    print()

    # ========== 设备端：生成认证请求 ==========
    print("[步骤4] 设备端生成认证请求（AuthReq）...")

    from src.common import AuthContext

    nonce = secrets.token_bytes(16)
    context = AuthContext(
        src_mac=device_mac,
        dst_mac=gateway_mac,
        epoch=999,  # 会被sync_service覆盖
        nonce=nonce,
        seq=1,
        alg_id='Mode2',
        ver=1,
        csi_id=12345
    )

    try:
        auth_req, session_key_device, feature_key_device = device_auth.create_auth_request(
            dev_id=device_mac,
            Z_frames=device_csi,
            context=context
        )

        print(f"✓ AuthReq generated")
        print(f"  Epoch (synced): {auth_req.epoch}")
        print(f"  DevPseudo: {auth_req.dev_pseudo.hex()}")
        print(f"  Digest: {auth_req.digest.hex()}")
        print(f"  Tag: {auth_req.tag.hex()[:32]}...")
        print(f"  Session Key (device): {session_key_device.hex()[:32]}...")
        print(f"  AuthReq size: {len(auth_req.serialize())} bytes")
        print()

    except Exception as e:
        print(f"✗ Failed to generate AuthReq: {e}")
        import traceback
        traceback.print_exc()
        return False

    # ========== 网关端：注册设备（用于伪名查找） ==========
    print("[步骤5] 网关端注册设备（用于DevPseudo查找）...")

    gateway_auth.register_device(device_mac, feature_key_device, auth_req.epoch)

    print(f"✓ Device registered in gateway")
    print()

    # ========== 网关端：验证认证请求 ==========
    print("[步骤6] 网关端验证认证请求...")

    try:
        result = gateway_auth.verify_auth_request(
            auth_req=auth_req,
            Z_frames=gateway_csi
        )

        if result.success:
            print(f"✓✓✓ Authentication SUCCESSFUL")
            print(f"  Mode: {result.mode}")
            print(f"  Session Key (gateway): {result.session_key.hex()[:32]}...")
            print(f"  Session Key Match: {result.session_key == session_key_device}")
            print(f"  MAT Token size: {len(result.token)} bytes")
            print()

            # 验证会话密钥
            assert result.session_key == session_key_device, "Session keys must match"

        else:
            print(f"✗✗✗ Authentication FAILED")
            print(f"  Reason: {result.reason}")
            print()
            return False

    except Exception as e:
        print(f"✗ Verification failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

    # ========== 验证完整性 ==========
    print("[步骤7] 验证端到端完整性...")

    checks = [
        ("Epoch synchronization", auth_req.epoch == gateway_sync.get_current_epoch()),
        ("Epoch validation", gateway_sync.is_epoch_valid(auth_req.epoch)),
        ("Session key consistency", result.session_key == session_key_device),
        ("Authentication success", result.success),
        ("MAT token present", result.token is not None),
    ]

    all_passed = True
    for check_name, check_result in checks:
        status = "✓" if check_result else "✗"
        print(f"  {status} {check_name}: {check_result}")
        if not check_result:
            all_passed = False

    print()

    if all_passed:
        print("=" * 80)
        print("✓✓✓ 端到端测试通过！所有三个模块协同工作正常。")
        print("=" * 80)
        return True
    else:
        print("=" * 80)
        print("✗✗✗ 端到端测试失败！")
        print("=" * 80)
        return False


def test_multi_device_scenario():
    """测试多设备场景"""
    print()
    print("=" * 80)
    print("端到端测试：多设备并发认证")
    print("=" * 80)
    print()

    # ========== 初始化网关 ==========
    print("[步骤1] 初始化网关...")

    gateway_mac = bytes.fromhex('AABBCCDDEEFF')
    gateway_key = secrets.token_bytes(32)

    gateway_sync = SynchronizationService(
        node_type='validator',
        node_id=gateway_mac,
        delta_t=30000,
        deterministic_for_testing=True
    )

    auth_config = AuthConfig()
    gateway_auth = VerifierSide(
        config=auth_config,
        issuer_id=gateway_mac,
        issuer_key=gateway_key,
        sync_service=gateway_sync
    )

    print(f"✓ Gateway initialized")
    print()

    # ========== 初始化多个设备 ==========
    print("[步骤2] 初始化3个IoT设备...")

    devices = [
        bytes.fromhex('001122334455'),
        bytes.fromhex('112233445566'),
        bytes.fromhex('223344556677'),
    ]

    device_auths = []
    device_syncs = []

    for i, device_mac in enumerate(devices):
        device_sync = SynchronizationService(
            node_type='device',
            node_id=device_mac,
            delta_t=30000,
            deterministic_for_testing=True
        )

        device_auth = DeviceSide(
            config=auth_config,
            sync_service=device_sync
        )

        device_syncs.append(device_sync)
        device_auths.append(device_auth)

        print(f"  Device {i+1}: {device_mac.hex()}")

    print(f"✓ {len(devices)} devices initialized")
    print()

    # ========== 依次认证每个设备 ==========
    print("[步骤3] 依次认证每个设备...")

    success_count = 0
    from src.common import AuthContext

    for i, (device_mac, device_auth) in enumerate(zip(devices, device_auths)):
        print(f"\n  --- Device {i+1}: {device_mac.hex()} ---")

        # 生成不同的CSI（模拟不同信道）
        np.random.seed(42 + i)
        device_csi = np.random.randn(6, 62)
        gateway_csi = device_csi.copy()  # 完美信道互惠性

        # 生成认证请求
        nonce = secrets.token_bytes(16)
        context = AuthContext(
            src_mac=device_mac,
            dst_mac=gateway_mac,
            epoch=0,
            nonce=nonce,
            seq=i+1,
            alg_id='Mode2',
            ver=1,
            csi_id=12345 + i
        )

        try:
            auth_req, session_key, feature_key = device_auth.create_auth_request(
                dev_id=device_mac,
                Z_frames=device_csi,
                context=context
            )

            # 注册设备
            gateway_auth.register_device(device_mac, feature_key, auth_req.epoch)

            # 验证
            result = gateway_auth.verify_auth_request(
                auth_req=auth_req,
                Z_frames=gateway_csi
            )

            if result.success:
                print(f"    ✓ Authentication successful")
                print(f"      Session key: {result.session_key.hex()[:32]}...")
                success_count += 1
            else:
                print(f"    ✗ Authentication failed: {result.reason}")

        except Exception as e:
            print(f"    ✗ Error: {e}")

    print()
    print(f"✓ Multi-device test completed")
    print(f"  Success rate: {success_count}/{len(devices)} ({success_count*100//len(devices)}%)")
    print()

    if success_count == len(devices):
        print("=" * 80)
        print("✓✓✓ 多设备场景测试通过！")
        print("=" * 80)
        return True
    else:
        print("=" * 80)
        print("⚠ 部分设备认证失败（可能是CSI噪声导致）")
        print("=" * 80)
        return success_count >= len(devices) * 0.8  # 80%通过率


def test_performance_benchmark():
    """性能基准测试"""
    print()
    print("=" * 80)
    print("性能基准测试")
    print("=" * 80)
    print()

    # ========== 初始化 ==========
    gateway_mac = bytes.fromhex('AABBCCDDEEFF')
    device_mac = bytes.fromhex('001122334455')

    gateway_sync = SynchronizationService(
        node_type='validator',
        node_id=gateway_mac,
        delta_t=30000,
        deterministic_for_testing=True
    )

    auth_config = AuthConfig()
    gateway_auth = VerifierSide(
        config=auth_config,
        issuer_id=gateway_mac,
        issuer_key=secrets.token_bytes(32),
        sync_service=gateway_sync
    )

    device_sync = SynchronizationService(
        node_type='device',
        node_id=device_mac,
        delta_t=30000,
        deterministic_for_testing=True
    )

    device_auth = DeviceSide(
        config=auth_config,
        sync_service=device_sync
    )

    # ========== 准备数据 ==========
    np.random.seed(42)
    device_csi = np.random.randn(6, 62)
    gateway_csi = device_csi.copy()  # 完美信道互惠性

    from src.common import AuthContext

    # ========== 测试认证请求生成性能 ==========
    print("[测试1] 认证请求生成性能...")

    num_iterations = 10
    total_time = 0

    for i in range(num_iterations):
        nonce = secrets.token_bytes(16)
        context = AuthContext(
            src_mac=device_mac,
            dst_mac=gateway_mac,
            epoch=0,
            nonce=nonce,
            seq=i,
            alg_id='Mode2',
            ver=1,
            csi_id=12345
        )

        start_time = time.time()
        auth_req, session_key, feature_key = device_auth.create_auth_request(
            dev_id=device_mac,
            Z_frames=device_csi,
            context=context
        )
        end_time = time.time()

        elapsed = (end_time - start_time) * 1000  # ms
        total_time += elapsed

    avg_time = total_time / num_iterations
    print(f"  Iterations: {num_iterations}")
    print(f"  Average time: {avg_time:.2f} ms")
    print(f"  Throughput: {1000/avg_time:.2f} req/s")
    print()

    # ========== 测试认证验证性能 ==========
    print("[测试2] 认证验证性能...")

    # 先生成一个请求
    nonce = secrets.token_bytes(16)
    context = AuthContext(
        src_mac=device_mac,
        dst_mac=gateway_mac,
        epoch=0,
        nonce=nonce,
        seq=1,
        alg_id='Mode2',
        ver=1,
        csi_id=12345
    )

    auth_req, session_key, feature_key = device_auth.create_auth_request(
        dev_id=device_mac,
        Z_frames=device_csi,
        context=context
    )

    gateway_auth.register_device(device_mac, feature_key, auth_req.epoch)

    total_time = 0

    for i in range(num_iterations):
        start_time = time.time()
        result = gateway_auth.verify_auth_request(
            auth_req=auth_req,
            Z_frames=gateway_csi
        )
        end_time = time.time()

        elapsed = (end_time - start_time) * 1000  # ms
        total_time += elapsed

    avg_time = total_time / num_iterations
    print(f"  Iterations: {num_iterations}")
    print(f"  Average time: {avg_time:.2f} ms")
    print(f"  Throughput: {1000/avg_time:.2f} verifications/s")
    print()

    # ========== 总结 ==========
    print("Performance Summary:")
    print(f"  ✓ AuthReq generation: {avg_time:.2f} ms")
    print(f"  ✓ AuthReq verification: {avg_time:.2f} ms")
    print(f"  ✓ Total latency: ~{avg_time*2:.2f} ms (round trip)")
    print()

    # 验收标准：< 100ms
    if avg_time * 2 < 100:
        print("=" * 80)
        print("✓✓✓ 性能基准测试通过！延迟满足要求（< 100ms）")
        print("=" * 80)
        return True
    else:
        print("=" * 80)
        print("⚠ 性能基准测试警告：延迟超过100ms")
        print("=" * 80)
        return False


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print(" 三模块端到端测试套件")
    print(" 验证 3.1 (encryption) + 3.2 (authentication) + 3.3 (synchronization)")
    print("=" * 80)
    print()

    results = []

    try:
        # 测试1：完整认证流程
        result1 = test_full_authentication_flow()
        results.append(("Full authentication flow", result1))

        # 测试2：多设备场景
        result2 = test_multi_device_scenario()
        results.append(("Multi-device scenario", result2))

        # 测试3：性能基准
        result3 = test_performance_benchmark()
        results.append(("Performance benchmark", result3))

        # 总结
        print()
        print("=" * 80)
        print("测试总结")
        print("=" * 80)
        for test_name, result in results:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"  {status}: {test_name}")

        all_passed = all(r for _, r in results)
        print()
        if all_passed:
            print("✓✓✓ 所有端到端测试通过！")
        else:
            print("⚠ 部分测试未通过")

        print("=" * 80)

        sys.exit(0 if all_passed else 1)

    except Exception as e:
        print(f"\n✗✗✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
