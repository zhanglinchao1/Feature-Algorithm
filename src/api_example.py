"""
UAV自组织网络认证API使用示例

展示UAV群组管理、移动性支持等高级功能的使用方法。
"""

import secrets
import time
import numpy as np
from authentication_api import FeatureBasedAuthenticationAPI
from uav_swarm_manager import UAVSwarmManager
from uav_mobility_support import UAVMobilitySupport


def example1_basic_uav_authentication():
    """示例1: 基本UAV节点认证"""
    print("\n" + "=" * 80)
    print("示例1: 基本UAV节点认证")
    print("=" * 80)
    print()

    # 场景：新UAV加入现有UAV群组
    new_uav_mac = bytes.fromhex('001122334455')
    verifier_uav_mac = bytes.fromhex('AABBCCDDEEFF')
    verifier_signing_key = secrets.token_bytes(32)

    print("[步骤1] 创建UAV节点API（请求认证方）...")
    new_uav_api = FeatureBasedAuthenticationAPI.create_uav_node(
        node_mac=new_uav_mac,
        peer_mac=verifier_uav_mac,
        deterministic=True  # 测试模式
    )
    print("✓ UAV节点API已创建")
    print()

    print("[步骤2] 创建对等验证节点API（验证方）...")
    verifier_api = FeatureBasedAuthenticationAPI.create_peer_verifier(
        node_mac=verifier_uav_mac,
        signing_key=verifier_signing_key,
        deterministic=True  # 测试模式
    )
    print("✓ 对等验证节点API已创建")
    print()

    print("[步骤3] 新UAV测量CSI并生成认证请求...")
    # 模拟CSI测量
    np.random.seed(42)
    new_uav_csi = np.random.randn(6, 62)

    # 生成认证请求
    auth_request_bytes, uav_response = new_uav_api.authenticate(new_uav_csi)

    if uav_response.success:
        print("✓ 认证请求生成成功")
        print(f"  节点ID: {uav_response.node_id.hex()}")
        print(f"  Session key: {uav_response.session_key.hex()[:32]}...")
        print(f"  延迟: {uav_response.latency_ms:.2f}ms")
    else:
        print(f"✗ 认证请求生成失败: {uav_response.reason}")
        return
    print()

    print("[步骤4] 验证UAV注册新节点...")
    verifier_api.register_uav_node(
        node_mac=new_uav_mac,
        feature_key=uav_response.feature_key,
        epoch=uav_response.epoch
    )
    print("✓ UAV节点已注册")
    print()

    print("[步骤5] 验证UAV测量CSI并验证认证请求...")
    # 信道互惠性：验证方测量到相似的CSI
    verifier_csi = new_uav_csi.copy()

    # 验证认证请求
    verifier_response = verifier_api.verify(auth_request_bytes, verifier_csi)

    if verifier_response.success:
        print("✓✓✓ 认证成功！")
        print(f"  UAV节点ID: {verifier_response.node_id.hex()}")
        print(f"  Session key: {verifier_response.session_key.hex()[:32]}...")
        print(f"  Session key匹配: {uav_response.session_key == verifier_response.session_key}")
        print(f"  MAT令牌大小: {len(verifier_response.token)} bytes")
        print(f"  延迟: {verifier_response.latency_ms:.2f}ms")
    else:
        print(f"✗✗✗ 认证失败")
        print(f"  原因: {verifier_response.reason}")

    print()
    print("=" * 80)
    print()


def example2_uav_swarm_management():
    """示例2: UAV群组管理"""
    print("\n" + "=" * 80)
    print("示例2: UAV群组管理")
    print("=" * 80)
    print()

    # 场景：协调节点管理UAV群组
    coordinator_mac = bytes.fromhex('AABBCCDDEEFF')
    coordinator_key = secrets.token_bytes(32)

    print("[步骤1] 创建UAV群组管理器...")
    swarm_manager = UAVSwarmManager(
        coordinator_mac=coordinator_mac,
        coordinator_signing_key=coordinator_key,
        group_id="AlphaSwarm",
        member_timeout=300,  # 5分钟超时
        key_rotation_interval=3600  # 1小时轮换
    )
    print()

    # 添加成员
    print("[步骤2] 添加UAV成员到群组...")
    uav_members = [
        bytes.fromhex('001122334455'),
        bytes.fromhex('112233445566'),
        bytes.fromhex('223344556677')
    ]

    for i, uav_mac in enumerate(uav_members):
        # 模拟UAV认证过程
        uav_api = FeatureBasedAuthenticationAPI.create_uav_node(
            node_mac=uav_mac,
            peer_mac=coordinator_mac
        )

        # 生成认证请求
        csi = np.random.randn(6, 62)
        auth_req, response = uav_api.authenticate(csi)

        # 添加到群组
        if response.success:
            swarm_manager.add_member(
                node_mac=uav_mac,
                feature_key=response.feature_key,
                epoch=response.epoch,
                session_key=response.session_key
            )

    print()

    # 验证成员认证
    print("[步骤3] 验证UAV成员认证...")
    test_uav_mac = uav_members[0]
    test_uav_api = FeatureBasedAuthenticationAPI.create_uav_node(
        node_mac=test_uav_mac,
        peer_mac=coordinator_mac
    )

    csi = np.random.randn(6, 62)
    auth_req_bytes, _ = test_uav_api.authenticate(csi)

    success, node_mac, response = swarm_manager.verify_member(auth_req_bytes, csi)
    if success:
        print(f"✓ 成员认证成功: {node_mac.hex()}")
    print()

    # 显示群组状态
    print("[步骤4] 显示群组状态...")
    swarm_manager.print_status()

    # 群组密钥轮换
    print("[步骤5] 手动触发群组密钥轮换...")
    new_key = swarm_manager.update_group_key()
    print(f"✓ 群组密钥已更新: {new_key.hex()[:32]}...")
    print()

    # 撤销成员
    print("[步骤6] 撤销UAV成员...")
    revoked_uav = uav_members[2]
    swarm_manager.revoke_member(revoked_uav, reason="安全测试")
    print()

    # 显示最终状态
    print("[步骤7] 显示最终群组状态...")
    swarm_manager.print_status()

    print("=" * 80)
    print()


def example3_uav_mobility_and_handover():
    """示例3: UAV移动性和快速切换"""
    print("\n" + "=" * 80)
    print("示例3: UAV移动性和快速切换")
    print("=" * 80)
    print()

    # 场景：UAV在多个对等节点间移动
    mobile_uav_mac = bytes.fromhex('001122334455')
    peer1_mac = bytes.fromhex('AABBCCDDEEFF')
    peer2_mac = bytes.fromhex('BBCCDDEE0011')
    peer3_mac = bytes.fromhex('CCDDEEFF1122')

    print("[步骤1] 创建移动UAV和移动性支持...")
    mobility = UAVMobilitySupport(
        node_mac=mobile_uav_mac,
        fast_handover_enabled=True,
        mat_token_cache_time=300
    )
    print()

    # 初始连接到peer1
    print("[步骤2] 初始连接到Peer1...")
    peer1_api = FeatureBasedAuthenticationAPI.create_uav_node(
        node_mac=mobile_uav_mac,
        peer_mac=peer1_mac
    )

    csi = np.random.randn(6, 62)
    auth_req, response = peer1_api.authenticate(csi)

    if response.success:
        print(f"✓ 连接成功: {peer1_mac.hex()}")
        print(f"  Session key: {response.session_key.hex()[:32]}...")

        # 缓存MAT令牌
        mobility.cache_mat_token(peer1_mac, response.token, response.session_key)
        mobility.current_peer = peer1_mac
        mobility.current_session_key = response.session_key
        mobility.current_mat_token = response.token
    print()

    # 快速切换到peer2
    print("[步骤3] 快速切换到Peer2...")
    success, context = mobility.fast_handover(
        old_peer_mac=peer1_mac,
        new_peer_mac=peer2_mac
    )

    if success:
        print(f"✓ 快速切换成功")
        print(f"  切换延迟: {context.handover_latency_ms:.2f}ms")
        print(f"  新对等节点: {peer2_mac.hex()}")
    else:
        print("✗ 快速切换失败")
    print()

    # 完整切换到peer3（需要重新认证）
    print("[步骤4] 完整切换到Peer3（重新认证）...")
    peer3_api = FeatureBasedAuthenticationAPI.create_uav_node(
        node_mac=mobile_uav_mac,
        peer_mac=peer3_mac
    )

    success, context, response = mobility.full_handover(
        old_peer_mac=peer2_mac,
        new_peer_mac=peer3_mac,
        new_peer_api=peer3_api,
        csi_measurements=csi
    )

    if success:
        print(f"✓ 完整切换成功")
        print(f"  切换延迟: {context.handover_latency_ms:.2f}ms")
        print(f"  新对等节点: {peer3_mac.hex()}")
        print(f"  Session key: {response.session_key.hex()[:32]}...")
    else:
        print("✗ 完整切换失败")
    print()

    # 智能切换（自动选择快速或完整）
    print("[步骤5] 智能切换回Peer1...")
    success, method = mobility.smart_handover(
        old_peer_mac=peer3_mac,
        new_peer_mac=peer1_mac
    )

    if success:
        print(f"✓ 智能切换成功")
        print(f"  切换方式: {method}")
    print()

    # 显示统计
    print("[步骤6] 显示移动性统计...")
    mobility.print_statistics()

    print("=" * 80)
    print()


def example4_integrated_uav_network():
    """示例4: 集成UAV网络（群组管理 + 移动性）"""
    print("\n" + "=" * 80)
    print("示例4: 集成UAV网络（群组管理 + 移动性）")
    print("=" * 80)
    print()

    # 场景：完整的UAV网络，包含群组管理和移动性支持
    coordinator_mac = bytes.fromhex('000000000001')
    coordinator_key = secrets.token_bytes(32)

    # 创建群组管理器
    print("[步骤1] 创建UAV群组...")
    swarm = UAVSwarmManager(
        coordinator_mac=coordinator_mac,
        coordinator_signing_key=coordinator_key,
        group_id="BetaSwarm"
    )
    print()

    # 添加多个UAV成员
    print("[步骤2] 添加UAV成员...")
    uav_list = []
    for i in range(5):
        uav_mac = bytes.fromhex(f'00112233445{i}')
        uav_api = FeatureBasedAuthenticationAPI.create_uav_node(
            node_mac=uav_mac,
            peer_mac=coordinator_mac
        )

        # 认证并添加
        csi = np.random.randn(6, 62)
        _, response = uav_api.authenticate(csi)

        if response.success:
            swarm.add_member(
                node_mac=uav_mac,
                feature_key=response.feature_key,
                epoch=response.epoch,
                session_key=response.session_key
            )
            uav_list.append(uav_mac)

    print(f"✓ 已添加 {len(uav_list)} 个UAV成员")
    print()

    # 模拟UAV移动
    print("[步骤3] 模拟UAV移动和切换...")
    mobile_uav = uav_list[0]
    mobility = UAVMobilitySupport(mobile_uav)

    # 初始连接
    mobility.current_peer = coordinator_mac
    print(f"  UAV {mobile_uav.hex()} 连接到协调节点")

    # 模拟切换到其他UAV节点
    for target_peer in uav_list[1:3]:
        time.sleep(0.1)  # 模拟时间流逝
        success, method = mobility.smart_handover(
            old_peer_mac=mobility.current_peer,
            new_peer_mac=target_peer
        )
        print(f"  切换到 {target_peer.hex()}: {method}")

    print()

    # 群组操作
    print("[步骤4] 群组密钥轮换...")
    swarm.update_group_key()
    print()

    # 清理不活跃成员
    print("[步骤5] 清理不活跃成员...")
    # 手动设置某个成员为过期（测试）
    test_member = uav_list[-1]
    if test_member in swarm.members:
        swarm.members[test_member].last_seen = time.time() - 400  # 超时

    inactive = swarm.cleanup_inactive_members()
    print(f"✓ 清理了 {len(inactive)} 个不活跃成员")
    print()

    # 最终状态
    print("[步骤6] 最终群组状态...")
    swarm.print_status()

    print("[步骤7] 移动性统计...")
    mobility.print_statistics()

    print("=" * 80)
    print()


def example5_error_handling():
    """示例5: 错误处理和异常场景"""
    print("\n" + "=" * 80)
    print("示例5: 错误处理和异常场景")
    print("=" * 80)
    print()

    uav_mac = bytes.fromhex('001122334455')
    peer_mac = bytes.fromhex('AABBCCDDEEFF')
    peer_key = secrets.token_bytes(32)

    # 测试1: CSI不匹配导致认证失败
    print("[测试1] CSI不匹配...")
    uav_api = FeatureBasedAuthenticationAPI.create_uav_node(
        node_mac=uav_mac,
        peer_mac=peer_mac
    )
    peer_api = FeatureBasedAuthenticationAPI.create_peer_verifier(
        node_mac=peer_mac,
        signing_key=peer_key
    )

    # UAV端使用一个CSI
    uav_csi = np.random.randn(6, 62)
    auth_req, response = uav_api.authenticate(uav_csi)

    # 注册
    peer_api.register_uav_node(uav_mac, response.feature_key, response.epoch)

    # 验证端使用不同的CSI（模拟信道条件差）
    peer_csi = np.random.randn(6, 62)  # 完全不同的CSI
    verify_response = peer_api.verify(auth_req, peer_csi)

    if not verify_response.success:
        print(f"✓ 预期的失败: {verify_response.reason}")
    print()

    # 测试2: 未注册的UAV
    print("[测试2] 未注册的UAV...")
    unknown_uav = bytes.fromhex('999999999999')
    unknown_api = FeatureBasedAuthenticationAPI.create_uav_node(
        node_mac=unknown_uav,
        peer_mac=peer_mac
    )

    csi = np.random.randn(6, 62)
    auth_req, _ = unknown_api.authenticate(csi)
    verify_response = peer_api.verify(auth_req, csi)

    if not verify_response.success:
        print(f"✓ 预期的失败: {verify_response.reason}")
    print()

    # 测试3: 快速切换缓存过期
    print("[测试3] 快速切换缓存过期...")
    mobility = UAVMobilitySupport(
        node_mac=uav_mac,
        mat_token_cache_time=1  # 1秒过期
    )

    # 缓存令牌
    mobility.cache_mat_token(peer_mac, b'test_token', b'test_key' * 2)

    # 等待过期
    time.sleep(1.5)

    # 尝试获取（应该返回None）
    cached = mobility.get_cached_mat_token(peer_mac)
    if cached is None:
        print("✓ 缓存已正确过期")
    print()

    print("=" * 80)
    print()


def run_all_examples():
    """运行所有示例"""
    print("\n" + "#" * 80)
    print("# UAV自组织网络认证API - 完整示例集")
    print("#" * 80)

    example1_basic_uav_authentication()
    example2_uav_swarm_management()
    example3_uav_mobility_and_handover()
    example4_integrated_uav_network()
    example5_error_handling()

    print("\n" + "#" * 80)
    print("# 所有示例运行完成！")
    print("#" * 80)
    print()


if __name__ == "__main__":
    # 可以运行所有示例，或单独运行某个示例
    import sys

    if len(sys.argv) > 1:
        example_num = sys.argv[1]
        examples = {
            '1': example1_basic_uav_authentication,
            '2': example2_uav_swarm_management,
            '3': example3_uav_mobility_and_handover,
            '4': example4_integrated_uav_network,
            '5': example5_error_handling
        }

        if example_num in examples:
            examples[example_num]()
        else:
            print(f"未知示例编号: {example_num}")
            print("可用示例: 1, 2, 3, 4, 5")
    else:
        # 默认运行所有示例
        run_all_examples()
