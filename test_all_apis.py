"""
完整的API接口测试脚本
测试所有7个接口并记录结果
"""
import requests
import json
import numpy as np
from datetime import datetime

# 测试结果记录
test_results = []
test_data_for_postman = {}

def log_test(name, success, status_code, response, error=None):
    """记录测试结果"""
    result = {
        'name': name,
        'success': success,
        'status_code': status_code,
        'response': response,
        'error': error,
        'timestamp': datetime.now().isoformat()
    }
    test_results.append(result)
    
    if success:
        print(f"[OK] {name}")
    else:
        print(f"[FAIL] {name}")
        if error:
            print(f"  错误: {error}")
    return result

def test_get_status():
    """测试 GET /api/status"""
    try:
        r = requests.get('http://localhost:5000/api/status')
        success = r.status_code == 200 and r.json()['success']
        return log_test('GET /api/status', success, r.status_code, r.json())
    except Exception as e:
        return log_test('GET /api/status', False, 0, None, str(e))

def test_post_reset():
    """测试 POST /api/reset"""
    try:
        r = requests.post('http://localhost:5000/api/reset')
        success = r.status_code == 200 and r.json()['success']
        return log_test('POST /api/reset', success, r.status_code, r.json())
    except Exception as e:
        return log_test('POST /api/reset', False, 0, None, str(e))

def test_mode1_register():
    """测试模式1注册"""
    try:
        data = {'dev_id': '001122334455'}
        test_data_for_postman['mode1_register'] = data
        
        r = requests.post('http://localhost:5000/api/device/mode1/register', json=data)
        success = r.status_code == 200 and r.json()['success'] and r.json()['data']['registered']
        return log_test('POST /api/device/mode1/register', success, r.status_code, r.json())
    except Exception as e:
        return log_test('POST /api/device/mode1/register', False, 0, None, str(e))

def test_mode1_auth_success():
    """测试模式1认证 - 成功场景"""
    try:
        data = {
            'dev_id': '001122334455',
            'rff_score': 0.85,
            'rff_confidence': 0.90,
            'snr': 20.0
        }
        test_data_for_postman['mode1_auth_success'] = data
        
        r = requests.post('http://localhost:5000/api/device/mode1/authenticate', json=data)
        result = r.json()
        # 期望认证成功，但实际可能失败 - 记录实际结果
        success = r.status_code == 200 and result['success']
        if success and 'data' in result and not result['data']['authenticated']:
            error_msg = f"认证失败: {result['data'].get('reason', 'unknown')}"
            return log_test('POST /api/device/mode1/authenticate (成功场景)', False, r.status_code, result, error_msg)
        return log_test('POST /api/device/mode1/authenticate (成功场景)', success, r.status_code, result)
    except Exception as e:
        return log_test('POST /api/device/mode1/authenticate (成功场景)', False, 0, None, str(e))

def test_mode1_auth_fail():
    """测试模式1认证 - 失败场景"""
    try:
        data = {
            'dev_id': '001122334455',
            'rff_score': 0.5,
            'rff_confidence': 0.7,
            'snr': 20.0
        }
        test_data_for_postman['mode1_auth_fail'] = data
        
        r = requests.post('http://localhost:5000/api/device/mode1/authenticate', json=data)
        result = r.json()
        # 期望认证失败
        success = r.status_code == 200 and result['success'] and not result['data']['authenticated']
        return log_test('POST /api/device/mode1/authenticate (失败场景)', success, r.status_code, result)
    except Exception as e:
        return log_test('POST /api/device/mode1/authenticate (失败场景)', False, 0, None, str(e))

def test_mode1_auth_low_snr():
    """测试模式1认证 - 低SNR场景"""
    try:
        data = {
            'dev_id': '001122334455',
            'rff_score': 0.85,
            'rff_confidence': 0.90,
            'snr': 5.0
        }
        test_data_for_postman['mode1_auth_low_snr'] = data
        
        r = requests.post('http://localhost:5000/api/device/mode1/authenticate', json=data)
        result = r.json()
        success = r.status_code == 200 and result['success']
        return log_test('POST /api/device/mode1/authenticate (低SNR)', success, r.status_code, result)
    except Exception as e:
        return log_test('POST /api/device/mode1/authenticate (低SNR)', False, 0, None, str(e))

def test_mode2_flow():
    """测试模式2完整流程"""
    session_data = {}
    
    # 步骤1: 创建认证请求
    try:
        np.random.seed(42)
        csi = np.random.randn(6, 62).tolist()
        
        data = {
            'dev_id': '001122334455',
            'dst_mac': 'AABBCCDDEEFF',
            'csi': csi,
            'seq': 1,
            'csi_id': 12345
        }
        test_data_for_postman['mode2_create_request'] = data
        
        r = requests.post('http://localhost:5000/api/device/mode2/create_request', json=data)
        result = r.json()
        
        if not (r.status_code == 200 and result['success']):
            log_test('POST /api/device/mode2/create_request', False, r.status_code, result)
            return
        
        log_test('POST /api/device/mode2/create_request', True, r.status_code, result)
        
        # 保存返回数据
        session_data['auth_req'] = result['data']['auth_req']
        session_data['session_key'] = result['data']['session_key']
        session_data['feature_key'] = result['data']['feature_key']
        session_data['epoch'] = result['data']['epoch']
        session_data['csi'] = csi
        
    except Exception as e:
        log_test('POST /api/device/mode2/create_request', False, 0, None, str(e))
        return
    
    # 步骤2: 验证端注册设备
    try:
        data = {
            'dev_id': '001122334455',
            'feature_key': session_data['feature_key'],
            'epoch': session_data['epoch']
        }
        test_data_for_postman['mode2_verifier_register'] = data
        
        r = requests.post('http://localhost:5000/api/verifier/mode2/register', json=data)
        result = r.json()
        
        success = r.status_code == 200 and result['success'] and result['data']['registered']
        log_test('POST /api/verifier/mode2/register', success, r.status_code, result)
        
        if not success:
            return
            
    except Exception as e:
        log_test('POST /api/verifier/mode2/register', False, 0, None, str(e))
        return
    
    # 步骤3: 验证端验证请求
    try:
        data = {
            'auth_req': session_data['auth_req'],
            'csi': session_data['csi']
        }
        test_data_for_postman['mode2_verifier_verify'] = data
        
        r = requests.post('http://localhost:5000/api/verifier/mode2/verify', json=data)
        result = r.json()
        
        success = r.status_code == 200 and result['success']
        
        if success and result['data']['authenticated']:
            # 验证session_key是否匹配
            if result['data']['session_key'] == session_data['session_key']:
                log_test('POST /api/verifier/mode2/verify', True, r.status_code, result)
                print(f"  [OK] Session Key 匹配")
            else:
                log_test('POST /api/verifier/mode2/verify', False, r.status_code, result, 
                        "Session Key 不匹配")
        else:
            error_msg = result['data'].get('reason', 'unknown') if result['success'] else 'Request failed'
            log_test('POST /api/verifier/mode2/verify', False, r.status_code, result, error_msg)
            
    except Exception as e:
        log_test('POST /api/verifier/mode2/verify', False, 0, None, str(e))

def generate_report():
    """生成测试报告"""
    print("\n" + "="*80)
    print("API测试报告")
    print("="*80)
    
    total = len(test_results)
    passed = sum(1 for r in test_results if r['success'])
    failed = total - passed
    
    print(f"\n总测试数: {total}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"成功率: {passed/total*100:.1f}%")
    
    if failed > 0:
        print("\n失败的测试:")
        for r in test_results:
            if not r['success']:
                print(f"  - {r['name']}")
                if r['error']:
                    print(f"    错误: {r['error']}")
                if r['response'] and 'data' in r['response']:
                    reason = r['response']['data'].get('reason')
                    if reason:
                        print(f"    原因: {reason}")
    
    # 保存详细报告
    with open('API_TEST_REPORT.md', 'w', encoding='utf-8') as f:
        f.write("# API接口测试报告\n\n")
        f.write(f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**测试结果**: {passed}/{total} 通过\n\n")
        
        f.write("## 测试详情\n\n")
        for i, r in enumerate(test_results, 1):
            status = "[OK]" if r['success'] else "[FAIL]"
            f.write(f"### {i}. {r['name']} {status}\n\n")
            f.write(f"- **状态码**: {r['status_code']}\n")
            f.write(f"- **时间**: {r['timestamp']}\n")
            
            if r['error']:
                f.write(f"- **错误**: {r['error']}\n")
            
            if r['response']:
                f.write(f"\n**响应**:\n```json\n{json.dumps(r['response'], indent=2, ensure_ascii=False)}\n```\n")
            
            f.write("\n")
        
        # 记录需要修复的问题
        if failed > 0:
            f.write("## 需要修复的问题\n\n")
            for r in test_results:
                if not r['success']:
                    f.write(f"### {r['name']}\n\n")
                    if r['error']:
                        f.write(f"**错误信息**: {r['error']}\n\n")
                    if r['response'] and 'data' in r['response']:
                        reason = r['response']['data'].get('reason')
                        if reason:
                            f.write(f"**失败原因**: {reason}\n\n")
    
    print(f"\n详细报告已保存到: API_TEST_REPORT.md")
    
    # 保存测试数据
    with open('test_data_for_postman.json', 'w', encoding='utf-8') as f:
        json.dump(test_data_for_postman, f, indent=2, ensure_ascii=False)
    
    print(f"测试数据已保存到: test_data_for_postman.json")

if __name__ == '__main__':
    print("="*80)
    print("开始API接口测试")
    print("="*80)
    print()
    
    # 测试管理接口
    print("【阶段1: 管理接口】")
    test_get_status()
    test_post_reset()
    print()
    
    # 测试模式1
    print("【阶段2: 模式1 - RFF快速认证】")
    test_mode1_register()
    test_mode1_auth_success()
    # 失败场景测试前需要重新注册（因为之前的认证可能影响状态）
    test_mode1_auth_fail()
    test_mode1_auth_low_snr()
    print()
    
    # 测试模式2
    print("【阶段3: 模式2 - 强认证】")
    test_mode2_flow()
    print()
    
    # 生成报告
    generate_report()

