# 基于特征的MAC身份认证API文档（UAV自组织网络版）

## 概述

本API提供简单易用的接口，用于UAV（无人机）自组织网络中的节点间身份认证，基于物理层特征（CSI）。API封装了三个模块（3.1特征加密、3.2认证、3.3同步）的复杂性，只需几行代码即可完成安全的点对点认证。

**适用场景**：
- 无人机群组自组织网络
- 对等分布式UAV通信
- 新UAV加入现有群组的认证
- UAV之间的相互认证

**核心特性**:
- ✅ 对等分布式：无中心化依赖，任意节点可相互认证
- ✅ 简单易用：一次API调用完成认证
- ✅ 高性能：认证延迟 < 15ms
- ✅ 物理层安全：基于CSI特征，难以伪造
- ✅ 隐私保护：使用DevPseudo保护真实身份
- ✅ 完整封装：隐藏底层复杂性

---

## 快速开始

### 安装依赖

```bash
pip install numpy
```

### 5分钟快速示例

```python
import secrets
import numpy as np
from authentication_api import FeatureBasedAuthenticationAPI

# 场景：新UAV要加入现有UAV群组

# 1. 新UAV节点：创建请求认证API
new_uav_api = FeatureBasedAuthenticationAPI.create_uav_node(
    node_mac=bytes.fromhex('001122334455'),  # 新UAV的MAC
    peer_mac=bytes.fromhex('AABBCCDDEEFF')   # 群组中验证节点的MAC
)

# 2. 群组中的验证UAV：创建验证API
verifier_uav_api = FeatureBasedAuthenticationAPI.create_peer_verifier(
    node_mac=bytes.fromhex('AABBCCDDEEFF'),  # 验证节点自己的MAC
    signing_key=secrets.token_bytes(32)       # 验证节点的签名密钥
)

# 3. 新UAV：测量CSI（实际应从无线网卡获取）
new_uav_csi = np.random.randn(6, 62)

# 4. 新UAV：生成认证请求
auth_request_bytes, uav_response = new_uav_api.authenticate(new_uav_csi)

# 5. 验证UAV：注册新UAV（首次需要，实际中应通过安全带外渠道）
verifier_uav_api.register_uav_node(
    node_mac=bytes.fromhex('001122334455'),
    feature_key=uav_response.feature_key,  # 从响应中获取
    epoch=uav_response.epoch
)

# 6. 验证UAV：测量CSI
verifier_csi = new_uav_csi.copy()  # 信道互惠性：应该测量到相似的CSI

# 7. 验证UAV：验证认证请求
verifier_response = verifier_uav_api.verify(auth_request_bytes, verifier_csi)

# 8. 检查结果
if verifier_response.success:
    print(f"✓ 新UAV认证成功！Session key: {verifier_response.session_key.hex()}")
    print(f"  MAT令牌大小: {len(verifier_response.token)} bytes")
else:
    print(f"✗ 认证失败: {verifier_response.reason}")
```

---

## API参考

### 1. 主入口类

#### `FeatureBasedAuthenticationAPI`

统一的认证API入口，提供创建UAV节点和验证节点API的工厂方法。

---

### 2. 创建UAV节点API（请求认证方）

#### `FeatureBasedAuthenticationAPI.create_uav_node()`

创建UAV节点认证API实例（用于请求认证）。

**方法签名**:
```python
@classmethod
def create_uav_node(
    cls,
    node_mac: bytes,
    peer_mac: bytes,
    epoch_period_ms: int = 30000,
    domain: str = "FeatureAuth",
    deterministic: bool = False
) -> UAVNodeAuthAPI
```

**参数说明**:

| 参数名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `node_mac` | bytes | 是 | - | 本UAV节点MAC地址，**必须为6字节** |
| `peer_mac` | bytes | 是 | - | 目标验证节点MAC地址，**必须为6字节** |
| `epoch_period_ms` | int | 否 | 30000 | Epoch周期（毫秒），建议10-60秒 |
| `domain` | str | 否 | "FeatureAuth" | 认证域标识，所有节点必须一致 |
| `deterministic` | bool | 否 | False | 确定性模式（**仅用于测试**） |

**返回值**:
- `UAVNodeAuthAPI`: UAV节点认证API实例

**异常**:
- `ValueError`: 如果MAC地址长度不是6字节

**示例**:
```python
uav_node_api = FeatureBasedAuthenticationAPI.create_uav_node(
    node_mac=bytes.fromhex('001122334455'),
    peer_mac=bytes.fromhex('AABBCCDDEEFF'),
    epoch_period_ms=30000  # 30秒epoch
)
```

---

### 3. 创建对等验证节点API（验证方）

#### `FeatureBasedAuthenticationAPI.create_peer_verifier()`

创建对等验证节点认证API实例（用于验证其他UAV）。

**方法签名**:
```python
@classmethod
def create_peer_verifier(
    cls,
    node_mac: bytes,
    signing_key: bytes,
    epoch_period_ms: int = 30000,
    beacon_interval_ms: int = 5000,
    domain: str = "FeatureAuth",
    deterministic: bool = False
) -> PeerVerifierAuthAPI
```

**参数说明**:

| 参数名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `node_mac` | bytes | 是 | - | 本验证节点MAC地址，**必须为6字节** |
| `signing_key` | bytes | 是 | - | 节点签名密钥，**必须为32字节** |
| `epoch_period_ms` | int | 否 | 30000 | Epoch周期（毫秒） |
| `beacon_interval_ms` | int | 否 | 5000 | 信标广播间隔（毫秒） |
| `domain` | str | 否 | "FeatureAuth" | 认证域标识 |
| `deterministic` | bool | 否 | False | 确定性模式（**仅用于测试**） |

**返回值**:
- `PeerVerifierAuthAPI`: 对等验证节点API实例

**异常**:
- `ValueError`: 如果MAC地址长度不是6字节或签名密钥长度不是32字节

**示例**:
```python
import secrets

peer_verifier_api = FeatureBasedAuthenticationAPI.create_peer_verifier(
    node_mac=bytes.fromhex('AABBCCDDEEFF'),
    signing_key=secrets.token_bytes(32),
    epoch_period_ms=30000,
    beacon_interval_ms=5000
)
```

---

### 4. UAV节点认证

#### `UAVNodeAuthAPI.authenticate()`

执行UAV节点认证，生成认证请求。

**方法签名**:
```python
def authenticate(
    self,
    csi_measurements: np.ndarray,
    nonce: Optional[bytes] = None
) -> Tuple[bytes, AuthenticationResponse]
```

**参数说明**:

| 参数名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `csi_measurements` | np.ndarray | 是 | - | CSI测量数据，shape为(M, D)，通常为(6, 62)<br>M=帧数，D=特征维度 |
| `nonce` | bytes | 否 | None | 随机数（16字节），None时自动生成 |

**返回值**:
- `Tuple[bytes, AuthenticationResponse]`:
  - `bytes`: 序列化的认证请求（需通过RF/WiFi发送给验证节点）
  - `AuthenticationResponse`: 认证响应对象

**异常**:
- `ValueError`: 如果CSI数据格式不正确或nonce长度不是16字节

**示例**:
```python
# 测量CSI（实际应从无线网卡获取）
csi_data = np.random.randn(6, 62)

# 生成认证请求
auth_request_bytes, response = uav_node_api.authenticate(csi_data)

if response.success:
    print(f"✓ 认证请求生成成功")
    print(f"  Session key: {response.session_key.hex()}")
    print(f"  Feature key: {response.feature_key.hex()}")
    print(f"  Epoch: {response.epoch}")

    # 通过RF/WiFi发送给验证节点
    send_to_peer(auth_request_bytes)
else:
    print(f"✗ 认证请求生成失败: {response.reason}")
```

---

### 5. 注册UAV节点

#### `PeerVerifierAuthAPI.register_uav_node()`

注册UAV节点（首次认证前需要）。

**方法签名**:
```python
def register_uav_node(
    self,
    node_mac: bytes,
    feature_key: bytes,
    epoch: int = 0
) -> bool
```

**参数说明**:

| 参数名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `node_mac` | bytes | 是 | - | UAV节点MAC地址（6字节） |
| `feature_key` | bytes | 是 | - | UAV节点特征密钥（32字节） |
| `epoch` | int | 否 | 0 | 注册时的epoch编号 |

**返回值**:
- `bool`: 是否注册成功

**注意事项**:
- ⚠️ 实际部署中，`feature_key`应通过**安全的带外渠道**获取（如预配置、信任链传递等）
- ⚠️ 测试时可以从`AuthenticationResponse.feature_key`获取

**示例**:
```python
# 方式1：从认证响应获取（仅用于测试/演示）
success = peer_verifier_api.register_uav_node(
    node_mac=bytes.fromhex('001122334455'),
    feature_key=uav_response.feature_key,
    epoch=uav_response.epoch
)

# 方式2：从安全配置获取（实际部署）
from secure_config import get_uav_feature_key
feature_key = get_uav_feature_key('001122334455')
success = peer_verifier_api.register_uav_node(
    node_mac=bytes.fromhex('001122334455'),
    feature_key=feature_key,
    epoch=0
)
```

---

### 6. 验证认证请求

#### `PeerVerifierAuthAPI.verify()`

验证UAV节点认证请求。

**方法签名**:
```python
def verify(
    self,
    auth_request_bytes: bytes,
    csi_measurements: np.ndarray
) -> AuthenticationResponse
```

**参数说明**:

| 参数名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `auth_request_bytes` | bytes | 是 | - | 序列化的认证请求（从UAV节点接收） |
| `csi_measurements` | np.ndarray | 是 | - | 验证节点测量的CSI数据，shape为(M, D)<br>**注意：应与请求节点测量相同信道（信道互惠性）** |

**返回值**:
- `AuthenticationResponse`: 认证响应对象

**异常**:
- `ValueError`: 如果CSI数据格式不正确

**示例**:
```python
# 接收认证请求
auth_request_bytes = receive_from_peer()

# 测量CSI
csi_data = np.random.randn(6, 62)

# 验证认证请求
response = peer_verifier_api.verify(auth_request_bytes, csi_data)

if response.success:
    print(f"✓✓✓ 认证成功！")
    print(f"  UAV节点ID: {response.node_id.hex()}")
    print(f"  Session key: {response.session_key.hex()}")
    print(f"  MAT令牌: {response.token.hex()}")

    # 发送MAT令牌给UAV节点
    send_to_peer(response.token)
else:
    print(f"✗✗✗ 认证失败")
    print(f"  原因: {response.reason}")
```

---

## 数据结构

### AuthenticationResponse

认证响应结果数据类。

**属性**:

| 属性名 | 类型 | 说明 |
|--------|------|------|
| `success` | bool | 认证是否成功 |
| `reason` | Optional[str] | 失败原因（成功时为None） |
| `session_key` | Optional[bytes] | 会话密钥（32字节，成功时返回） |
| `node_id` | Optional[bytes] | UAV节点MAC地址（6字节） |
| `epoch` | Optional[int] | 认证时的epoch编号 |
| `token` | Optional[bytes] | MAT令牌（成功时返回） |
| `latency_ms` | Optional[float] | 认证延迟（毫秒） |
| `feature_key` | Optional[bytes] | 特征密钥（32字节，用于注册） |

**方法**:
- `to_dict() -> Dict[str, Any]`: 转换为字典格式

---

## 常见失败原因

### 1. `device_not_registered`
- **原因**: UAV节点未在验证节点注册
- **解决**: 调用`register_uav_node()`注册节点

### 2. `epoch_out_of_range`
- **原因**: 认证请求的epoch已过期或超出容忍窗口
- **解决**: 检查两个节点的时间同步

### 3. `digest_mismatch`
- **原因**: 配置摘要不匹配（CSI特征不一致）
- **解决**:
  - 检查信道质量
  - 确保测量时间接近
  - 检查UAV间距离和移动速度

### 4. `tag_verification_failed`
- **原因**: 认证标签验证失败
- **解决**:
  - 检查feature_key是否正确
  - 检查domain参数是否一致

### 5. `feature_mismatch`
- **原因**: 特征密钥生成失败（BCH解码失败）
- **解决**:
  - 改善信道条件
  - 减少UAV移动速度
  - 增加CSI测量帧数

---

## 使用场景

### 场景1：新UAV加入群组

```python
# === 新UAV端 ===
new_uav_api = FeatureBasedAuthenticationAPI.create_uav_node(
    node_mac=NEW_UAV_MAC,
    peer_mac=VERIFIER_UAV_MAC
)

csi_data = measure_csi()
auth_request, response = new_uav_api.authenticate(csi_data)

# 通过RF发送认证请求
send_via_radio(auth_request)

# === 验证UAV端 ===
verifier_api = FeatureBasedAuthenticationAPI.create_peer_verifier(
    node_mac=VERIFIER_UAV_MAC,
    signing_key=VERIFIER_SIGNING_KEY
)

# 注册新UAV（如果是首次）
verifier_api.register_uav_node(NEW_UAV_MAC, feature_key, epoch)

# 接收并验证
auth_request = receive_via_radio()
csi_data = measure_csi()
result = verifier_api.verify(auth_request, csi_data)

if result.success:
    # 发送MAT令牌
    send_via_radio(result.token)
```

### 场景2：UAV间相互认证

```python
# UAV A和UAV B可以相互认证
# 每个UAV既有UAVNodeAuthAPI也有PeerVerifierAuthAPI

class UAVNode:
    def __init__(self, node_mac, signing_key):
        self.node_mac = node_mac

        # 用于请求认证
        self.requestor_api = None  # 动态创建

        # 用于验证其他UAV
        self.verifier_api = FeatureBasedAuthenticationAPI.create_peer_verifier(
            node_mac=node_mac,
            signing_key=signing_key
        )

    def authenticate_to_peer(self, peer_mac, csi_data):
        """向对等节点请求认证"""
        api = FeatureBasedAuthenticationAPI.create_uav_node(
            node_mac=self.node_mac,
            peer_mac=peer_mac
        )
        return api.authenticate(csi_data)

    def verify_peer(self, auth_request, csi_data):
        """验证对等节点"""
        return self.verifier_api.verify(auth_request, csi_data)

# 使用
uav_a = UAVNode(UAV_A_MAC, UAV_A_KEY)
uav_b = UAVNode(UAV_B_MAC, UAV_B_KEY)

# A向B认证
csi_a = measure_csi()
auth_req_a, _ = uav_a.authenticate_to_peer(UAV_B_MAC, csi_a)

# B验证A
csi_b = measure_csi()
result = uav_b.verify_peer(auth_req_a, csi_b)
```

### 场景3：UAV群组网络

```python
class UAVSwarmNetwork:
    """UAV群组网络管理"""

    def __init__(self, node_mac, signing_key):
        self.node_mac = node_mac
        self.verifier_api = FeatureBasedAuthenticationAPI.create_peer_verifier(
            node_mac=node_mac,
            signing_key=signing_key
        )
        self.member_uavs = {}  # 群组成员

    def accept_new_member(self, new_uav_mac, auth_request, csi_data):
        """接受新成员加入"""
        # 验证认证请求
        result = self.verifier_api.verify(auth_request, csi_data)

        if result.success:
            self.member_uavs[new_uav_mac] = {
                'joined_at': time.time(),
                'session_key': result.session_key,
                'mat_token': result.token
            }
            return True, result.token
        else:
            return False, None

    def remove_member(self, uav_mac):
        """移除成员"""
        if uav_mac in self.member_uavs:
            del self.member_uavs[uav_mac]
```

---

## 性能指标

基于test_uav_api.py的测试结果：

| 指标 | 数值 | 说明 |
|------|------|------|
| 认证请求生成延迟 | ~13ms | UAV节点端 |
| 认证验证延迟 | ~3ms | 验证节点端 |
| 总认证延迟 | <20ms | 端到端（不含传输） |
| 认证请求大小 | 71 bytes | 网络传输开销小 |
| MAT令牌大小 | 74 bytes | 后续快速认证 |
| 吞吐量 | >800 auth/s | 单个验证节点 |

**注意**：
- 延迟不包括RF/WiFi传输时间
- CSI测量时间取决于硬件（通常10-50ms）
- 实际性能受硬件和网络条件影响

---

## 安全建议

### 1. 密钥管理 ⚠️

- ✅ **DO**: 使用硬件安全模块（HSM）存储signing_key
- ✅ **DO**: 通过安全带外渠道分发feature_key
- ✅ **DO**: 定期轮换signing_key
- ❌ **DON'T**: 将signing_key硬编码在代码中
- ❌ **DON'T**: 通过不安全渠道传输feature_key

### 2. CSI测量 ⚠️

- ✅ **DO**: 确保CSI测量时间间隔尽可能短
- ✅ **DO**: 在静止或低速移动时进行认证
- ✅ **DO**: 检查信号质量（RSSI、SNR）
- ❌ **DON'T**: 在高速移动时进行认证
- ❌ **DON'T**: 忽略信道质量检查

### 3. Epoch同步 ⚠️

- ✅ **DO**: 使用NTP/GPS进行时间同步
- ✅ **DO**: 设置合理的epoch_period_ms（10-60秒）
- ✅ **DO**: 监控epoch同步状态
- ❌ **DON'T**: 使用本地时钟作为唯一时间源

### 4. 注册管理 ⚠️

- ✅ **DO**: 实现注册撤销机制
- ✅ **DO**: 记录审计日志
- ✅ **DO**: 定期清理过期注册
- ❌ **DON'T**: 允许未授权的注册

---

## 故障排查

### Q1: 认证总是失败，提示"digest_mismatch"

**可能原因**:
1. CSI测量不一致（信道条件差）
2. UAV间距离太远
3. UAV高速移动
4. 测量时间间隔太长

**解决方法**:
```python
# 1. 检查CSI测量质量
print(f"CSI shape: {csi_data.shape}")
print(f"CSI std: {np.std(csi_data)}")

# 2. 使用测试模式验证
api = FeatureBasedAuthenticationAPI.create_uav_node(
    ...,
    deterministic=True  # 测试模式
)

# 3. 使用完全相同的CSI（测试）
verifier_csi = uav_csi.copy()
```

### Q2: 首次认证失败，提示"device_not_registered"

**原因**: 忘记注册UAV节点

**解决方法**:
```python
# 确保在验证前注册
peer_verifier_api.register_uav_node(
    node_mac=uav_node_mac,
    feature_key=uav_response.feature_key,
    epoch=uav_response.epoch
)
```

### Q3: Session key不匹配

**原因**: CSI特征不一致导致密钥生成不同

**解决方法**:
```python
# 检查两端的CSI相似度
similarity = np.corrcoef(uav_csi.flatten(), verifier_csi.flatten())[0, 1]
print(f"CSI similarity: {similarity}")

# 相似度应该 > 0.9
if similarity < 0.9:
    print("⚠️ 警告：CSI相似度过低，可能导致认证失败")
```

---

## FAQ

### Q: 这个API适合什么样的UAV网络？

A: 适合：
- ✅ 自组织UAV群组（10-100架）
- ✅ 对等分布式网络
- ✅ 短距离通信（<1km）
- ✅ 低速/悬停UAV

不太适合：
- ❌ 大规模UAV集群（>1000架）
- ❌ 高速飞行场景（>50m/s）
- ❌ 长距离通信（>5km）

### Q: 需要什么硬件支持？

A: 最低要求：
- 支持CSI测量的WiFi网卡（如Intel 5300、Atheros 9390）
- 或专用的CSI测量硬件
- 建议：GPS模块（用于时间同步）

### Q: 如何处理UAV节点离线/故障？

A:
```python
# 建议实现超时机制
import time

class UAVRegistry:
    def __init__(self, timeout=300):  # 5分钟超时
        self.timeout = timeout
        self.last_seen = {}

    def update_last_seen(self, node_mac):
        self.last_seen[node_mac] = time.time()

    def is_active(self, node_mac):
        if node_mac not in self.last_seen:
            return False
        return (time.time() - self.last_seen[node_mac]) < self.timeout

    def cleanup_inactive(self):
        now = time.time()
        inactive = [mac for mac, t in self.last_seen.items()
                   if now - t > self.timeout]
        for mac in inactive:
            del self.last_seen[mac]
            # 注销节点
```

### Q: 如何实现群组密钥？

A: 建议在应用层实现：
```python
# 使用session_key派生群组密钥
from hashlib import sha256

def derive_group_key(session_keys):
    """从多个session_key派生群组密钥"""
    combined = b''.join(sorted(session_keys))
    return sha256(combined).digest()

# 所有群组成员使用相同的群组密钥加密广播消息
```

---

## 完整示例

参见项目中的示例文件：
- `test_uav_api.py`: 基本UAV认证流程
- `api_example.py`: 多场景示例（待更新为UAV版本）

---

## 技术支持

如有问题，请查看：
1. `UAV_SCENARIO_ANALYSIS.md`: UAV场景适配性分析
2. `FINAL_INTEGRATION_TEST_REPORT.md`: 集成测试报告
3. `DEPLOYMENT_GUIDE.md`: 部署指南

---

*最后更新：2024*
