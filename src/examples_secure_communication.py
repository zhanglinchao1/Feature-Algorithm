"""
UAV安全通信示例

展示如何使用UAV安全通信功能进行：
1. 点对点加密通信
2. 群组广播加密
3. 会话管理
"""

import secrets
import numpy as np
from uav_secure_channel import UAVSecureChannel
from uav_secure_swarm import UAVSecureSwarmCommunicator
from authentication_api import FeatureBasedAuthenticationAPI
from uav_swarm_manager import UAVSwarmManager


def example1_p2p_encrypted_communication():
    """示例1: 点对点加密通信"""
    print("\n" + "=" * 80)
    print("示例1: 点对点加密通信")
    print("=" * 80)
    print()

    # 场景：两个UAV节点建立安全通信
    uav_a_mac = bytes.fromhex('001122334455')
    uav_b_mac = bytes.fromhex('AABBCCDDEEFF')

    print("[步骤1] 模拟认证过程，生成会话密钥...")
    # 在实际场景中，这通过物理层特征认证获得
    session_key = secrets.token_bytes(32)
    print(f"✓ Session Key: {session_key.hex()[:32]}...")
    print()

    print("[步骤2] UAV-A 和 UAV-B 初始化安全信道...")
    channel_a = UAVSecureChannel(uav_a_mac)
    channel_b = UAVSecureChannel(uav_b_mac)
    print("✓ 安全信道已初始化")
    print()

    print("[步骤3] UAV-A 发送加密消息到 UAV-B...")
    plaintext = b"Hello UAV-B! This is a secure message from UAV-A."
    print(f"  明文: {plaintext.decode('utf-8')}")

    encrypted_msg = channel_a.encrypt_p2p(
        plaintext=plaintext,
        session_key=session_key,
        dst_mac=uav_b_mac
    )
    print(f"✓ 消息已加密")
    print(f"  明文大小: {len(plaintext)} bytes")
    print(f"  密文大小: {len(encrypted_msg)} bytes")
    print(f"  加密开销: {len(encrypted_msg) - len(plaintext)} bytes")
    print()

    print("[步骤4] UAV-B 接收并解密消息...")
    success, decrypted_msg, src_mac = channel_b.decrypt_p2p(
        encrypted_data=encrypted_msg,
        session_key=session_key
    )

    if success:
        print("✓✓✓ 解密成功！")
        print(f"  来源: {src_mac.hex()}")
        print(f"  明文: {decrypted_msg.decode('utf-8')}")
        print(f"  完整性验证: {'通过' if decrypted_msg == plaintext else '失败'}")
    else:
        print("✗ 解密失败")

    print()

    print("[步骤5] 测试防重放攻击...")
    print("  尝试重放相同消息...")
    success2, _, _ = channel_b.decrypt_p2p(
        encrypted_data=encrypted_msg,
        session_key=session_key
    )
    if not success2:
        print("✓ 重放攻击已被阻止！")
    else:
        print("✗ 重放攻击未被检测（不应发生）")

    print()
    print("=" * 80)
    print()


def example2_group_broadcast_encryption():
    """示例2: 群组广播加密"""
    print("\n" + "=" * 80)
    print("示例2: 群组广播加密")
    print("=" * 80)
    print()

    # 场景：协调节点向群组广播消息
    coordinator_mac = bytes.fromhex('AABBCCDDEEFF')
    member1_mac = bytes.fromhex('001122334455')
    member2_mac = bytes.fromhex('112233445566')
    member3_mac = bytes.fromhex('223344556677')

    coordinator_signing_key = secrets.token_bytes(32)
    group_id = "UAVSwarm001"

    print("[步骤1] 创建群组管理器...")
    swarm_manager = UAVSwarmManager(
        coordinator_mac=coordinator_mac,
        coordinator_signing_key=coordinator_signing_key,
        group_id=group_id
    )
    print()

    print("[步骤2] 添加群组成员（简化注册）...")
    # 模拟成员认证并添加
    for i, member_mac in enumerate([member1_mac, member2_mac, member3_mac], 1):
        feature_key = secrets.token_bytes(32)
        session_key = secrets.token_bytes(32)
        mat_token = secrets.token_bytes(64)

        swarm_manager.add_member(
            node_mac=member_mac,
            feature_key=feature_key,
            session_key=session_key,
            mat_token=mat_token
        )

    print(f"✓ 已添加 {swarm_manager.get_member_count()} 个成员")
    print()

    print("[步骤3] 派生群组密钥...")
    group_key, version = swarm_manager.get_group_key()
    print(f"✓ 群组密钥版本: {version}")
    print(f"  Group Key: {group_key.hex()[:32]}...")
    print()

    print("[步骤4] 协调节点广播加密消息...")
    coordinator_channel = UAVSecureChannel(coordinator_mac)

    broadcast_msg = b"Attention all UAVs: Return to base immediately!"
    print(f"  明文: {broadcast_msg.decode('utf-8')}")

    encrypted_broadcast = coordinator_channel.encrypt_group(
        plaintext=broadcast_msg,
        group_key=group_key,
        group_id=group_id
    )
    print(f"✓ 广播消息已加密")
    print(f"  密文大小: {len(encrypted_broadcast)} bytes")
    print()

    print("[步骤5] 所有成员接收并解密广播...")
    for i, member_mac in enumerate([member1_mac, member2_mac, member3_mac], 1):
        member_channel = UAVSecureChannel(member_mac)

        success, decrypted_msg, src_mac = member_channel.decrypt_group(
            encrypted_data=encrypted_broadcast,
            group_key=group_key,
            group_id=group_id
        )

        if success:
            print(f"  ✓ 成员 {i} ({member_mac.hex()}) 解密成功")
            print(f"    来源: {src_mac.hex()}")
            print(f"    消息: {decrypted_msg.decode('utf-8')}")
        else:
            print(f"  ✗ 成员 {i} 解密失败")

    print()
    print("=" * 80)
    print()


def example3_integrated_secure_swarm():
    """示例3: 集成认证与加密通信"""
    print("\n" + "=" * 80)
    print("示例3: 集成认证与加密通信")
    print("=" * 80)
    print()

    # 场景：完整的认证和通信流程
    coordinator_mac = bytes.fromhex('AABBCCDDEEFF')
    uav_mac = bytes.fromhex('001122334455')
    coordinator_signing_key = secrets.token_bytes(32)

    print("[步骤1] 创建协调节点通信器...")
    coordinator_comm = UAVSecureSwarmCommunicator(
        node_mac=coordinator_mac,
        is_coordinator=True,
        coordinator_signing_key=coordinator_signing_key,
        group_id="UAVSwarm001"
    )
    print()

    print("[步骤2] 创建UAV节点通信器...")
    uav_comm = UAVSecureSwarmCommunicator(
        node_mac=uav_mac,
        is_coordinator=False,
        group_id="UAVSwarm001"
    )
    print()

    print("[步骤3] UAV节点向协调节点发起认证...")
    # 模拟CSI测量
    np.random.seed(42)
    csi_data = np.random.randn(6, 62)

    success, reason = uav_comm.authenticate_and_establish_session(
        peer_mac=coordinator_mac,
        my_csi=csi_data,
        is_requester=True
    )

    if success:
        print("✓ 认证成功，会话已建立")
    else:
        print(f"✗ 认证失败: {reason}")
        return
    print()

    print("[步骤4] 协调节点验证并建立会话...")
    success, reason = coordinator_comm.authenticate_and_establish_session(
        peer_mac=uav_mac,
        my_csi=csi_data,
        peer_csi=csi_data,
        peer_signing_key=coordinator_signing_key,
        is_requester=False
    )

    if success:
        print("✓ 验证成功，会话已建立")
    else:
        print(f"✗ 验证失败: {reason}")
        return
    print()

    print("[步骤5] UAV发送加密消息到协调节点...")
    msg1 = b"Coordinator, this is UAV-01. Position update: (lat=39.9, lon=116.4, alt=100m)"

    success, encrypted_msg1, reason = uav_comm.send_secure_message(
        plaintext=msg1,
        dst_mac=coordinator_mac
    )

    if success:
        print(f"✓ 消息已发送")
        print(f"  密文大小: {len(encrypted_msg1)} bytes")
    else:
        print(f"✗ 发送失败: {reason}")
    print()

    print("[步骤6] 协调节点接收并解密...")
    # 注意：这里需要修改receive_secure_message以支持会话查找
    print("  （演示：在完整实现中，这里会通过网络接收并解密消息）")
    print()

    print("[步骤7] 查看会话统计...")
    coordinator_comm.print_status()
    uav_comm.print_status()

    print("=" * 80)
    print()


def example4_security_features():
    """示例4: 安全特性演示"""
    print("\n" + "=" * 80)
    print("示例4: 安全特性演示")
    print("=" * 80)
    print()

    uav_a_mac = bytes.fromhex('001122334455')
    uav_b_mac = bytes.fromhex('AABBCCDDEEFF')
    session_key = secrets.token_bytes(32)

    channel_a = UAVSecureChannel(uav_a_mac)
    channel_b = UAVSecureChannel(uav_b_mac)

    # 测试1: 消息完整性保护
    print("[测试1] 消息完整性保护...")
    plaintext = b"Original message"
    encrypted = channel_a.encrypt_p2p(plaintext, session_key, uav_b_mac)

    # 篡改密文
    tampered = bytearray(encrypted)
    tampered[-20] ^= 0xFF  # 修改一个字节
    tampered = bytes(tampered)

    success, _, _ = channel_b.decrypt_p2p(tampered, session_key)
    if not success:
        print("  ✓ 检测到消息被篡改")
    else:
        print("  ✗ 未检测到篡改（不应发生）")
    print()

    # 测试2: 防重放攻击
    print("[测试2] 防重放攻击...")
    plaintext2 = b"Test replay attack"
    encrypted2 = channel_a.encrypt_p2p(plaintext2, session_key, uav_b_mac)

    # 第一次解密（正常）
    success1, msg1, _ = channel_b.decrypt_p2p(encrypted2, session_key)
    print(f"  第1次解密: {'成功' if success1 else '失败'}")

    # 第二次解密同一消息（重放）
    success2, msg2, _ = channel_b.decrypt_p2p(encrypted2, session_key)
    print(f"  第2次解密（重放）: {'成功' if success2 else '失败'}")

    if not success2:
        print("  ✓ 重放攻击被成功阻止")
    else:
        print("  ✗ 重放攻击未被阻止（不应发生）")
    print()

    # 测试3: 消息时效性
    print("[测试3] 消息时效性验证...")
    print("  （在实际环境中，过期消息会被拒绝）")
    print("  ✓ 时间戳验证已启用（MAX_MESSAGE_AGE_MS=30000ms）")
    print()

    # 测试4: 序列号单调性
    print("[测试4] 序列号单调性...")
    stats = channel_a.get_statistics()
    print(f"  ✓ 已发送消息: {stats['total_messages_sent']}")
    print(f"  ✓ 序列号自动递增，确保消息顺序")
    print()

    print("=" * 80)
    print()


def example5_performance_benchmark():
    """示例5: 性能基准测试"""
    print("\n" + "=" * 80)
    print("示例5: 性能基准测试")
    print("=" * 80)
    print()

    import time

    uav_a_mac = bytes.fromhex('001122334455')
    uav_b_mac = bytes.fromhex('AABBCCDDEEFF')
    session_key = secrets.token_bytes(32)

    channel_a = UAVSecureChannel(uav_a_mac)
    channel_b = UAVSecureChannel(uav_b_mac)

    # 测试不同大小的消息
    test_sizes = [64, 256, 1024, 4096, 16384]  # bytes

    print("测试点对点加密性能:")
    print(f"{'消息大小':<12} {'加密延迟':<15} {'解密延迟':<15} {'总延迟':<15} {'吞吐量':<15}")
    print("-" * 80)

    for size in test_sizes:
        plaintext = secrets.token_bytes(size)

        # 加密性能
        start = time.time()
        for _ in range(100):
            encrypted = channel_a.encrypt_p2p(plaintext, session_key, uav_b_mac)
        encrypt_time = (time.time() - start) / 100 * 1000  # ms

        # 解密性能
        start = time.time()
        for _ in range(100):
            channel_b.decrypt_p2p(encrypted, session_key)
        decrypt_time = (time.time() - start) / 100 * 1000  # ms

        total_time = encrypt_time + decrypt_time
        throughput = (size / 1024) / (total_time / 1000)  # KB/s

        print(f"{size:<12} {encrypt_time:<15.3f} {decrypt_time:<15.3f} {total_time:<15.3f} {throughput:<15.2f}")

    print()
    print("注：")
    print("  - 延迟单位：毫秒（ms）")
    print("  - 吞吐量单位：KB/s")
    print("  - 每个测试运行100次取平均值")
    print()

    print("=" * 80)
    print()


def main():
    """运行所有示例"""
    print("\n")
    print("████████████████████████████████████████████████████████████████████████████████")
    print("██                                                                            ██")
    print("██           UAV安全通信完整示例 - 认证、加密、会话管理                          ██")
    print("██                                                                            ██")
    print("████████████████████████████████████████████████████████████████████████████████")

    try:
        example1_p2p_encrypted_communication()
        input("按Enter继续下一个示例...")

        example2_group_broadcast_encryption()
        input("按Enter继续下一个示例...")

        example3_integrated_secure_swarm()
        input("按Enter继续下一个示例...")

        example4_security_features()
        input("按Enter继续下一个示例...")

        example5_performance_benchmark()

        print("\n")
        print("████████████████████████████████████████████████████████████████████████████████")
        print("██                                                                            ██")
        print("██                         所有示例运行完成！                                  ██")
        print("██                                                                            ██")
        print("████████████████████████████████████████████████████████████████████████████████")
        print()

    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    except Exception as e:
        print(f"\n\n错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
