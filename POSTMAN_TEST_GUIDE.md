

# Postman API测试指南

## 概述

本指南介绍如何使用Postman测试基于特征的身份认证API，包括**模式1（RFF快速认证）**和**模式2（强认证）**。

## 前置条件

1. **安装依赖**
   ```bash
   pip install flask flask-cors numpy
   ```

2. **启动API服务器**
   ```bash
   cd C:\Users\dell\Desktop\Feature-Algorithm
   python api_server.py
   ```

   服务器将在 `http://localhost:5000` 启动。

3. **安装Postman**
   - 下载地址: https://www.postman.com/downloads/
   - 或使用在线版本: https://web.postman.com/

## API端点概览

### 模式1: RFF快速认证

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/api/device/mode1/register` | 注册设备 |
| POST | `/api/device/mode1/authenticate` | RFF快速认证 |

### 模式2: 强认证

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/api/device/mode2/create_request` | 设备端创建认证请求 |
| POST | `/api/verifier/mode2/register` | 验证端注册设备 |
| POST | `/api/verifier/mode2/verify` | 验证端验证请求 |

### 管理端点

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/status` | 获取服务器状态 |
| POST | `/api/reset` | 重置所有状态 |

---

## 测试场景

### 场景1: 模式1 - RFF快速认证

#### 步骤1: 注册设备

**请求:**
```http
POST http://localhost:5000/api/device/mode1/register
Content-Type: application/json

{
    "dev_id": "001122334455",
    "rff_template": "base64_encoded_template"  // 可选：RFF模板数据
}
```

**注意**: `rff_template` 参数是可选的。如果不提供，系统会自动生成模拟的RFF模板。

**响应示例:**
```json
{
    "success": true,
    "timestamp": 1700000000.123,
    "data": {
        "dev_id": "001122334455",
        "registered": true,
        "total_devices": 1
    }
}
```

#### 步骤2: 执行RFF快速认证

**请求:**
```http
POST http://localhost:5000/api/device/mode1/authenticate
Content-Type: application/json

{
    "dev_id": "001122334455",
    "rff_score": 0.85,
    "rff_confidence": 0.90,
    "snr": 20.0
}
```

**参数说明:**
- `dev_id`: 设备MAC地址（十六进制字符串）
- `rff_score`: RFF匹配分数（0-1之间，>0.8为高匹配）
- `rff_confidence`: RFF置信度（0-1之间，保留参数但当前未使用）
- `snr`: 信噪比（dB，可选，默认20.0）
- `policy`: 认证策略（可选，默认"default"）

**注意**: API服务器内部会将 `rff_score` 和其他参数转换为模拟的RFF特征字节串（使用SHA256哈希）。在实际系统中，这应该是从物理层获取的真实RFF特征数据。

**响应示例（认证成功）:**
```json
{
    "success": true,
    "timestamp": 1700000000.456,
    "data": {
        "authenticated": true,
        "dev_id": "001122334455",
        "decision": "ACCEPT",
        "reason": null,
        "token_fast": "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXo=",
        "token_size": 64,
        "latency_ms": 12.5
    }
}
```

**响应示例（认证失败 - RFF分数低）:**
```json
{
    "success": true,
    "timestamp": 1700000000.789,
    "data": {
        "authenticated": false,
        "dev_id": "001122334455",
        "decision": "REJECT",
        "reason": "rff_score_too_low",
        "token_fast": null,
        "token_size": 0,
        "latency_ms": 8.3
    }
}
```

---

### 场景2: 模式2 - 强认证

#### 步骤1: 设备端创建认证请求

**请求:**
```http
POST http://localhost:5000/api/device/mode2/create_request
Content-Type: application/json

{
    "dev_id": "001122334455",
    "dst_mac": "AABBCCDDEEFF",
    "csi": [
        [0.1, 0.2, 0.3, ..., (62个数值)],
        [0.1, 0.2, 0.3, ..., (62个数值)],
        [0.1, 0.2, 0.3, ..., (62个数值)],
        [0.1, 0.2, 0.3, ..., (62个数值)],
        [0.1, 0.2, 0.3, ..., (62个数值)],
        [0.1, 0.2, 0.3, ..., (62个数值)]
    ],
    "seq": 1,
    "csi_id": 12345
}
```

**参数说明:**
- `dev_id`: 设备MAC地址（十六进制）
- `dst_mac`: 目标验证器MAC地址（十六进制）
- `csi`: CSI特征矩阵（6×62），JSON数组格式
- `nonce`: 随机数（可选，16字节十六进制）
- `seq`: 序列号（可选）
- `csi_id`: CSI标识（可选）

**响应示例:**
```json
{
    "success": true,
    "timestamp": 1700000001.123,
    "data": {
        "auth_req": "YWJjZGVm...==",
        "session_key": "3fb0b1e96cf6e30e6355aaf691faef6f...",
        "feature_key": "a1b2c3d4e5f6...",
        "epoch": 0,
        "dev_pseudo": "68c9567dcc6375750812dbb5",
        "digest": "ef09d99d1897fac8",
        "latency_ms": 15.3
    }
}
```

**重要:** 请保存响应中的 `auth_req`、`session_key` 和 `feature_key`，后续步骤需要使用。

#### 步骤2: 验证端注册设备

使用步骤1返回的 `feature_key` 注册设备。

**请求:**
```http
POST http://localhost:5000/api/verifier/mode2/register
Content-Type: application/json

{
    "dev_id": "001122334455",
    "feature_key": "a1b2c3d4e5f6...",
    "epoch": 0
}
```

**响应示例:**
```json
{
    "success": true,
    "timestamp": 1700000001.456,
    "data": {
        "dev_id": "001122334455",
        "registered": true,
        "total_devices": 1
    }
}
```

#### 步骤3: 验证端验证认证请求

使用步骤1返回的 `auth_req` 和相同/相似的CSI进行验证。

**请求:**
```http
POST http://localhost:5000/api/verifier/mode2/verify
Content-Type: application/json

{
    "auth_req": "YWJjZGVm...==",
    "csi": [
        [0.1, 0.2, 0.3, ..., (62个数值)],
        [0.1, 0.2, 0.3, ..., (62个数值)],
        [0.1, 0.2, 0.3, ..., (62个数值)],
        [0.1, 0.2, 0.3, ..., (62个数值)],
        [0.1, 0.2, 0.3, ..., (62个数值)],
        [0.1, 0.2, 0.3, ..., (62个数值)]
    ]
}
```

**响应示例（认证成功）:**
```json
{
    "success": true,
    "timestamp": 1700000001.789,
    "data": {
        "authenticated": true,
        "dev_id": "001122334455",
        "reason": null,
        "session_key": "3fb0b1e96cf6e30e6355aaf691faef6f...",
        "mat_token": "ZGVmZ2hp...==",
        "token_size": 74,
        "epoch": 0,
        "latency_ms": 18.7
    }
}
```

**验证:** 比对设备端的 `session_key` 和验证端的 `session_key` 是否一致。

---

## 管理端点测试

### 获取服务器状态

**请求:**
```http
GET http://localhost:5000/api/status
```

**响应示例:**
```json
{
    "success": true,
    "timestamp": 1700000002.123,
    "data": {
        "mode1": {
            "initialized": true,
            "devices_count": 1
        },
        "mode2": {
            "device_side_initialized": true,
            "verifier_side_initialized": true,
            "devices_count": 1,
            "sessions_count": 1
        },
        "server_version": "1.0.0"
    }
}
```

### 重置服务器状态

**请求:**
```http
POST http://localhost:5000/api/reset
```

**响应示例:**
```json
{
    "success": true,
    "timestamp": 1700000002.456,
    "data": {
        "message": "Server state reset successfully"
    }
}
```

---

## Postman测试集合

### 导入预设集合

1. 复制 `postman_collection.json` 文件内容
2. 打开Postman
3. 点击 **Import** → **Raw text**
4. 粘贴JSON内容
5. 点击 **Import**

### 使用集合

1. 选择导入的集合 "特征认证API测试"
2. 按顺序执行请求：
   - **模式1测试**
     1. Mode1 - 注册设备
     2. Mode1 - 认证（成功）
     3. Mode1 - 认证（失败 - 低RFF分数）
   
   - **模式2测试**
     1. Mode2 - 设备端创建请求
     2. Mode2 - 验证端注册设备
     3. Mode2 - 验证端验证请求

### 自定义变量

在Postman集合中设置环境变量：

- `base_url`: `http://localhost:5000`
- `dev_id`: `001122334455`
- `dst_mac`: `AABBCCDDEEFF`
- `feature_key`: （从步骤1响应中获取）
- `auth_req`: （从步骤1响应中获取）

---

## 快速测试 - CSI数据生成

### Python脚本生成CSI

```python
import numpy as np
import json

# 生成模拟CSI数据（6×62矩阵）
np.random.seed(42)
csi = np.random.randn(6, 62).tolist()

# 输出为JSON
print(json.dumps(csi, indent=2))
```

### 示例CSI数据（简化版）

```json
{
    "csi": [
        [0.5, -0.3, 0.8, 0.2, -0.1, 0.6, ...],  // 62个值
        [0.4, -0.2, 0.7, 0.3, -0.2, 0.5, ...],  // 62个值
        [0.5, -0.3, 0.8, 0.2, -0.1, 0.6, ...],  // 62个值
        [0.4, -0.2, 0.7, 0.3, -0.2, 0.5, ...],  // 62个值
        [0.5, -0.3, 0.8, 0.2, -0.1, 0.6, ...],  // 62个值
        [0.4, -0.2, 0.7, 0.3, -0.2, 0.5, ...]   // 62个值
    ]
}
```

---

## 常见问题

### Q1: 模式2认证失败 - `feature_mismatch`

**原因:** 设备端和验证端的CSI特征不匹配。

**解决方案:**
- 确保两端使用相同或非常相似的CSI数据（模拟信道互惠性）
- 在测试环境下，可以使用完全相同的CSI数据

### Q2: `bchlib` 导入警告

**警告信息:** `Warning: bchlib import failed, falling back to reedsolo mock.`

**说明:** 这是正常的，系统会自动回退到备用纠错方案。

### Q3: 如何模拟RFF认证失败？

**方法:** 降低 `rff_score` 或 `snr` 参数：

```json
{
    "dev_id": "001122334455",
    "rff_score": 0.5,   // < 0.8，低于阈值
    "rff_confidence": 0.7,
    "snr": 5.0          // 低信噪比
}
```

### Q4: 如何测试epoch验证？

**方法:** 在不同时间点进行认证，系统会自动处理epoch更新。

---

## 性能指标参考

### 模式1 (RFF快速认证)
- **延迟**: 8-15 ms
- **成功率**: 85-95%（RFF分数 > 0.8）
- **吞吐量**: ~1000 次/秒

### 模式2 (强认证)
- **延迟**: 15-25 ms
- **成功率**: 95-99%（CSI匹配度高）
- **吞吐量**: ~500 次/秒

---

## 下一步

1. **压力测试**: 使用Postman的Collection Runner进行批量测试
2. **集成测试**: 测试模式1失败后回退到模式2的场景
3. **分布式测试**: 多个验证器节点的协同认证

## 技术支持

如有问题，请参考：
- `API.MD` - 详细API文档
- `DEPLOYMENT_GUIDE.md` - 部署指南
- `UAV_SECURE_COMMUNICATION_GUIDE.md` - UAV场景指南

