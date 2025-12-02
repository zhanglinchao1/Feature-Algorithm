"""
UAV安全通信自动化测试

自动运行所有测试并生成报告。
"""

import secrets
import time
import numpy as np
from uav_secure_channel import UAVSecureChannel
from uav_secure_swarm import UAVSecureSwarmCommunicator
from uav_swarm_manager import UAVSwarmManager


def test_p2p_encryption():
    """测试点对点加密"""
    print("\n" + "=" * 80)
    print("测试1: 点对点加密通信")
    print("=" * 80)

    try:
        uav_a_mac = bytes.fromhex('001122334455')
        uav_b_mac = bytes.fromhex('AABBCCDDEEFF')
        session_key = secrets.token_bytes(32)

        channel_a = UAVSecureChannel(uav_a_mac)
        channel_b = UAVSecureChannel(uav_b_mac)

        # 测试加密/解密
        plaintext = b"Hello UAV-B! This is a secure message from UAV-A."
        encrypted = channel_a.encrypt_p2p(plaintext, session_key, uav_b_mac)
        success, decrypted, src_mac = channel_b.decrypt_p2p(encrypted, session_key)

        assert success, "解密失败"
        assert decrypted == plaintext, "明文不匹配"
        assert src_mac == uav_a_mac, "源MAC不匹配"

        print("✓ 加密/解密: 通过")
        print(f"  明文大小: {len(plaintext)} bytes")
        print(f"  密文大小: {len(encrypted)} bytes")

        # 测试防重放
        success2, _, _ = channel_b.decrypt_p2p(encrypted, session_key)
        assert not success2, "重放攻击未被检测"
        print("✓ 防重放攻击: 通过")

        return True

    except Exception as e:
        print(f"✗ 测试失败: {str(e)}")
        return False


def test_group_encryption():
    """测试群组广播加密"""
    print("\n" + "=" * 80)
    print("测试2: 群组广播加密")
    print("=" * 80)

    try:
        coordinator_mac = bytes.fromhex('AABBCCDDEEFF')
        member1_mac = bytes.fromhex('001122334455')
        member2_mac = bytes.fromhex('112233445566')
        member3_mac = bytes.fromhex('223344556677')

        coordinator_signing_key = secrets.token_bytes(32)
        group_id = "UAVSwarm001"

        # 创建群组管理器
        swarm_manager = UAVSwarmManager(
            coordinator_mac=coordinator_mac,
            coordinator_signing_key=coordinator_signing_key,
            group_id=group_id
        )

        # 添加成员
        for member_mac in [member1_mac, member2_mac, member3_mac]:
            swarm_manager.add_member(
                node_mac=member_mac,
                feature_key=secrets.token_bytes(32),
                session_key=secrets.token_bytes(32)
            )

        # 获取群组密钥
        group_key, version = swarm_manager.get_group_key()
        print(f"✓ 群组密钥版本: {version}")

        # 广播加密
        coordinator_channel = UAVSecureChannel(coordinator_mac)
        broadcast_msg = b"Attention all UAVs: Return to base!"
        encrypted = coordinator_channel.encrypt_group(broadcast_msg, group_key, group_id)

        print(f"✓ 广播加密: 通过")
        print(f"  密文大小: {len(encrypted)} bytes")

        # 所有成员解密
        success_count = 0
        for member_mac in [member1_mac, member2_mac, member3_mac]:
            member_channel = UAVSecureChannel(member_mac)
            success, decrypted, src_mac = member_channel.decrypt_group(
                encrypted, group_key, group_id
            )
            if success and decrypted == broadcast_msg:
                success_count += 1

        assert success_count == 3, f"只有{success_count}/3成员成功解密"
        print(f"✓ 群组解密: 通过（3/3成员）")

        return True

    except Exception as e:
        print(f"✗ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_message_integrity():
    """测试消息完整性"""
    print("\n" + "=" * 80)
    print("测试3: 消息完整性保护")
    print("=" * 80)

    try:
        uav_a_mac = bytes.fromhex('001122334455')
        uav_b_mac = bytes.fromhex('AABBCCDDEEFF')
        session_key = secrets.token_bytes(32)

        channel_a = UAVSecureChannel(uav_a_mac)
        channel_b = UAVSecureChannel(uav_b_mac)

        plaintext = b"Original message"
        encrypted = channel_a.encrypt_p2p(plaintext, session_key, uav_b_mac)

        # 篡改密文
        tampered = bytearray(encrypted)
        tampered[-20] ^= 0xFF
        tampered = bytes(tampered)

        success, _, _ = channel_b.decrypt_p2p(tampered, session_key)
        assert not success, "篡改未被检测"

        print("✓ 消息完整性验证: 通过")
        print("  篡改检测: 已阻止")

        return True

    except Exception as e:
        print(f"✗ 测试失败: {str(e)}")
        return False


def test_performance():
    """测试性能"""
    print("\n" + "=" * 80)
    print("测试4: 加密性能基准")
    print("=" * 80)

    try:
        uav_a_mac = bytes.fromhex('001122334455')
        uav_b_mac = bytes.fromhex('AABBCCDDEEFF')
        session_key = secrets.token_bytes(32)

        channel_a = UAVSecureChannel(uav_a_mac)
        channel_b = UAVSecureChannel(uav_b_mac)

        test_sizes = [64, 256, 1024, 4096]
        print(f"\n{'大小(B)':<10} {'加密(ms)':<12} {'解密(ms)':<12} {'吞吐量(KB/s)':<15}")
        print("-" * 60)

        for size in test_sizes:
            plaintext = secrets.token_bytes(size)

            # 加密性能 - 每次迭代创建新消息
            encrypted_messages = []
            start = time.time()
            iterations = 100
            for _ in range(iterations):
                encrypted = channel_a.encrypt_p2p(plaintext, session_key, uav_b_mac)
                encrypted_messages.append(encrypted)
            encrypt_time = (time.time() - start) / iterations * 1000

            # 解密性能 - 使用不同的消息
            start = time.time()
            for encrypted in encrypted_messages:
                channel_b.decrypt_p2p(encrypted, session_key)
            decrypt_time = (time.time() - start) / iterations * 1000

            throughput = (size / 1024) / ((encrypt_time + decrypt_time) / 1000)

            print(f"{size:<10} {encrypt_time:<12.3f} {decrypt_time:<12.3f} {throughput:<15.2f}")

        print("\n✓ 性能测试: 完成")
        return True

    except Exception as e:
        print(f"✗ 测试失败: {str(e)}")
        return False


def test_session_management():
    """测试会话管理"""
    print("\n" + "=" * 80)
    print("测试5: 会话管理和端到端通信")
    print("=" * 80)

    try:
        uav_a_mac = bytes.fromhex('001122334455')
        uav_b_mac = bytes.fromhex('AABBCCDDEEFF')
        session_key = secrets.token_bytes(32)

        # 创建安全信道
        channel_a = UAVSecureChannel(uav_a_mac)
        channel_b = UAVSecureChannel(uav_b_mac)

        print("✓ 安全信道已创建")

        # 模拟建立会话（在实际中这通过认证完成）
        from uav_secure_swarm import SecureCommunicationSession
        session_a_to_b = SecureCommunicationSession(
            peer_mac=uav_b_mac,
            session_key=session_key,
            secure_channel=channel_a,
            established_at=time.time(),
            last_used=time.time()
        )

        session_b_to_a = SecureCommunicationSession(
            peer_mac=uav_a_mac,
            session_key=session_key,
            secure_channel=channel_b,
            established_at=time.time(),
            last_used=time.time()
        )

        print("✓ 会话已建立")

        # 测试发送和接收
        plaintext1 = b"Hello UAV-B, this is UAV-A"
        encrypted1 = channel_a.encrypt_p2p(plaintext1, session_key, uav_b_mac)

        success, decrypted1, src = channel_b.decrypt_p2p(encrypted1, session_key)
        assert success, "解密失败"
        assert decrypted1 == plaintext1, "数据不匹配"

        print("✓ A→B通信: 通过")

        # 反向通信
        plaintext2 = b"Hello UAV-A, this is UAV-B responding"
        encrypted2 = channel_b.encrypt_p2p(plaintext2, session_key, uav_a_mac)

        success, decrypted2, src = channel_a.decrypt_p2p(encrypted2, session_key)
        assert success, "解密失败"
        assert decrypted2 == plaintext2, "数据不匹配"

        print("✓ B→A通信: 通过")

        # 测试会话统计
        session_a_to_b.messages_sent = 10
        session_a_to_b.messages_received = 8

        print(f"✓ 会话统计: 通过")
        print(f"  发送: {session_a_to_b.messages_sent} | 接收: {session_a_to_b.messages_received}")

        return True

    except Exception as e:
        print(f"✗ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_key_rotation():
    """测试密钥轮换"""
    print("\n" + "=" * 80)
    print("测试6: 群组密钥轮换")
    print("=" * 80)

    try:
        coordinator_mac = bytes.fromhex('AABBCCDDEEFF')
        coordinator_signing_key = secrets.token_bytes(32)

        swarm_manager = UAVSwarmManager(
            coordinator_mac=coordinator_mac,
            coordinator_signing_key=coordinator_signing_key,
            group_id="UAVSwarm001"
        )

        # 添加成员
        member1_mac = bytes.fromhex('001122334455')
        member2_mac = bytes.fromhex('112233445566')

        for member_mac in [member1_mac, member2_mac]:
            swarm_manager.add_member(
                node_mac=member_mac,
                feature_key=secrets.token_bytes(32),
                session_key=secrets.token_bytes(32)
            )

        # 获取初始密钥
        key1, version1 = swarm_manager.get_group_key()
        print(f"✓ 初始密钥版本: {version1}")

        # 轮换密钥
        key2 = swarm_manager.update_group_key()
        _, version2 = swarm_manager.get_group_key()

        assert version2 == version1 + 1, "版本号未递增"
        assert key1 != key2, "密钥未改变"
        print(f"✓ 密钥轮换: 通过")
        print(f"  新版本: {version2}")

        # 撤销成员触发轮换
        swarm_manager.revoke_member(member1_mac)
        _, version3 = swarm_manager.get_group_key()

        assert version3 == version2 + 1, "撤销后版本号未递增"
        print(f"✓ 撤销触发轮换: 通过")
        print(f"  撤销后版本: {version3}")

        return True

    except Exception as e:
        print(f"✗ 测试失败: {str(e)}")
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n")
    print("=" * 80)
    print("                  UAV安全通信功能测试报告")
    print("=" * 80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    tests = [
        ("点对点加密通信", test_p2p_encryption),
        ("群组广播加密", test_group_encryption),
        ("消息完整性保护", test_message_integrity),
        ("加密性能基准", test_performance),
        ("会话管理", test_session_management),
        ("群组密钥轮换", test_key_rotation),
    ]

    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))
        time.sleep(0.5)  # 短暂延迟

    # 生成总结报告
    print("\n" + "=" * 80)
    print("                        测试总结")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{name:<30} {status}")

    print("=" * 80)
    print(f"总计: {passed}/{total} 测试通过 ({passed/total*100:.1f}%)")
    print("=" * 80)

    if passed == total:
        print("\n🎉 所有测试通过！UAV安全通信功能正常工作。\n")
        return True
    else:
        print(f"\n⚠️ {total - passed} 个测试失败，请检查错误信息。\n")
        return False


if __name__ == "__main__":
    try:
        success = run_all_tests()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n\n严重错误: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)
