# UAV安全通信功能指南

## 📋 功能概述

本项目现已实现**完整的UAV群组安全通信**功能，包括：

1. ✅ **物理层特征认证**（基于CSI）
2. ✅ **会话密钥派生**（特征加密算法）
3. ✅ **点对点加密通信**（AES-256-GCM）
4. ✅ **群组广播加密**（共享群组密钥）
5. ✅ **防重放攻击**（序列号跟踪）
6. ✅ **消息完整性保护**（AEAD认证）
7. ✅ **会话管理**（生命周期跟踪）
8. ✅ **群组密钥轮换**（成员变更触发）

---

## 🔐 安全架构

### 两阶段安全模型

```
阶段1: 认证与密钥协商（使用特征加密，计算密集）
┌──────────────────────────────────────────────────────────┐
│ UAV-A → 测量CSI → 特征加密 → session_key + feature_key    │
│ UAV-B → 测量CSI → 特征加密 → 验证 → session_key (相同)    │
│                                                          │
│ 时间: ~13ms (认证) + ~3ms (验证)                          │
│ 频率: 每30-60分钟一次，或成员变更时                       │
└──────────────────────────────────────────────────────────┘
                        ↓
阶段2: 数据加密通信（使用session_key，高效）
┌──────────────────────────────────────────────────────────┐
│ UAV-A → 明文 → AES-GCM(session_key) → 密文 → UAV-B       │
│                                                          │
│ 时间: ~0.01ms (加密) + ~0.007ms (解密)                   │
│ 频率: 每次通信（高频）                                    │
└──────────────────────────────────────────────────────────┘
```

### 关键原则

⚠️ **重要**：**特征加密算法仅用于认证阶段，不用于数据通信！**

| 场景 | 是否使用特征加密 | 实际使用的加密方式 |
|------|---------------|------------------|
| **首次认证** | ✅ 是 | 特征加密（CSI → 密钥） |
| **正常通信** | ❌ 否 | AES-256-GCM（session_key） |
| **群组广播** | ❌ 否 | AES-256-GCM（group_key） |
| **密钥过期** | ✅ 是 | 特征加密（重新认证） |

---

## 📦 核心模块

### 1. `uav_secure_channel.py` (~600行)

**功能**：底层加密/解密引擎

**主要类**：
- `SecureMessage`: 安全消息结构（序列化/反序列化）
- `UAVSecureChannel`: 加密信道管理

**核心方法**：
```python
# 点对点加密
encrypted = channel.encrypt_p2p(
    plaintext=b"Hello",
    session_key=session_key,  # 32字节
    dst_mac=peer_mac           # 6字节
)

# 点对点解密
success, plaintext, src_mac = channel.decrypt_p2p(
    encrypted_data=encrypted,
    session_key=session_key
)

# 群组广播加密
encrypted = channel.encrypt_group(
    plaintext=b"Broadcast message",
    group_key=group_key,       # 32字节
    group_id="UAVSwarm001"
)

# 群组广播解密
success, plaintext, src_mac = channel.decrypt_group(
    encrypted_data=encrypted,
    group_key=group_key,
    group_id="UAVSwarm001"
)
```

**安全特性**：
- ✅ AES-256-GCM加密
- ✅ 防重放攻击（1000消息窗口）
- ✅ 时间戳验证（30秒有效期）
- ✅ 序列号单调性
- ✅ 消息完整性（16字节认证标签）

### 2. `uav_secure_swarm.py` (~450行)

**功能**：集成认证与加密的高级接口

**主要类**：
- `UAVSecureSwarmCommunicator`: 安全群组通信器
- `SecureCommunicationSession`: 会话管理

**核心方法**：
```python
# 创建协调节点通信器
coordinator = UAVSecureSwarmCommunicator(
    node_mac=coordinator_mac,
    is_coordinator=True,
    coordinator_signing_key=signing_key,
    group_id="UAVSwarm001"
)

# 创建普通节点通信器
uav_node = UAVSecureSwarmCommunicator(
    node_mac=uav_mac,
    is_coordinator=False,
    group_id="UAVSwarm001"
)

# 发送加密消息
success, encrypted, reason = uav_node.send_secure_message(
    plaintext=b"Position update",
    dst_mac=coordinator_mac
)

# 接收加密消息
success, plaintext, src_mac, reason = coordinator.receive_secure_message(
    encrypted_data=encrypted
)

# 广播加密消息
success, encrypted, reason = coordinator.broadcast_secure_message(
    plaintext=b"Return to base"
)

# 接收广播
success, plaintext, src_mac, reason = uav_node.receive_broadcast_message(
    encrypted_data=encrypted,
    group_key=group_key
)
```

**管理功能**：
- 会话建立与关闭
- 会话超时清理
- 统计信息跟踪
- 状态监控

### 3. `examples_secure_communication.py` (~400行)

**功能**：5个完整使用示例

**示例列表**：
1. **示例1**: 点对点加密通信
2. **示例2**: 群组广播加密
3. **示例3**: 集成认证与加密通信
4. **示例4**: 安全特性演示
5. **示例5**: 性能基准测试

**运行方式**：
```bash
python examples_secure_communication.py
```

### 4. `test_secure_communication.py` (~350行)

**功能**：自动化测试套件

**测试用例**：
1. ✅ 点对点加密通信
2. ✅ 群组广播加密（3成员）
3. ✅ 消息完整性保护
4. ✅ 加密性能基准
5. ✅ 会话管理与双向通信
6. ✅ 群组密钥轮换

**运行方式**：
```bash
python test_secure_communication.py
```

**测试结果**：
```
================================================================================
                        测试总结
================================================================================
点对点加密通信                        ✓ 通过
群组广播加密                         ✓ 通过
消息完整性保护                        ✓ 通过
加密性能基准                         ✓ 通过
会话管理和端到端通信                   ✓ 通过
群组密钥轮换                         ✓ 通过
================================================================================
总计: 6/6 测试通过 (100.0%)
================================================================================

🎉 所有测试通过！UAV安全通信功能正常工作。
```

---

## 🚀 快速开始

### 基本使用流程

```python
import secrets
import numpy as np
from authentication_api import FeatureBasedAuthenticationAPI
from uav_secure_channel import UAVSecureChannel

# 步骤1: 认证并获取session_key
uav_a_mac = bytes.fromhex('001122334455')
uav_b_mac = bytes.fromhex('AABBCCDDEEFF')

# UAV-A: 创建认证请求
uav_a_api = FeatureBasedAuthenticationAPI.create_uav_node(
    node_mac=uav_a_mac,
    peer_mac=uav_b_mac
)

csi_data = np.random.randn(6, 62)  # 测量CSI
auth_request, response_a = uav_a_api.authenticate(csi_data)
session_key_a = response_a.session_key

# UAV-B: 验证请求
uav_b_api = FeatureBasedAuthenticationAPI.create_peer_verifier(
    node_mac=uav_b_mac,
    signing_key=secrets.token_bytes(32)
)

uav_b_api.register_uav_node(
    node_mac=uav_a_mac,
    feature_key=response_a.feature_key,
    epoch=response_a.epoch
)

response_b = uav_b_api.verify(auth_request, csi_data)
session_key_b = response_b.session_key

# 验证: session_key_a == session_key_b

# 步骤2: 使用session_key进行加密通信
channel_a = UAVSecureChannel(uav_a_mac)
channel_b = UAVSecureChannel(uav_b_mac)

# UAV-A 发送加密消息
plaintext = b"Hello UAV-B, this is UAV-A"
encrypted = channel_a.encrypt_p2p(plaintext, session_key_a, uav_b_mac)

# UAV-B 接收并解密
success, decrypted, src_mac = channel_b.decrypt_p2p(encrypted, session_key_b)

print(f"解密成功: {success}")
print(f"消息: {decrypted.decode('utf-8')}")
print(f"来源: {src_mac.hex()}")
```

---

## 📊 性能指标

### 加密性能（基于测试）

| 消息大小 | 加密延迟 | 解密延迟 | 总延迟 | 吞吐量 |
|---------|---------|---------|--------|--------|
| 64B     | 0.014ms | 0.007ms | 0.021ms | 3 MB/s |
| 256B    | 0.010ms | 0.006ms | 0.016ms | 16 MB/s |
| 1KB     | 0.012ms | 0.010ms | 0.022ms | 46 MB/s |
| 4KB     | 0.017ms | 0.008ms | 0.025ms | 161 MB/s |

### 消息开销

```
原始消息: N bytes
↓
加密消息: N + 56 bytes

开销分解:
- 头部: 40 bytes (版本、类型、MAC、序列号、时间戳、nonce)
- GCM标签: 16 bytes (完整性认证)
```

### 对比：认证 vs 通信

| 操作 | 延迟 | 使用场景 |
|------|------|---------|
| **特征认证** | ~13-16ms | 首次认证/密钥协商（低频） |
| **数据加密** | ~0.01ms | 每次通信（高频） |
| **速度提升** | **~1300倍** | 使用session_key加密 |

---

## 🔒 安全特性

### 1. 机密性（Confidentiality）
- **算法**: AES-256-GCM
- **密钥**: 256位 session_key 或 group_key
- **Nonce**: 每条消息随机生成（12字节）

### 2. 完整性（Integrity）
- **方法**: GCM认证标签（16字节）
- **AAD**: 消息头部（版本、类型、MAC、序列号、时间戳）
- **防篡改**: 任何修改导致解密失败

### 3. 防重放（Anti-Replay）
- **机制**: 序列号跟踪
- **窗口**: 1000条消息
- **效果**: 重复消息自动拒绝

### 4. 新鲜度（Freshness）
- **时间戳**: Unix毫秒级时间戳
- **有效期**: 30秒
- **时钟偏差**: 允许±5秒

### 5. 认证（Authentication）
- **源认证**: MAC地址 + 签名密钥
- **消息认证**: GCM AEAD
- **会话认证**: 基于物理层特征

---

## 🛡️ 威胁防护

| 威胁类型 | 防护机制 | 状态 |
|---------|---------|------|
| 窃听（Eavesdropping） | AES-256-GCM加密 | ✅ 防护 |
| 篡改（Tampering） | GCM认证标签 | ✅ 检测 |
| 重放（Replay） | 序列号跟踪 | ✅ 阻止 |
| 中间人（MITM） | 物理层认证 + 签名 | ✅ 防护 |
| 消息注入（Injection） | MAC验证 + 序列号 | ✅ 阻止 |
| 延迟攻击（Delay） | 时间戳验证 | ✅ 检测 |
| 身份伪造（Spoofing） | 特征认证 + 密钥 | ✅ 防护 |

---

## 🔄 密钥管理

### 密钥层次结构

```
协调节点签名密钥 (coordinator_signing_key)
          ↓
    群组密钥 (group_key) = SHA256(group_id + all_session_keys + version)
          ↓
    会话密钥 (session_key) = 特征加密(CSI)
          ↓
    消息加密 (AES-GCM)
```

### 密钥轮换触发条件

1. **定时轮换**：每隔 `key_rotation_interval` 秒（默认3600秒）
2. **成员变更**：
   - 新成员加入（添加其session_key）
   - 成员撤销（排除其session_key）
   - 成员超时（自动清理）
3. **手动触发**：调用 `update_group_key()`

### 密钥版本管理

```python
# 获取当前群组密钥
group_key, version = swarm_manager.get_group_key()

# 手动轮换
new_key = swarm_manager.update_group_key()
_, new_version = swarm_manager.get_group_key()

# version自动递增: v1 → v2 → v3 ...
```

---

## 📝 使用示例

### 示例1：点对点加密通信

```python
from uav_secure_channel import UAVSecureChannel
import secrets

# 初始化
uav_a_mac = bytes.fromhex('001122334455')
uav_b_mac = bytes.fromhex('AABBCCDDEEFF')
session_key = secrets.token_bytes(32)  # 通过认证获得

channel_a = UAVSecureChannel(uav_a_mac)
channel_b = UAVSecureChannel(uav_b_mac)

# UAV-A 发送
plaintext = b"Mission command: proceed to waypoint 3"
encrypted = channel_a.encrypt_p2p(plaintext, session_key, uav_b_mac)

# UAV-B 接收
success, decrypted, src = channel_b.decrypt_p2p(encrypted, session_key)
print(f"收到来自 {src.hex()} 的消息: {decrypted.decode()}")
```

### 示例2：群组广播

```python
from uav_swarm_manager import UAVSwarmManager
import secrets

# 创建群组
coordinator_mac = bytes.fromhex('AABBCCDDEEFF')
signing_key = secrets.token_bytes(32)

swarm = UAVSwarmManager(
    coordinator_mac=coordinator_mac,
    coordinator_signing_key=signing_key,
    group_id="Squadron-Alpha"
)

# 添加成员（通过认证）
for member_mac in [member1_mac, member2_mac, member3_mac]:
    swarm.add_member(
        node_mac=member_mac,
        feature_key=feature_key,
        session_key=session_key
    )

# 获取群组密钥
group_key, version = swarm.get_group_key()

# 协调节点广播
coordinator_channel = UAVSecureChannel(coordinator_mac)
broadcast = coordinator_channel.encrypt_group(
    plaintext=b"All units: Emergency landing protocol",
    group_key=group_key,
    group_id="Squadron-Alpha"
)

# 所有成员接收
for member_mac in [member1_mac, member2_mac, member3_mac]:
    member_channel = UAVSecureChannel(member_mac)
    success, msg, src = member_channel.decrypt_group(
        encrypted_data=broadcast,
        group_key=group_key,
        group_id="Squadron-Alpha"
    )
    if success:
        print(f"成员 {member_mac.hex()} 收到: {msg.decode()}")
```

---

## 🔧 配置参数

### UAVSecureChannel 参数

```python
class UAVSecureChannel:
    # 消息最大有效期（毫秒）
    MAX_MESSAGE_AGE_MS = 30000  # 30秒

    # 重放检测窗口大小
    REPLAY_WINDOW_SIZE = 1000   # 1000条消息
```

### UAVSwarmManager 参数

```python
swarm_manager = UAVSwarmManager(
    coordinator_mac=...,
    coordinator_signing_key=...,
    group_id="UAVSwarm",
    member_timeout=300,          # 成员超时：5分钟
    key_rotation_interval=3600   # 密钥轮换：1小时
)
```

---

## ⚠️ 注意事项

### 1. 依赖项

确保安装以下依赖：

```bash
pip install cryptography numpy
```

### 2. 时钟同步

- 所有UAV节点需要时钟同步（NTP）
- 允许最大偏差：±5秒
- 超时消息将被拒绝

### 3. 密钥存储

- `session_key`、`group_key` 应存储在安全内存
- 生产环境建议使用硬件安全模块（HSM）
- 定期轮换密钥

### 4. 性能优化

- 小消息（<1KB）适合实时通信
- 大文件传输考虑分块加密
- 批量消息可复用nonce派生机制

### 5. 生产部署

- 禁用 `deterministic=True`（仅用于测试）
- 启用日志审计
- 配置入侵检测系统（IDS）
- 定期安全评估

---

## 📚 参考文档

### 相关文件

- `authentication_api.py` - 认证API
- `uav_swarm_manager.py` - 群组管理
- `uav_mobility_support.py` - 移动性支持
- `feature-encryption/` - 特征加密模块
- `feature-authentication/` - 特征认证模块

### 标准与规范

- **AES-GCM**: NIST SP 800-38D
- **密钥派生**: NIST SP 800-108
- **时间戳**: RFC 3161
- **MAC地址**: IEEE 802

---

## 🎯 使用场景

### ✅ 适用场景

1. **无人机编队通信**：协调节点与多个UAV加密通信
2. **战术数据链**：军用/执法UAV的安全信息交换
3. **商用无人机网络**：物流、巡检、监控等应用
4. **应急响应系统**：灾害救援中的UAV协同
5. **自组织网络**：动态拓扑的UAV集群

### ❌ 不适用场景

1. **超低延迟需求**（<0.01ms）- 加密有~0.02ms开销
2. **极高吞吐量**（>1Gbps）- 受限于软件加密性能
3. **资源极受限设备**（<1MB RAM）- 需要裁剪功能

---

## 🐛 故障排查

### 常见问题

**Q1: 解密失败 "tag_mismatch"**
```
原因: 密钥不匹配或消息被篡改
解决: 确认双方使用相同的session_key，检查认证流程
```

**Q2: "检测到重放攻击"**
```
原因: 重复发送相同消息
解决: 每次发送生成新消息（自动递增序列号）
```

**Q3: "消息过期"**
```
原因: 时间戳超过30秒
解决: 检查时钟同步，减少网络延迟
```

**Q4: "未建立会话"**
```
原因: 未完成认证流程
解决: 先调用 authenticate_and_establish_session()
```

---

## 📈 未来扩展

### 计划中的功能

- [ ] 硬件加密加速（支持AES-NI指令集）
- [ ] 量子安全算法（后量子密码）
- [ ] 多播优化（减少群组广播开销）
- [ ] 密钥托管服务（Key Escrow）
- [ ] 前向安全性（Forward Secrecy）
- [ ] 分布式密钥管理（无协调节点模式）

---

## 📞 支持

如有问题或建议，请：

1. 查看示例代码：`examples_secure_communication.py`
2. 运行测试验证：`python test_secure_communication.py`
3. 检查日志输出：`[UAVSecureChannel]` 标签
4. 查阅API文档：模块docstring

---

## ✅ 总结

本实现提供了**生产级别**的UAV安全通信功能：

✅ **完整性**：覆盖认证→加密→通信全流程
✅ **安全性**：AES-256-GCM + 多重防护机制
✅ **性能**：<0.02ms加密延迟，161MB/s吞吐量
✅ **可靠性**：100%测试通过率
✅ **易用性**：简洁的API + 详细文档

**关键创新**：将计算密集的特征加密（认证）与高效的对称加密（通信）完美结合，实现了安全性与性能的最佳平衡。
