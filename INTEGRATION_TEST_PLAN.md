# 三模块联调集成测试计划

**创建日期**: 2025-11-19
**版本**: v1.0
**状态**: 设计中

---

## 1. 概述

### 1.1 目标

将以下三个独立开发的模块集成到一起，实现完整的基于物理层特征的MAC身份认证系统：

- **3.1 feature-encryption**: 基于特征的加密算法
- **3.2 feature-authentication**: 基于特征的认证方法
- **3.3 feature_synchronization**: 基于特征的周期变化同步机制

### 1.2 集成架构

```
┌─────────────────────────────────────────────────────────────┐
│                     完整认证系统                              │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐      ┌──────────────┐      ┌───────────┐ │
│  │   3.3 Sync   │◄────►│   3.2 Auth   │◄────►│  3.1 FE   │ │
│  │   (时间窗)    │      │   (认证)     │      │  (密钥)    │ │
│  └──────────────┘      └──────────────┘      └───────────┘ │
│         │                      │                     │       │
│         │                      │                     │       │
│    epoch管理              认证流程             特征→密钥    │
│    密钥轮换              Tag验证               S,K,Ks派生   │
│    MAT管理               伪名生成              digest计算   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 当前状态

| 模块 | 开发状态 | 测试状态 | 接口状态 |
|------|---------|---------|---------|
| 3.1 feature-encryption | ✅ 完成 | ✅ 6/6通过 | ✅ 接口完整 |
| 3.2 feature-authentication | ✅ 完成 | ✅ 3/4通过 | ✅ 已集成3.1 |
| 3.3 feature_synchronization | ✅ 完成 | ✅ 7/7通过 | ⚠️ 使用Mock |

**关键问题**: 3.3模块使用Mock实现3.1接口，需要替换为真实接口

---

## 2. 接口依赖分析

### 2.1 模块依赖关系

```
3.3 (Sync) ──┐
             ├──► 3.1 (FE) ──► 物理层特征
3.2 (Auth) ──┘
```

- **3.1 → 无依赖**: 独立模块，只依赖物理层特征输入
- **3.2 → 依赖3.1**: 需要调用3.1的`register()`和`authenticate()`
- **3.3 → 依赖3.1**: 需要调用3.1的密钥派生接口

### 2.2 3.1模块导出的接口

**文件**: `feature-encryption/src/feature_encryption.py`

```python
class FeatureEncryption:
    def __init__(self, config: FeatureEncryptionConfig = None,
                 deterministic_for_testing: bool = False):
        """初始化特征加密算法"""
        pass

    def register(self, device_id: str, Z_frames: np.ndarray,
                 context: Context, **kwargs) -> Tuple[KeyOutput, Dict[str, Any]]:
        """
        注册阶段：采集特征并生成辅助数据

        Args:
            device_id: 设备标识
            Z_frames: 多帧特征，shape (M, D)
            context: 上下文信息 (srcMAC, dstMAC, dom, ver, epoch, Ci, nonce)
            **kwargs: 额外参数（如mask_bytes等）

        Returns:
            key_output: KeyOutput(S, L, K, Ks, digest)
            metadata: 包含theta_L, theta_H, mask, bit_count等
        """
        pass

    def authenticate(self, device_id: str, Z_frames: np.ndarray,
                     context: Context, **kwargs) -> Tuple[Optional[KeyOutput], bool]:
        """
        认证阶段：重新采集特征并恢复密钥

        Args:
            device_id: 设备标识
            Z_frames: 多帧特征，shape (M, D)
            context: 上下文信息
            **kwargs: 额外参数

        Returns:
            key_output: KeyOutput或None
            success: 是否成功
        """
        pass

@dataclass
class Context:
    """上下文信息"""
    srcMAC: bytes      # 源MAC地址（6字节）
    dstMAC: bytes      # 目标MAC地址（6字节）
    dom: bytes         # 域标识
    ver: int           # 算法版本
    epoch: int         # 时间窗编号
    Ci: int            # 哈希链计数器
    nonce: bytes       # 随机数（16字节）

@dataclass
class KeyOutput:
    """密钥输出"""
    S: bytes           # 稳定特征串（32字节）
    L: bytes           # 随机扰动值（32字节）
    K: bytes           # 特征密钥（KEY_LENGTH字节）
    Ks: bytes          # 会话密钥（KEY_LENGTH字节）
    digest: bytes      # 一致性摘要（DIGEST_LENGTH字节）
```

### 2.3 3.2模块的集成状态

**文件**: `feature-authentication/src/_fe_bridge.py`

✅ **已完成**: 3.2模块已经实现了对3.1模块的桥接导入，解决了命名冲突问题

```python
from _fe_bridge import FeatureEncryption, FEContext, KeyOutput, FEConfig
```

**使用示例**:
```python
# feature-authentication/src/mode2_strong_auth.py
from ._fe_bridge import FeatureEncryption, FEContext, KeyOutput

# 在Issuer和Verifier中使用
self.fe = FeatureEncryption(fe_config)
```

### 2.4 3.3模块的Mock实现

**文件**: `feature_synchronization/sync/key_rotation.py:62-81`

⚠️ **待替换**: 当前使用Mock实现

```python
# 当前代码
if self.feature_key_engine:
    # 真实实现（待集成）
    S, L, K, Ks, digest = self.feature_key_engine.derive_keys(...)
else:
    # Mock实现 ← 需要替换
    feature_key, session_key = self._mock_derive_keys(...)
```

**问题**:
1. `feature_key_engine`未初始化，始终使用Mock
2. Mock实现无法提供真实的物理层特征绑定
3. 缺少S、L、digest等关键输出

---

## 3. 集成任务分解

### 任务1: 创建3.1模块的桥接适配器 (3.3 → 3.1)

**目标**: 为3.3模块提供调用3.1接口的适配层

**实现**: 创建 `feature_synchronization/adapters/fe_adapter.py`

```python
"""3.1模块适配器"""
import sys
from pathlib import Path
import numpy as np

# 导入3.1模块（解决命名冲突）
_fe_root = Path(__file__).parent.parent.parent / 'feature-encryption'
sys.path.insert(0, str(_fe_root))

from src.feature_encryption import FeatureEncryption, Context, KeyOutput
from src.config import FeatureEncryptionConfig

class FeatureEncryptionAdapter:
    """
    3.1模块适配器

    将3.3需要的接口转换为3.1的调用
    """

    def __init__(self, config: FeatureEncryptionConfig = None):
        self.fe = FeatureEncryption(config)

    def derive_keys_for_device(self, device_mac: bytes, validator_mac: bytes,
                                feature_vector: np.ndarray, epoch: int,
                                nonce: bytes, hash_chain_counter: int,
                                domain: bytes = b'DefaultDomain',
                                version: int = 1) -> tuple:
        """
        为3.3模块提供密钥派生接口

        Args:
            device_mac: 设备MAC地址（6字节）
            validator_mac: 验证节点MAC地址（6字节）
            feature_vector: 特征向量，shape (M, D)
            epoch: epoch编号
            nonce: 随机数（16字节）
            hash_chain_counter: 哈希链计数器
            domain: 域标识
            version: 版本号

        Returns:
            (S, L, K, Ks, digest): 密钥材料
        """
        # 构造上下文
        context = Context(
            srcMAC=device_mac,
            dstMAC=validator_mac,
            dom=domain,
            ver=version,
            epoch=epoch,
            Ci=hash_chain_counter,
            nonce=nonce
        )

        # 调用3.1接口
        device_id = device_mac.hex()
        key_output, metadata = self.fe.register(device_id, feature_vector, context)

        return key_output.S, key_output.L, key_output.K, key_output.Ks, key_output.digest

    def authenticate_device(self, device_mac: bytes, validator_mac: bytes,
                            feature_vector: np.ndarray, epoch: int,
                            nonce: bytes, hash_chain_counter: int,
                            domain: bytes = b'DefaultDomain',
                            version: int = 1) -> tuple:
        """
        为3.3模块提供认证接口

        Returns:
            (success, S, L, K, Ks, digest): 认证结果和密钥材料
        """
        context = Context(
            srcMAC=device_mac,
            dstMAC=validator_mac,
            dom=domain,
            ver=version,
            epoch=epoch,
            Ci=hash_chain_counter,
            nonce=nonce
        )

        device_id = device_mac.hex()
        key_output, success = self.fe.authenticate(device_id, feature_vector, context)

        if success:
            return True, key_output.S, key_output.L, key_output.K, key_output.Ks, key_output.digest
        else:
            return False, None, None, None, None, None
```

### 任务2: 修改3.3模块使用真实接口

**文件**: `feature_synchronization/sync/key_rotation.py`

**修改1**: 在`__init__`中初始化适配器

```python
from ..adapters.fe_adapter import FeatureEncryptionAdapter

class KeyRotationManager:
    def __init__(self, ...):
        # ...existing code...

        # 初始化3.1适配器
        self.fe_adapter = FeatureEncryptionAdapter()
```

**修改2**: 替换Mock实现

```python
def generate_key_material(self, device_mac: bytes, validator_mac: bytes,
                          feature_vector: np.ndarray = None) -> KeyMaterial:
    # ...existing code...

    # 调用3.1真实接口（替换Mock）
    S, L, K, Ks, digest = self.fe_adapter.derive_keys_for_device(
        device_mac=device_mac,
        validator_mac=validator_mac,
        feature_vector=feature_vector,
        epoch=epoch,
        nonce=nonce,
        hash_chain_counter=hash_chain_counter,
        domain=self.domain,
        version=1
    )

    feature_key = K
    session_key = Ks

    # ...existing code...
```

### 任务3: 集成3.2和3.3模块

**目标**: 让3.2模块的认证流程使用3.3提供的epoch和密钥轮换能力

**设计思路**:

```python
# 3.2模块中添加3.3的依赖
from feature_synchronization.sync import SynchronizationService

class Mode2StrongAuth:
    def __init__(self, ...):
        # ...existing code...

        # 可选：集成3.3的同步服务
        self.sync_service = None

    def set_sync_service(self, sync_service: SynchronizationService):
        """设置同步服务（可选）"""
        self.sync_service = sync_service

    def _get_current_epoch(self) -> int:
        """获取当前epoch"""
        if self.sync_service:
            return self.sync_service.get_current_epoch()
        else:
            # 降级：使用本地时间计算
            return int(time.time() // 30)  # 30秒一个epoch

    def _is_epoch_valid(self, epoch: int) -> bool:
        """检查epoch有效性"""
        if self.sync_service:
            return self.sync_service.is_epoch_valid(epoch)
        else:
            # 降级：允许±1 epoch
            current = self._get_current_epoch()
            return abs(epoch - current) <= 1
```

### 任务4: 编写端到端集成测试

**文件**: `tests/test_e2e_integration.py`

**测试场景1**: 完整认证流程（3.1 + 3.2）

```python
def test_full_authentication_flow():
    """测试完整认证流程"""
    # 1. 初始化3.1模块
    fe = FeatureEncryption(deterministic_for_testing=True)

    # 2. 初始化3.2模块
    issuer = Mode2StrongAuthIssuer(fe_config)
    verifier = Mode2StrongAuthVerifier(fe_config)

    # 3. 设备端注册
    device_mac = bytes.fromhex('001122334455')
    Z_frames = generate_test_csi(M=6, D=62)

    auth_req = issuer.register_and_authenticate(device_mac, Z_frames)

    # 4. 验证端认证
    result = verifier.verify_authentication(auth_req)

    assert result.success == True
    assert result.mat_token is not None
```

**测试场景2**: 带同步的认证流程（3.1 + 3.2 + 3.3）

```python
def test_authentication_with_sync():
    """测试集成同步机制的认证流程"""
    # 1. 初始化3.3同步服务
    sync_service = SynchronizationService(
        node_type='validator',
        node_id=b'\x00\x00\x00\x00\x00\x01'
    )
    sync_service.start()

    # 2. 初始化3.2认证模块，绑定同步服务
    verifier = Mode2StrongAuthVerifier(fe_config)
    verifier.set_sync_service(sync_service)

    # 3. 设备端生成密钥材料
    device_mac = bytes.fromhex('001122334455')
    validator_mac = b'\x00\x00\x00\x00\x00\x01'

    # 从同步服务获取当前epoch
    current_epoch = sync_service.get_current_epoch()

    # 生成密钥材料
    key_material = sync_service.key_rotation.generate_key_material(
        device_mac=device_mac,
        validator_mac=validator_mac,
        feature_vector=Z_frames
    )

    # 4. 使用生成的密钥进行认证
    # ...

    assert key_material.epoch == current_epoch
    assert key_material.is_valid()
```

**测试场景3**: 密钥轮换测试

```python
def test_key_rotation():
    """测试epoch切换时的密钥轮换"""
    # 1. 初始化系统
    sync_service = SynchronizationService(...)

    # 2. 在epoch=0时注册
    epoch0_material = generate_key_material(epoch=0)

    # 3. 时间推进到epoch=1
    advance_time(30)

    # 4. 验证新epoch的密钥
    epoch1_material = generate_key_material(epoch=1)

    # 5. 检查密钥已轮换
    assert epoch0_material.feature_key != epoch1_material.feature_key
    assert epoch0_material.pseudonym != epoch1_material.pseudonym
```

---

## 4. 测试验收标准

### 4.1 单元测试

| 模块 | 测试文件 | 要求 |
|------|---------|------|
| 3.1 | test_progressive.py | ✅ 6/6通过 |
| 3.2 | test_mode2.py | ✅ 3/3通过 |
| 3.3 | test_integration.py | ✅ 7/7通过 |

### 4.2 集成测试

| 测试场景 | 验收标准 |
|---------|---------|
| 3.1 + 3.2 集成 | 完整认证流程通过 |
| 3.1 + 3.3 集成 | 真实密钥派生替换Mock |
| 3.2 + 3.3 集成 | epoch同步和验证通过 |
| 三模块端到端 | 完整认证+同步+轮换通过 |

### 4.3 性能指标

| 指标 | 目标值 | 测量方法 |
|------|--------|---------|
| 密钥派生时延 | < 50ms | 计时统计 |
| 认证成功率 | > 99% | 100次重复测试 |
| digest一致性 | 100% | 注册/认证对比 |
| epoch同步精度 | ±1 epoch | 时钟偏差测试 |

---

## 5. 开发计划

### 第一阶段：接口适配 (预计1-2天)

- [x] ~~任务1.1: 分析三模块接口依赖关系~~
- [ ] 任务1.2: 创建`fe_adapter.py`适配器
- [ ] 任务1.3: 修改3.3的`key_rotation.py`使用真实接口
- [ ] 任务1.4: 单元测试验证适配器

### 第二阶段：模块集成 (预计1-2天)

- [ ] 任务2.1: 实现3.2和3.3的接口集成
- [ ] 任务2.2: 编写集成测试脚本
- [ ] 任务2.3: 运行测试并修复问题

### 第三阶段：端到端验证 (预计1天)

- [ ] 任务3.1: 编写端到端测试场景
- [ ] 任务3.2: 性能测试和优化
- [ ] 任务3.3: 文档编写

### 第四阶段：提交和部署 (预计0.5天)

- [ ] 任务4.1: 代码review
- [ ] 任务4.2: 提交到主分支
- [ ] 任务4.3: 编写集成指南

---

## 6. 风险和注意事项

### 6.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 命名空间冲突 | 高 | 使用适配器模式隔离 |
| CSI数据格式不匹配 | 中 | 统一数据接口规范 |
| epoch同步延迟 | 中 | 多窗容忍策略 |
| Mock替换破坏现有测试 | 低 | 保留Mock作为备选 |

### 6.2 注意事项

1. **命名空间隔离**: 三个模块都使用`src`作为包名，需要通过适配器隔离
2. **测试数据一致性**: 确保三个模块使用相同的测试CSI数据格式
3. **向后兼容**: 保留Mock实现作为备选，支持独立测试
4. **确定性测试**: 集成测试时启用`deterministic_for_testing=True`
5. **digest一致性**: 确保register和authenticate使用相同的阈值

---

## 7. 文档产出

### 7.1 技术文档

- [x] `INTEGRATION_TEST_PLAN.md` - 本文档
- [ ] `INTEGRATION_GUIDE.md` - 集成指南
- [ ] `API_REFERENCE.md` - 统一API文档

### 7.2 测试文档

- [ ] `TEST_REPORT_INTEGRATION.md` - 集成测试报告
- [ ] `PERFORMANCE_BENCHMARK.md` - 性能基准测试

---

## 8. 附录

### 8.1 目录结构

```
Feature-Algorithm/
├── feature-encryption/          # 3.1模块
│   ├── src/
│   │   ├── feature_encryption.py
│   │   ├── config.py
│   │   └── ...
│   └── test_progressive.py
│
├── feature-authentication/      # 3.2模块
│   ├── src/
│   │   ├── mode2_strong_auth.py
│   │   ├── _fe_bridge.py
│   │   └── ...
│   └── tests/test_mode2.py
│
├── feature_synchronization/     # 3.3模块
│   ├── sync/
│   │   ├── key_rotation.py
│   │   └── ...
│   ├── adapters/                # 新增
│   │   └── fe_adapter.py
│   └── tests/test_integration.py
│
├── tests/                       # 新增：集成测试
│   ├── test_e2e_integration.py
│   ├── test_with_sync.py
│   └── test_key_rotation.py
│
├── INTEGRATION_TEST_PLAN.md     # 本文档
└── README.md
```

### 8.2 参考资料

- [3.1 feature-encryption 文档](./3.1-feature-encryption.md)
- [3.2 feature-authentication 文档](./3.2-feature-authentication.md)
- [3.3 feature-synchronization 文档](./3.3-feature-synchronization.md)
- [feature_synchronization README](./feature_synchronization/README.md)
- [feature_synchronization TEST_REPORT](./feature_synchronization/TEST_REPORT.md)

---

**文档维护**:
本文档随集成进度动态更新，最新版本见Git仓库。

**联系人**: 项目负责人
**最后更新**: 2025-11-19
