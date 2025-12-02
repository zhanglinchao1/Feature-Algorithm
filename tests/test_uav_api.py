"""
测试UAV认证API的基本功能
"""

import secrets
import numpy as np
from authentication_api import FeatureBasedAuthenticationAPI
from feature_synchronization.sync.synchronization_service import SynchronizationService

def test_basic_uav_authentication():
    """测试基本的UAV节点认证"""
    print("=" * 80)
    print("测试UAV节点认证")
    print("=" * 80)
    print()

    # ========== 配置参数 ==========
    uav_node_mac = bytes.fromhex('001122334455')
    peer_node_mac = bytes.fromhex('AABBCCDDEEFF')
    peer_signing_key = secrets.token_bytes(32)

    # ========== 步骤1: 创建UAV节点API ==========
    print("[步骤1] 创建UAV节点API...")
    uav_node_api = FeatureBasedAuthenticationAPI.create_uav_node(
        node_mac=uav_node_mac,
        peer_mac=peer_node_mac,
        epoch_period_ms=30000,
        deterministic=True
    )
    print("✓ UAV节点API已创建")
    print()

    # ========== 步骤2: 创建对等验证节点API ==========
    print("[步骤2] 创建对等验证节点API...")
    peer_verifier_api = FeatureBasedAuthenticationAPI.create_peer_verifier(
        node_mac=peer_node_mac,
        signing_key=peer_signing_key,
        epoch_period_ms=30000,
        beacon_interval_ms=5000,
        deterministic=True
    )
    print("✓ 对等验证节点API已创建")
    print()

    # ========== 步骤3: 模拟CSI测量 ==========
    print("[步骤3] 模拟物理层特征（CSI）测量...")
    np.random.seed(42)
    uav_csi = np.random.randn(6, 62)
    peer_csi = uav_csi.copy()  # 完美信道互惠性
    print(f"✓ CSI数据准备完成 (shape: {uav_csi.shape})")
    print()

    # ========== 步骤4: UAV节点生成认证请求 ==========
    print("[步骤4] UAV节点生成认证请求...")
    auth_request_bytes, uav_response = uav_node_api.authenticate(uav_csi)

    if uav_response.success:
        print("✓ 认证请求生成成功")
        print(f"  节点ID: {uav_response.node_id.hex()}")
        print(f"  Epoch: {uav_response.epoch}")
        print(f"  Session key: {uav_response.session_key.hex()[:32]}...")
        print(f"  延迟: {uav_response.latency_ms:.2f}ms")
        print(f"  请求大小: {len(auth_request_bytes)} bytes")
    else:
        print(f"✗ 认证请求生成失败: {uav_response.reason}")
        return False
    print()

    # ========== 步骤5: 对等节点注册UAV节点 ==========
    print("[步骤5] 对等节点注册UAV节点...")
    # 注意：实际部署中，feature_key应通过安全的带外渠道获取
    # 这里为了演示，我们使用认证响应中返回的feature_key
    # （在实际部署中，设备会通过安全渠道预先注册）
    feature_key = uav_response.feature_key

    success = peer_verifier_api.register_uav_node(
        node_mac=uav_node_mac,
        feature_key=feature_key,
        epoch=uav_response.epoch
    )
    if success:
        print("✓ UAV节点注册成功")
    else:
        print("✗ UAV节点注册失败")
        return False
    print()

    # ========== 步骤6: 对等节点验证认证请求 ==========
    print("[步骤6] 对等节点验证认证请求...")
    peer_response = peer_verifier_api.verify(auth_request_bytes, peer_csi)

    if peer_response.success:
        print("✓✓✓ 认证成功！")
        print(f"  节点ID: {peer_response.node_id.hex()}")
        print(f"  Epoch: {peer_response.epoch}")
        print(f"  Session key: {peer_response.session_key.hex()[:32]}...")
        print(f"  MAT token大小: {len(peer_response.token) if peer_response.token else 0} bytes")
        print(f"  延迟: {peer_response.latency_ms:.2f}ms")

        # 验证session key是否匹配
        if uav_response.session_key == peer_response.session_key:
            print("  ✓ Session key匹配")
        else:
            print("  ✗ Session key不匹配")
            return False
    else:
        print(f"✗✗✗ 认证失败！")
        print(f"  原因: {peer_response.reason}")
        return False
    print()

    print("=" * 80)
    print()
    return True


if __name__ == "__main__":
    print("\n")
    print("*" * 80)
    print(" UAV自组织网络认证API - 测试")
    print("*" * 80)
    print()

    try:
        success = test_basic_uav_authentication()
        if success:
            print("*" * 80)
            print(" 测试成功！")
            print("*" * 80)
        else:
            print("*" * 80)
            print(" 测试失败！")
            print("*" * 80)
    except Exception as e:
        print("*" * 80)
        print(f" 测试异常: {e}")
        print("*" * 80)
        import traceback
        traceback.print_exc()

    print()
