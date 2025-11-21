# API接口测试报告

**测试时间**: 2025-11-21 15:32:04

**测试结果**: 9/9 通过

## 测试详情

### 1. GET /api/status [OK]

- **状态码**: 200
- **时间**: 2025-11-21T15:31:48.354626

**响应**:
```json
{
  "data": {
    "mode1": {
      "devices_count": 0,
      "initialized": false
    },
    "mode2": {
      "device_side_initialized": false,
      "devices_count": 0,
      "sessions_count": 0,
      "verifier_side_initialized": false
    },
    "server_version": "1.0.0"
  },
  "success": true,
  "timestamp": 1763710308.3516173
}
```

### 2. POST /api/reset [OK]

- **状态码**: 200
- **时间**: 2025-11-21T15:31:50.405515

**响应**:
```json
{
  "data": {
    "message": "Server state reset successfully"
  },
  "success": true,
  "timestamp": 1763710310.4034464
}
```

### 3. POST /api/device/mode1/register [OK]

- **状态码**: 200
- **时间**: 2025-11-21T15:31:52.462391

**响应**:
```json
{
  "data": {
    "dev_id": "001122334455",
    "registered": true,
    "total_devices": 1
  },
  "success": true,
  "timestamp": 1763710312.4596357
}
```

### 4. POST /api/device/mode1/authenticate (成功场景) [OK]

- **状态码**: 200
- **时间**: 2025-11-21T15:31:54.520220

**响应**:
```json
{
  "data": {
    "authenticated": true,
    "decision": "ACCEPT",
    "dev_id": "001122334455",
    "latency_ms": 1.99,
    "reason": null,
    "token_fast": "ABEiM0RVahUgaaYVIGkHZGVmYXVsdFgZG+E2rl2mw8OgLNZSl1Q=",
    "token_size": 38
  },
  "success": true,
  "timestamp": 1763710314.5179298
}
```

### 5. POST /api/device/mode1/authenticate (失败场景) [OK]

- **状态码**: 200
- **时间**: 2025-11-21T15:31:56.576477

**响应**:
```json
{
  "data": {
    "authenticated": false,
    "decision": "REJECT",
    "dev_id": "001122334455",
    "latency_ms": 0.81,
    "reason": "rff_failed",
    "token_fast": null,
    "token_size": 0
  },
  "success": true,
  "timestamp": 1763710316.5735857
}
```

### 6. POST /api/device/mode1/authenticate (低SNR) [OK]

- **状态码**: 200
- **时间**: 2025-11-21T15:31:58.627346

**响应**:
```json
{
  "data": {
    "authenticated": false,
    "decision": "REJECT",
    "dev_id": "001122334455",
    "latency_ms": 1.14,
    "reason": "rff_failed",
    "token_fast": null,
    "token_size": 0
  },
  "success": true,
  "timestamp": 1763710318.625399
}
```

### 7. POST /api/device/mode2/create_request [OK]

- **状态码**: 200
- **时间**: 2025-11-21T15:32:00.719338

**响应**:
```json
{
  "data": {
    "auth_req": "S28qAj8OJH3ZSXwLOTAAAAAAAACPZ+45ZuacmsHCKtLmkix0AQAAAAVNb2RlMgHvCdmdGJf6yOax4nBPFLCGHIwdvwjpcDc=",
    "dev_pseudo": "4b6f2a023f0e247dd9497c0b",
    "digest": "ef09d99d1897fac8",
    "epoch": 0,
    "feature_key": "d9a8c1e923e29fc1b650ad0a87f82770e5c35361f359554fd39f31e9edb4a20f",
    "latency_ms": 12.16,
    "session_key": "71d125e58605f71a05039ef9be0ee6d5ccddbca4898d0bb654126c1e851f1157"
  },
  "success": true,
  "timestamp": 1763710320.7167227
}
```

### 8. POST /api/verifier/mode2/register [OK]

- **状态码**: 200
- **时间**: 2025-11-21T15:32:02.776314

**响应**:
```json
{
  "data": {
    "dev_id": "001122334455",
    "registered": true,
    "total_devices": 1
  },
  "success": true,
  "timestamp": 1763710322.7744865
}
```

### 9. POST /api/verifier/mode2/verify [OK]

- **状态码**: 200
- **时间**: 2025-11-21T15:32:04.825539

**响应**:
```json
{
  "data": {
    "authenticated": true,
    "dev_id": "001122334455",
    "epoch": 0,
    "latency_ms": 5.1,
    "mat_token": "qrvM3e7/S28qAj8OJH3ZSXwLAAAAACwBAAC2jtrNNBn193WUmYPvJ2mTsFgdLGt6pULVmK1Qbmzc8MAAqE65ABgm/oQ/MXny8ZM=",
    "reason": null,
    "session_key": "71d125e58605f71a05039ef9be0ee6d5ccddbca4898d0bb654126c1e851f1157",
    "token_size": 74
  },
  "success": true,
  "timestamp": 1763710324.8236413
}
```

