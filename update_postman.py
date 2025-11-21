"""
更新postman_collection.json的请求数据
使用测试通过的真实数据
"""
import json

# 读取postman collection
with open('postman_collection.json', 'r', encoding='utf-8') as f:
    collection = json.load(f)

# 读取测试数据
with open('test_data_for_postman.json', 'r', encoding='utf-8') as f:
    test_data = json.load(f)

# 更新函数
def update_request_body(item, new_data):
    """更新请求体"""
    if 'request' in item and 'body' in item['request']:
        item['request']['body']['raw'] = json.dumps(new_data, indent=4, ensure_ascii=False)

# 遍历collection并更新
for group in collection['item']:
    if group['name'] == '模式1 - RFF快速认证':
        for item in group['item']:
            if '注册设备' in item['name']:
                update_request_body(item, test_data['mode1_register'])
                print(f"[OK] 更新: {item['name']}")
            elif 'RFF认证 - 成功' in item['name']:
                update_request_body(item, test_data['mode1_auth_success'])
                print(f"[OK] 更新: {item['name']}")
            elif 'RFF认证 - 失败（低RFF分数）' in item['name']:
                update_request_body(item, test_data['mode1_auth_fail'])
                print(f"[OK] 更新: {item['name']}")
            elif 'RFF认证 - 失败（低SNR）' in item['name']:
                update_request_body(item, test_data['mode1_auth_low_snr'])
                print(f"[OK] 更新: {item['name']}")
    
    elif group['name'] == '模式2 - 强认证':
        for item in group['item']:
            if '设备端创建认证请求' in item['name']:
                # Mode2的CSI数据保持原样（简化版）
                # 只更新基本参数
                data = {
                    "dev_id": test_data['mode2_create_request']['dev_id'],
                    "dst_mac": test_data['mode2_create_request']['dst_mac'],
                    "csi": test_data['mode2_create_request']['csi'],
                    "seq": test_data['mode2_create_request']['seq'],
                    "csi_id": test_data['mode2_create_request']['csi_id']
                }
                update_request_body(item, data)
                print(f"[OK] 更新: {item['name']}")
            # 注意：验证端的请求使用环境变量，不需要更新

# 保存更新后的collection
with open('postman_collection.json', 'w', encoding='utf-8') as f:
    json.dump(collection, f, indent='\t', ensure_ascii=False)

print("\n[完成] postman_collection.json已更新")

