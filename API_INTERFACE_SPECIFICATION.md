# 基于特征的身份认证 - API接口规范文档

## 文档版本
- **版本**: v1.0.0
- **更新日期**: 2025-11-20
- **API服务器**: `api_server.py`
- **Postman集合**: `postman_collection.json`

---

## 通用说明

### 请求格式
- **Content-Type**: `application/json`
- **编码**: UTF-8

### 响应格式
所有接口均返回统一的JSON格式：

```json
{
  "success": true,           // boolean - 请求是否成功
  "timestamp": 1763637369.46, // float - Unix时间戳
  "data": { ... },           // object - 成功时返回的数据
  "error": "..."             // string - 失败时返回的错误信息
}
```

### 数据类型约定
- **MAC地址**: 12位十六进制字符串，如 `"001122334455"` 或 `"AABBCCDDEEFF"`
- **密钥/哈希**: 十六进制字符串，如 `"a1b2c3d4..."` (长度视具体字段而定)
- **Base64数据**: Base64编码字符串，如 `"YWJjZGVm..."`
- **CSI数据**: 二维浮点数组 `[[float, ...], ...]` 或 Base64编码的numpy数组

---

## 模式1: RFF快速认证

### 1. POST /api/device/mode1/register
**功能**: 在模式1中注册设备

#### 请求参数 (Request Body)
```json
{
  "dev_id": "001122334455",           // string - 设备MAC地址（必需）
  "rff_template": "YWJjZGVm..."       // string - RFF模板Base64编码（可选）
}
```

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `dev_id` | string | ✓ | 6字节MAC地址的十六进制表示，如 "001122334455" |
| `rff_template` | string | ✗ | RFF模板数据的Base64编码，省略时系统自动生成 |

#### 响应参数 (Response Body)
```json
{
  "success": true,
  "timestamp": 1763637369.467,
  "data": {
    "dev_id": "001122334455",        // string - 已注册的设备MAC地址
    "registered": true,              // boolean - 是否注册成功
    "total_devices": 1               // integer - 当前已注册设备总数
  }
}
```

| 字段路径 | 类型 | 说明 |
|----------|------|------|
| `success` | boolean | 请求是否成功 |
| `timestamp` | float | Unix时间戳（秒） |
| `data.dev_id` | string | 已注册的设备MAC地址（十六进制，12字符） |
| `data.registered` | boolean | 注册结果，true表示成功 |
| `data.total_devices` | integer | 模式1中当前已注册的设备总数 |

#### Postman测试断言
```javascript
pm.expect(jsonData.success).to.be.true;
pm.expect(jsonData.data.registered).to.be.true;
```

---

### 2. POST /api/device/mode1/authenticate
**功能**: 使用RFF特征进行快速认证

#### 请求参数 (Request Body)
```json
{
  "dev_id": "001122334455",          // string - 设备MAC地址（必需）
  "rff_score": 0.85,                 // number - RFF匹配分数 0.0-1.0（必需）
  "rff_confidence": 0.90,            // number - RFF置信度 0.0-1.0（可选，保留字段）
  "snr": 20.0,                       // number - 信噪比（dB）（可选，默认20.0）
  "policy": "default"                // string - 认证策略（可选，默认"default"）
}
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `dev_id` | string | ✓ | - | 6字节MAC地址的十六进制表示 |
| `rff_score` | number | ✓ | - | RFF匹配分数，范围 [0.0, 1.0] |
| `rff_confidence` | number | ✗ | 0.0 | RFF置信度（保留字段，当前未使用） |
| `snr` | number | ✗ | 20.0 | 信噪比（单位：dB） |
| `policy` | string | ✗ | "default" | 认证策略名称 |

#### 响应参数 (Response Body)

**认证成功时**:
```json
{
  "success": true,
  "timestamp": 1763637370.123,
  "data": {
    "authenticated": true,           // boolean - 认证结果
    "dev_id": "001122334455",        // string - 设备MAC地址
    "decision": "ACCEPT",            // string - 决策结果："ACCEPT" 或 "REJECT"
    "reason": null,                  // string|null - 失败原因（成功时为null）
    "token_fast": "YWJjZGVm...",     // string - TokenFast的Base64编码
    "token_size": 64,                // integer - Token字节大小
    "latency_ms": 0.52               // number - 处理延迟（毫秒）
  }
}
```

**认证失败时**:
```json
{
  "success": true,
  "timestamp": 1763637370.456,
  "data": {
    "authenticated": false,          // boolean - 认证结果
    "dev_id": "001122334455",        // string - 设备MAC地址
    "decision": "REJECT",            // string - 决策结果
    "reason": "rff_score_below_threshold",  // string - 失败原因
    "token_fast": null,              // null - 无Token
    "token_size": 0,                 // integer - Token大小为0
    "latency_ms": 0.48               // number - 处理延迟
  }
}
```

| 字段路径 | 类型 | 说明 |
|----------|------|------|
| `success` | boolean | 请求是否成功（注意：即使认证失败，success也为true） |
| `timestamp` | float | Unix时间戳（秒） |
| `data.authenticated` | boolean | 认证结果，true=通过，false=拒绝 |
| `data.dev_id` | string | 设备MAC地址（十六进制，12字符） |
| `data.decision` | string | 决策结果："ACCEPT"（接受）或 "REJECT"（拒绝） |
| `data.reason` | string \| null | 失败原因代码，如 "rff_failed", "device_not_registered", "rff_score_below_threshold" |
| `data.token_fast` | string \| null | TokenFast令牌的Base64编码（仅认证成功时有效） |
| `data.token_size` | integer | Token字节大小（失败时为0） |
| `data.latency_ms` | number | 服务器处理延迟，单位毫秒（保留2位小数） |

#### 失败原因代码 (reason)
- `device_not_registered`: 设备未注册
- `rff_failed`: RFF判定失败（rff_pass=False）
- `rff_score_below_threshold`: RFF分数低于阈值

#### Postman测试断言
```javascript
// 成功场景
pm.expect(jsonData.success).to.be.true;
pm.expect(jsonData.data.authenticated).to.be.true;
pm.expect(jsonData.data.decision).to.eql("ACCEPT");

// 失败场景
pm.expect(jsonData.data.authenticated).to.be.false;
pm.expect(jsonData.data.decision).to.eql("REJECT");
```

---

## 模式2: 强认证

### 3. POST /api/verifier/mode2/register
**功能**: 验证端注册设备

#### 请求参数 (Request Body)
```json
{
  "dev_id": "001122334455",          // string - 设备MAC地址（必需）
  "feature_key": "e5f6a7b8...",      // string - 特征密钥K（必需，64位十六进制）
  "epoch": 0                         // integer - Epoch编号（必需）
}
```

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `dev_id` | string | ✓ | 设备MAC地址（6字节，12位十六进制） |
| `feature_key` | string | ✓ | 特征密钥K（32字节，64位十六进制），从步骤3获取 |
| `epoch` | integer | ✓ | 时间窗编号，必须与设备端一致 |

#### 响应参数 (Response Body)
```json
{
  "success": true,
  "timestamp": 1763637372.567,
  "data": {
    "dev_id": "001122334455",        // string - 已注册的设备MAC地址
    "registered": true,              // boolean - 是否注册成功
    "total_devices": 1               // integer - 当前已注册设备总数
  }
}
```

| 字段路径 | 类型 | 说明 |
|----------|------|------|
| `success` | boolean | 请求是否成功 |
| `timestamp` | float | Unix时间戳（秒） |
| `data.dev_id` | string | 已注册的设备MAC地址（十六进制，12字符） |
| `data.registered` | boolean | 注册结果，true表示成功 |
| `data.total_devices` | integer | 模式2验证端已注册的设备总数 |

#### Postman测试断言
```javascript
pm.expect(jsonData.success).to.be.true;
pm.expect(jsonData.data.registered).to.be.true;
```

---

### 4. POST /api/device/mode2/create_request
**功能**: 设备端创建认证请求

#### 请求参数 (Request Body)
```json
{
  "dev_id": "001122334455",          // string - 设备MAC地址（必需）
  "dst_mac": "AABBCCDDEEFF",         // string - 验证端MAC地址（必需）
  "csi": [                           // array - CSI数据矩阵（必需）
    [0.5, -0.3, 0.8, ...],           // 62个浮点数
    [0.4, -0.2, 0.7, ...],           // 62个浮点数
    ...                              // 共6行
  ],
  "nonce": "1a2b3c4d...",            // string - 16字节随机数（可选，十六进制）
  "seq": 1,                          // integer - 序列号（可选，默认1）
  "csi_id": 12345                    // integer - CSI标识（可选，默认12345）
}
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `dev_id` | string | ✓ | - | 设备MAC地址（6字节，十六进制） |
| `dst_mac` | string | ✓ | - | 目标验证端MAC地址（6字节，十六进制） |
| `csi` | array | ✓ | - | CSI数据矩阵（6行×62列浮点数）或Base64编码的numpy数组 |
| `nonce` | string | ✗ | (随机生成) | 16字节随机数的十六进制表示（32字符） |
| `seq` | integer | ✗ | 1 | 序列号 |
| `csi_id` | integer | ✗ | 12345 | CSI测量标识符 |

#### 响应参数 (Response Body)
```json
{
  "success": true,
  "timestamp": 1763637371.234,
  "data": {
    "auth_req": "YWJjZGVm...",       // string - 序列化AuthReq的Base64编码
    "session_key": "a1b2c3d4...",    // string - 会话密钥Ks（32字节，64位十六进制）
    "feature_key": "e5f6a7b8...",    // string - 特征密钥K（32字节，64位十六进制）
    "epoch": 0,                      // integer - 当前时间窗编号
    "dev_pseudo": "ef32b80b85cc...", // string - 设备伪名（12字节，24位十六进制）
    "digest": "c9d0e1f2...",         // string - 配置摘要（32字节，64位十六进制）
    "latency_ms": 10.21              // number - 处理延迟（毫秒）
  }
}
```

| 字段路径 | 类型 | 长度 | 说明 |
|----------|------|------|------|
| `success` | boolean | - | 请求是否成功 |
| `timestamp` | float | - | Unix时间戳（秒） |
| `data.auth_req` | string | 可变 | AuthReq对象序列化后的Base64编码，需传递给验证端 |
| `data.session_key` | string | 64字符 | 会话密钥Ks的十六进制表示（32字节） |
| `data.feature_key` | string | 64字符 | 特征密钥K的十六进制表示（32字节），需用于注册 |
| `data.epoch` | integer | - | 当前时间窗编号（epoch） |
| `data.dev_pseudo` | string | 24字符 | 设备伪名的十六进制表示（12字节），用于隐私保护 |
| `data.digest` | string | 64字符 | 配置摘要的十六进制表示（32字节），用于配置一致性检查 |
| `data.latency_ms` | number | - | 服务器端处理延迟（毫秒，保留2位小数） |

#### Postman测试断言
```javascript
pm.expect(jsonData.success).to.be.true;
pm.expect(jsonData.data.auth_req).to.exist;
pm.expect(jsonData.data.session_key).to.exist;
pm.expect(jsonData.data.feature_key).to.exist;

// 保存到环境变量供后续使用
pm.environment.set("auth_req", jsonData.data.auth_req);
pm.environment.set("session_key", jsonData.data.session_key);
pm.environment.set("feature_key", jsonData.data.feature_key);
pm.environment.set("epoch", jsonData.data.epoch);
```

---

### 5. POST /api/verifier/mode2/verify
**功能**: 验证端验证认证请求

#### 请求参数 (Request Body)
```json
{
  "auth_req": "YWJjZGVm...",         // string - AuthReq的Base64编码（必需）
  "csi": [                           // array - CSI数据矩阵（必需）
    [0.5, -0.3, 0.8, ...],           // 62个浮点数
    [0.4, -0.2, 0.7, ...],           // 62个浮点数
    ...                              // 共6行
  ]
}
```

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `auth_req` | string | ✓ | 从步骤4获取的AuthReq的Base64编码 |
| `csi` | array | ✓ | 验证端测量的CSI数据（6行×62列浮点数）或Base64编码 |

**注意**: 验证端的CSI数据应与设备端的CSI数据具有信道互惠性，即在相同时间、相同频段测量的双向信道特征应该相似。

#### 响应参数 (Response Body)

**验证成功时**:
```json
{
  "success": true,
  "timestamp": 1763637373.890,
  "data": {
    "authenticated": true,           // boolean - 认证结果
    "dev_id": "001122334455",        // string - 设备MAC地址
    "reason": null,                  // string|null - 失败原因（成功时为null）
    "session_key": "a1b2c3d4...",    // string - 会话密钥Ks（64位十六进制）
    "mat_token": "YWJjZGVm...",      // string - MAT令牌的Base64编码
    "token_size": 74,                // integer - Token字节大小
    "epoch": 0,                      // integer - Epoch编号
    "latency_ms": 5.31               // number - 处理延迟（毫秒）
  }
}
```

**验证失败时**:
```json
{
  "success": true,
  "timestamp": 1763637373.890,
  "data": {
    "authenticated": false,          // boolean - 认证结果
    "dev_id": "001122334455",        // string - 设备MAC地址（或"unknown"）
    "reason": "tag_mismatch",        // string - 失败原因
    "session_key": null,             // null - 无会话密钥
    "mat_token": null,               // null - 无Token
    "token_size": 0,                 // integer - Token大小为0
    "epoch": 0,                      // integer - Epoch编号
    "latency_ms": 5.18               // number - 处理延迟
  }
}
```

| 字段路径 | 类型 | 说明 |
|----------|------|------|
| `success` | boolean | 请求是否成功（注意：即使认证失败，success也为true） |
| `timestamp` | float | Unix时间戳（秒） |
| `data.authenticated` | boolean | 认证结果，true=通过，false=拒绝 |
| `data.dev_id` | string | 设备MAC地址（十六进制，12字符）或"unknown"（无法定位设备时） |
| `data.reason` | string \| null | 失败原因代码，成功时为null |
| `data.session_key` | string \| null | 会话密钥Ks的十六进制表示（32字节，64字符），仅认证成功时有效 |
| `data.mat_token` | string \| null | MAT令牌的Base64编码，仅认证成功时有效 |
| `data.token_size` | integer | Token字节大小（失败时为0） |
| `data.epoch` | integer | 时间窗编号 |
| `data.latency_ms` | number | 服务器处理延迟（毫秒，保留2位小数） |

#### 失败原因代码 (reason)
- `device_not_registered`: 设备未在验证端注册
- `epoch_out_of_range`: Epoch超出有效范围
- `feature_mismatch`: 特征不匹配（BCH解码失败）
- `digest_mismatch`: 配置摘要不一致
- `tag_mismatch`: 认证标签校验失败

#### Postman测试断言
```javascript
pm.expect(jsonData.success).to.be.true;
pm.expect(jsonData.data.authenticated).to.be.true;

// 验证session_key是否与设备端一致
var device_session_key = pm.environment.get("session_key");
pm.expect(jsonData.data.session_key).to.eql(device_session_key);
```

---

## 管理接口

### 6. GET /api/status
**功能**: 获取服务器当前状态

#### 请求参数
无

#### 响应参数 (Response Body)
```json
{
  "success": true,
  "timestamp": 1763637374.123,
  "data": {
    "mode1": {
      "initialized": true,           // boolean - 模式1是否已初始化
      "devices_count": 2             // integer - 已注册设备数量
    },
    "mode2": {
      "device_side_initialized": true,      // boolean - 设备端是否已初始化
      "verifier_side_initialized": true,    // boolean - 验证端是否已初始化
      "devices_count": 1,                   // integer - 已注册设备数量
      "sessions_count": 1                   // integer - 活跃会话数量
    },
    "server_version": "1.0.0"        // string - 服务器版本号
  }
}
```

| 字段路径 | 类型 | 说明 |
|----------|------|------|
| `success` | boolean | 请求是否成功 |
| `timestamp` | float | Unix时间戳（秒） |
| `data.mode1.initialized` | boolean | 模式1认证器是否已初始化 |
| `data.mode1.devices_count` | integer | 模式1中已注册的设备数量 |
| `data.mode2.device_side_initialized` | boolean | 模式2设备端是否已初始化 |
| `data.mode2.verifier_side_initialized` | boolean | 模式2验证端是否已初始化 |
| `data.mode2.devices_count` | integer | 模式2验证端已注册的设备数量 |
| `data.mode2.sessions_count` | integer | 模式2设备端活跃会话数量 |
| `data.server_version` | string | API服务器版本号 |

---

### 7. POST /api/reset
**功能**: 重置所有服务器状态

#### 请求参数
无

#### 响应参数 (Response Body)
```json
{
  "success": true,
  "timestamp": 1763637375.456,
  "data": {
    "message": "Server state reset successfully"  // string - 操作结果消息
  }
}
```

| 字段路径 | 类型 | 说明 |
|----------|------|------|
| `success` | boolean | 请求是否成功 |
| `timestamp` | float | Unix时间戳（秒） |
| `data.message` | string | 操作结果消息 |

**注意**: 此操作将清除所有已注册的设备、会话和令牌。

---

## 错误处理

### HTTP状态码
- `200 OK`: 请求成功（包括认证失败的情况，因为请求本身成功处理）
- `400 Bad Request`: 请求参数错误或格式不正确
- `500 Internal Server Error`: 服务器内部错误

### 错误响应格式
```json
{
  "success": false,
  "timestamp": 1763637376.789,
  "error": "Invalid dev_id format (expected hex or base64)"
}
```

### 常见错误消息
- `"Invalid dev_id format (expected hex or base64)"`: MAC地址格式错误
- `"dev_id is required"`: 缺少必需参数dev_id
- `"Invalid CSI format (expected base64-encoded numpy array)"`: CSI数据格式错误
- `"Mode1 not initialized. Please register a device first."`: 模式1未初始化
- `"Mode2 verifier not initialized. Please register a device first."`: 模式2验证端未初始化

---

## 完整测试流程

### 模式1测试流程
1. **注册设备**: `POST /api/device/mode1/register`
2. **认证（成功）**: `POST /api/device/mode1/authenticate` (高RFF分数)
3. **认证（失败）**: `POST /api/device/mode1/authenticate` (低RFF分数)
4. **检查状态**: `GET /api/status`

### 模式2测试流程
1. **设备端创建请求**: `POST /api/device/mode2/create_request` → 获取 `feature_key`, `auth_req`, `session_key`
2. **验证端注册设备**: `POST /api/verifier/mode2/register` (使用步骤1的`feature_key`)
3. **验证端验证请求**: `POST /api/verifier/mode2/verify` (使用步骤1的`auth_req`)
4. **验证会话密钥**: 比对步骤1和步骤3的`session_key`是否一致
5. **检查状态**: `GET /api/status`

---

## 与Postman集合的一致性验证

| 接口 | 文档完整性 | 参数一致性 | 返回值一致性 | 测试断言一致性 | 状态 |
|------|-----------|-----------|-------------|---------------|------|
| POST /api/device/mode1/register | ✓ | ✓ | ✓ | ✓ | 通过 |
| POST /api/device/mode1/authenticate | ✓ | ✓ | ✓ | ✓ | 通过 |
| POST /api/device/mode2/create_request | ✓ | ✓ | ✓ | ✓ | 通过 |
| POST /api/verifier/mode2/register | ✓ | ✓ | ✓ | ✓ | 通过 |
| POST /api/verifier/mode2/verify | ✓ | ✓ | ✓ | ✓ | 通过 |
| GET /api/status | ✓ | ✓ | ✓ | ✓ | 通过 |
| POST /api/reset | ✓ | ✓ | ✓ | ✓ | 通过 |

**验证结果**: 所有接口文档与Postman集合完全一致 ✓

---

## 附录

### 数据长度参考
- **MAC地址**: 6字节 = 12位十六进制字符
- **Nonce**: 16字节 = 32位十六进制字符
- **特征密钥(K)**: 32字节 = 64位十六进制字符
- **会话密钥(Ks)**: 32字节 = 64位十六进制字符
- **设备伪名(DevPseudo)**: 12字节 = 24位十六进制字符
- **配置摘要(digest)**: 32字节 = 64位十六进制字符
- **TokenFast**: 约64字节（可变）
- **MAT Token**: 约74字节（可变）

### CSI数据格式
- **维度**: 6行 × 62列
- **数据类型**: 浮点数（float64）
- **JSON表示**: 二维数组 `[[float, ...], ...]`
- **Base64表示**: numpy数组序列化后的Base64编码

---

**文档结束**

