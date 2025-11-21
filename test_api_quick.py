"""
快速API测试脚本

测试模式1和模式2的基本功能
"""

import requests
import json
import numpy as np

BASE_URL = "http://localhost:5000"

def print_section(title):
    """打印分隔线"""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)
    print()

def test_mode1():
    """测试模式1 - RFF快速认证"""
    print_section("测试模式1 - RFF快速认证")
    
    # 步骤1: 注册设备
    print("[步骤1] 注册设备...")
    response = requests.post(
        f"{BASE_URL}/api/device/mode1/register",
        json={"dev_id": "001122334455"}
    )
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    print()
    
    # 步骤2: 认证成功
    print("[步骤2] RFF认证 - 高分数（应成功）...")
    response = requests.post(
        f"{BASE_URL}/api/device/mode1/authenticate",
        json={
            "dev_id": "001122334455",
            "rff_score": 0.85,
            "rff_confidence": 0.90,
            "snr": 20.0
        }
    )
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(f"认证结果: {result['data']['authenticated']}")
    print(f"决策: {result['data']['decision']}")
    print(f"延迟: {result['data']['latency_ms']}ms")
    print()
    
    # 步骤3: 认证失败
    print("[步骤3] RFF认证 - 低分数（应失败）...")
    response = requests.post(
        f"{BASE_URL}/api/device/mode1/authenticate",
        json={
            "dev_id": "001122334455",
            "rff_score": 0.5,
            "rff_confidence": 0.7,
            "snr": 20.0
        }
    )
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(f"认证结果: {result['data']['authenticated']}")
    print(f"决策: {result['data']['decision']}")
    print(f"原因: {result['data']['reason']}")
    print()

def test_mode2():
    """测试模式2 - 强认证"""
    print_section("测试模式2 - 强认证")
    
    # 生成CSI数据
    np.random.seed(42)
    csi = np.random.randn(6, 62).tolist()
    
    # 步骤1: 设备端创建认证请求
    print("[步骤1] 设备端创建认证请求...")
    response = requests.post(
        f"{BASE_URL}/api/device/mode2/create_request",
        json={
            "dev_id": "001122334455",
            "dst_mac": "AABBCCDDEEFF",
            "csi": csi,
            "seq": 1,
            "csi_id": 12345
        }
    )
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(f"认证请求已创建")
    print(f"  Epoch: {result['data']['epoch']}")
    print(f"  Dev Pseudo: {result['data']['dev_pseudo'][:24]}...")
    print(f"  Session Key: {result['data']['session_key'][:32]}...")
    print(f"  延迟: {result['data']['latency_ms']}ms")
    print()
    
    # 保存数据
    auth_req = result['data']['auth_req']
    session_key_device = result['data']['session_key']
    feature_key = result['data']['feature_key']
    epoch = result['data']['epoch']
    
    # 步骤2: 验证端注册设备
    print("[步骤2] 验证端注册设备...")
    response = requests.post(
        f"{BASE_URL}/api/verifier/mode2/register",
        json={
            "dev_id": "001122334455",
            "feature_key": feature_key,
            "epoch": epoch
        }
    )
    print(f"状态码: {response.status_code}")
    print(f"设备已注册")
    print()
    
    # 步骤3: 验证端验证请求
    print("[步骤3] 验证端验证认证请求...")
    response = requests.post(
        f"{BASE_URL}/api/verifier/mode2/verify",
        json={
            "auth_req": auth_req,
            "csi": csi  # 使用相同的CSI（模拟信道互惠性）
        }
    )
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(f"认证结果: {result['data']['authenticated']}")
    
    if result['data']['authenticated']:
        session_key_verifier = result['data']['session_key']
        print(f"  Session Key: {session_key_verifier[:32]}...")
        print(f"  Session Key匹配: {session_key_device == session_key_verifier}")
        print(f"  MAT令牌大小: {result['data']['token_size']} bytes")
        print(f"  延迟: {result['data']['latency_ms']}ms")
        print("[OK][OK][OK] 模式2认证成功！")
    else:
        print(f"  失败原因: {result['data']['reason']}")
        print("[FAIL] 模式2认证失败")
    print()

def test_status():
    """测试状态端点"""
    print_section("测试服务器状态")
    
    response = requests.get(f"{BASE_URL}/api/status")
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    print()

if __name__ == '__main__':
    try:
        print("\n" + "=" * 80)
        print("基于特征的身份认证 - API快速测试")
        print("=" * 80)
        print()
        print(f"API服务器: {BASE_URL}")
        print()
        
        # 测试服务器连接
        try:
            response = requests.get(BASE_URL, timeout=2)
            print("[OK] 服务器连接成功")
        except requests.exceptions.ConnectionError:
            print("[FAIL] 无法连接到服务器")
            print("请确保服务器已启动: python api_server.py")
            exit(1)
        
        # 重置状态
        print("\n重置服务器状态...")
        requests.post(f"{BASE_URL}/api/reset")
        print("[OK] 服务器状态已重置")
        
        # 执行测试
        test_mode1()
        test_mode2()
        test_status()
        
        print("\n" + "=" * 80)
        print("[OK][OK][OK] 所有测试完成！")
        print("=" * 80)
        print()
        print("下一步:")
        print("  1. 使用Postman导入 postman_collection.json")
        print("  2. 参考 POSTMAN_TEST_GUIDE.md 进行详细测试")
        print("  3. 测试各种边界条件和失败场景")
        print()
        
    except Exception as e:
        print(f"\n[FAIL][FAIL][FAIL] 错误: {e}")
        import traceback
        traceback.print_exc()

