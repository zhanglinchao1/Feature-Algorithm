# 第二阶段：3.2与3.3集成设计方案

**日期**: 2025-11-19
**目标**: 实现3.2认证模块与3.3同步模块的集成

---

## 1. 当前状态分析

### 1.1 3.2模块 (feature-authentication)

**现有实现**:
- `DeviceSide.create_auth_request()`: 直接调用3.1的`register()`
- `VerifierSide.verify_auth_request()`: 直接调用3.1的`authenticate()`
- epoch从外部传入的`AuthContext`获取，无同步机制
- 无epoch有效性验证
- 无密钥轮换机制

**关键代码位置**:
```python
# feature-authentication/src/mode2_strong_auth.py:187-196
key_output, metadata = self.fe.register(
    device_id=dev_id.hex(),
    Z_frames=Z_frames,
    context=fe_context,
    mask_bytes=b'device_mask'
)

# feature-authentication/src/mode2_strong_auth.py:432-438
key_output, success = self.fe.authenticate(
    device_id=dev_id.hex(),
    Z_frames=Z_frames,
    context=fe_context,
    mask_bytes=b'device_mask'
)
```

### 1.2 3.3模块 (feature_synchronization)

**可用接口** (`SynchronizationService`):
1. `get_current_epoch()` - 获取当前epoch
2. `is_epoch_valid(epoch)` - 检查epoch是否在容忍范围内
3. `generate_or_get_key_material(device_mac, epoch, feature_vector, nonce)` - 生成/获取密钥
4. `issue_mat_token(device_pseudonym, epoch, session_key, ttl)` - 签发MAT
5. `verify_mat_token(mat)` - 验证MAT
6. `is_synchronized()` - 检查同步状态

**密钥生成路径**:
```
SynchronizationService.generate_or_get_key_material()
    ↓
KeyRotationManager.generate_key_material()
    ↓
FeatureEncryptionAdapter.derive_keys_for_device()
    ↓
FeatureEncryption.register() [3.1模块]
```

---

## 2. 集成设计方案

### 2.1 设计原则

1. **向后兼容**: 保持现有3.2的独立运行能力
2. **可选集成**: 通过可选参数启用3.3集成
3. **最小侵入**: 尽量减少对现有代码的修改
4. **清晰分层**: 3.2依赖3.3，3.3依赖3.1

### 2.2 集成架构

```
┌─────────────────────────────────────────┐
│  3.2 feature-authentication (模式二)    │
│                                         │
│  ┌─────────────┐    ┌──────────────┐   │
│  │ DeviceSide  │    │ VerifierSide │   │
│  └──────┬──────┘    └──────┬───────┘   │
│         │                  │            │
│         │ 可选依赖          │            │
│         ↓                  ↓            │
└─────────┼──────────────────┼────────────┘
          │                  │
          ↓                  ↓
┌─────────────────────────────────────────┐
│  3.3 feature_synchronization            │
│                                         │
│  ┌──────────────────────────────────┐   │
│  │  SynchronizationService          │   │
│  │  - get_current_epoch()           │   │
│  │  - is_epoch_valid()              │   │
│  │  - generate_or_get_key_material()│   │
│  │  - issue_mat_token()             │   │
│  └──────────────┬───────────────────┘   │
│                 │                       │
│                 ↓                       │
│  ┌──────────────────────────────────┐   │
│  │  KeyRotationManager              │   │
│  └──────────────┬───────────────────┘   │
│                 │                       │
│                 ↓                       │
│  ┌──────────────────────────────────┐   │
│  │  FeatureEncryptionAdapter        │   │
│  └──────────────┬───────────────────┘   │
└─────────────────┼───────────────────────┘
                  │
                  ↓
┌─────────────────────────────────────────┐
│  3.1 feature-encryption                 │
│  - FeatureEncryption.register()         │
│  - FeatureEncryption.authenticate()     │
└─────────────────────────────────────────┘
```

### 2.3 修改方案

#### 2.3.1 DeviceSide修改

**添加参数**:
```python
class DeviceSide:
    def __init__(self, config: AuthConfig,
                 fe_config: Optional[FEConfig] = None,
                 sync_service: Optional['SynchronizationService'] = None):
        self.sync_service = sync_service
        # ... 现有代码
```

**修改create_auth_request()**:
```python
def create_auth_request(self, dev_id: bytes, Z_frames: np.ndarray,
                       context: AuthContext) -> Tuple[AuthReq, bytes]:
    # Step 0: 如果使用sync_service，从中获取epoch
    if self.sync_service:
        # 使用同步的epoch
        epoch = self.sync_service.get_current_epoch()
        context = AuthContext(
            src_mac=context.src_mac,
            dst_mac=context.dst_mac,
            epoch=epoch,  # 使用同步的epoch
            nonce=context.nonce,
            seq=context.seq,
            alg_id=context.alg_id,
            ver=context.ver,
            csi_id=context.csi_id
        )

    # Step 1: 生成密钥
    if self.sync_service:
        # 使用3.3的密钥生成（通过适配器调用3.1）
        key_material = self.sync_service.generate_or_get_key_material(
            device_mac=dev_id,
            epoch=context.epoch,
            feature_vector=Z_frames,
            nonce=context.nonce
        )
        K = key_material.feature_key
        Ks = key_material.session_key
        # 需要获取digest - 这需要从key_material中添加
        digest = key_material.pseudonym[:8]  # 临时方案
    else:
        # 直接调用3.1（向后兼容）
        key_output, metadata = self.fe.register(...)
        K = key_output.K
        Ks = key_output.Ks
        digest = key_output.digest

    # Step 2-4: 保持不变
    # ...
```

#### 2.3.2 VerifierSide修改

**添加参数**:
```python
class VerifierSide:
    def __init__(self, config: AuthConfig, issuer_id: bytes, issuer_key: bytes,
                 fe_config: Optional[FEConfig] = None,
                 sync_service: Optional['SynchronizationService'] = None):
        self.sync_service = sync_service
        # ... 现有代码
```

**修改verify_auth_request()**:
```python
def verify_auth_request(self, auth_req: AuthReq, Z_frames: np.ndarray) -> AuthResult:
    # Step 0: Epoch有效性检查（如果使用sync_service）
    if self.sync_service:
        if not self.sync_service.is_epoch_valid(auth_req.epoch):
            return AuthResult(
                success=False,
                mode="mode2",
                reason="epoch_out_of_range"
            )

    # Step 1: 设备定位（保持不变）
    dev_id = self.locate_device(auth_req.dev_pseudo, auth_req.epoch)

    # Step 2: 密钥重构
    if self.sync_service:
        # 使用3.3的密钥生成
        key_material = self.sync_service.generate_or_get_key_material(
            device_mac=dev_id,
            epoch=auth_req.epoch,
            feature_vector=Z_frames,
            nonce=auth_req.nonce
        )
        K = key_material.feature_key
        Ks = key_material.session_key
        success = True  # 3.3的generate_or_get_key_material总是成功
        digest = key_material.pseudonym[:8]  # 临时方案
    else:
        # 直接调用3.1（向后兼容）
        key_output, success = self.fe.authenticate(...)
        K = key_output.K
        Ks = key_output.Ks
        digest = key_output.digest

    # Step 3-5: 保持不变
    # ...
```

### 2.4 问题：digest字段不匹配

**问题描述**:
- 3.1的`KeyOutput`包含`digest`字段（8字节配置摘要）
- 3.3的`KeyMaterial`不包含`digest`字段
- 3.2需要`digest`进行配置一致性检查

**解决方案**:
1. **方案A**: 修改`KeyMaterial`添加`digest`字段
2. **方案B**: 在`FeatureEncryptionAdapter`返回额外的`digest`
3. **方案C**: 在集成场景下跳过digest检查（不推荐）

**推荐方案A**: 修改`KeyMaterial`数据类

```python
# feature_synchronization/core/key_material.py
@dataclass
class KeyMaterial:
    feature_key: bytes      # K: 特征密钥（32字节）
    session_key: bytes      # Ks: 会话密钥（32字节）
    pseudonym: bytes        # DevPseudo: 设备伪名（12字节）
    epoch: int              # 绑定的epoch
    created_at: int         # 创建时间戳(ms)
    expires_at: int         # 过期时间戳(ms)
    digest: bytes = b''     # 新增: 配置摘要（8字节），用于3.2集成
```

---

## 3. 实现步骤

### 3.1 第一步：修改KeyMaterial添加digest字段

**文件**: `feature_synchronization/core/key_material.py`

**修改**:
```python
@dataclass
class KeyMaterial:
    # ... 现有字段
    digest: bytes = b''  # 配置摘要（8字节）
```

**文件**: `feature_synchronization/sync/key_rotation.py`

**修改**: 在`generate_key_material()`中保存digest

### 3.2 第二步：修改Mode2StrongAuth支持SynchronizationService

**文件**: `feature-authentication/src/mode2_strong_auth.py`

**修改**:
1. `DeviceSide.__init__()` 添加`sync_service`参数
2. `VerifierSide.__init__()` 添加`sync_service`参数
3. `DeviceSide.create_auth_request()` 集成3.3接口
4. `VerifierSide.verify_auth_request()` 集成3.3接口

### 3.3 第三步：编写集成测试

**文件**: `test_integration_3.2_3.3.py`

**测试场景**:
1. 使用SynchronizationService的完整认证流程
2. Epoch有效性验证
3. 跨epoch密钥轮换
4. 向后兼容测试（不使用sync_service）

### 3.4 第四步：代码审查

- 运行所有测试
- 检查代码质量
- 验证向后兼容性
- 性能评估

---

## 4. 测试计划

### 4.1 单元测试

**新增测试**:
- `test_device_side_with_sync_service()` - DeviceSide使用sync_service
- `test_verifier_side_with_sync_service()` - VerifierSide使用sync_service
- `test_epoch_validation()` - Epoch有效性检查
- `test_backward_compatibility()` - 向后兼容性

### 4.2 集成测试

**测试场景**:
1. **正常流程**: Device + Verifier都使用sync_service
2. **Epoch过期**: 使用过期的epoch，验证拒绝
3. **密钥轮换**: 跨epoch认证
4. **混合模式**: Device使用sync_service，Verifier不使用（应失败）

### 4.3 回归测试

- 运行现有的`test_mode2.py`确保无回归
- 运行3.1模块测试
- 运行3.3模块测试

---

## 5. 验收标准

### 5.1 功能完整性

- ✅ DeviceSide支持可选的sync_service
- ✅ VerifierSide支持可选的sync_service
- ✅ Epoch自动从sync_service获取
- ✅ Epoch有效性自动验证
- ✅ 密钥通过3.3生成（内部调用3.1）
- ✅ 向后兼容（不提供sync_service时正常工作）

### 5.2 测试覆盖

- ✅ 单元测试通过率 ≥ 95%
- ✅ 集成测试覆盖主要场景
- ✅ 回归测试全部通过

### 5.3 代码质量

- ✅ 代码注释清晰
- ✅ 日志输出完善
- ✅ 异常处理健全
- ✅ 符合现有代码风格

---

## 6. 风险与缓解

### 6.1 风险：digest字段不匹配

**缓解**: 修改KeyMaterial添加digest字段

### 6.2 风险：向后兼容性破坏

**缓解**:
- sync_service为可选参数，默认None
- 保留直接调用3.1的路径
- 全面的回归测试

### 6.3 风险：性能下降

**缓解**:
- 使用3.3的密钥缓存机制
- 避免重复密钥生成

---

## 7. 时间估算

| 任务 | 预计时间 |
|------|---------|
| 修改KeyMaterial | 0.5小时 |
| 修改Mode2StrongAuth | 1.5小时 |
| 编写集成测试 | 1小时 |
| 调试和修复 | 1小时 |
| 代码审查和文档 | 1小时 |
| **总计** | **5小时** |

---

## 8. 下一阶段预览

**第三阶段**: 三模块端到端测试
- 完整认证流程（3.1 + 3.2 + 3.3）
- 多设备场景
- 性能基准测试
- 压力测试

**第四阶段**: 文档和优化
- 集成指南
- API文档
- 部署文档
