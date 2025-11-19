# 三模块集成系统部署与使用指南

## 目录
1. [系统要求](#系统要求)
2. [快速开始](#快速开始)
3. [详细配置](#详细配置)
4. [使用示例](#使用示例)
5. [故障排除](#故障排除)
6. [最佳实践](#最佳实践)

---

## 系统要求

### 硬件要求
- **IoT设备**: 支持WiFi CSI测量的无线网卡
- **网关/验证节点**: x86或ARM处理器，至少512MB RAM
- **网络**: 2.4GHz或5GHz WiFi

### 软件依赖
```bash
# Python版本
Python >= 3.8

# 必需的包
numpy >= 1.20.0
secrets (Python标准库)
hashlib (Python标准库)
struct (Python标准库)
logging (Python标准库)
```

### 安装依赖
```bash
pip install numpy
```

---

## 快速开始

### 1. 克隆仓库
```bash
git clone <repository-url>
cd Feature-Algorithm
```

### 2. 验证安装
运行端到端测试验证系统正常工作：
```bash
python test_end_to_end.py
```

预期输出：
```
✓ PASS: Full authentication flow
✓ PASS: Multi-device scenario
✓ PASS: Performance benchmark
✓✓✓ 所有端到端测试通过！
```

### 3. 运行集成测试
```bash
# 测试3.2 + 3.3集成
python test_integration_3.2_3.3.py
```

---

## 详细配置

### 网关配置

#### 步骤1: 初始化SynchronizationService
```python
from feature_synchronization.sync.synchronization_service import SynchronizationService

# 网关MAC地址（6字节）
gateway_mac = bytes.fromhex('AABBCCDDEEFF')

# 创建同步服务
gateway_sync = SynchronizationService(
    node_type='validator',           # 验证节点类型
    node_id=gateway_mac,              # 节点ID
    delta_t=30000,                    # Epoch周期30秒
    beacon_interval=5000,             # 信标广播间隔5秒
    domain="FeatureAuth",             # 域标识（必须与设备端一致）
    deterministic_for_testing=False   # 生产环境使用False
)
```

#### 步骤2: 初始化认证服务
```python
from src.mode2_strong_auth import VerifierSide
from src.config import AuthConfig
import secrets

# 认证配置
auth_config = AuthConfig()

# 网关签名密钥（应安全存储）
gateway_key = secrets.token_bytes(32)

# 创建验证端
gateway_auth = VerifierSide(
    config=auth_config,
    issuer_id=gateway_mac,
    issuer_key=gateway_key,
    sync_service=gateway_sync  # 关联同步服务
)
```

#### 步骤3: 启动服务
```python
print(f"Gateway initialized")
print(f"  MAC: {gateway_mac.hex()}")
print(f"  Current epoch: {gateway_sync.get_current_epoch()}")
print(f"  Ready to accept authentication requests")
```

---

### 设备配置

#### 步骤1: 初始化SynchronizationService
```python
from feature_synchronization.sync.synchronization_service import SynchronizationService

# 设备MAC地址（6字节）
device_mac = bytes.fromhex('001122334455')

# 创建同步服务
device_sync = SynchronizationService(
    node_type='device',              # 设备节点类型
    node_id=device_mac,               # 节点ID
    delta_t=30000,                    # Epoch周期（与网关一致）
    domain="FeatureAuth",             # 域标识（与网关一致）
    deterministic_for_testing=False   # 生产环境使用False
)
```

#### 步骤2: 初始化认证服务
```python
from src.mode2_strong_auth import DeviceSide
from src.config import AuthConfig

# 认证配置
auth_config = AuthConfig()

# 创建设备端
device_auth = DeviceSide(
    config=auth_config,
    sync_service=device_sync  # 关联同步服务
)
```

---

## 使用示例

### 完整认证流程

#### 设备端：生成认证请求
```python
import numpy as np
import secrets
from src.common import AuthContext

# 1. 采集物理层特征（CSI）
# 注意：实际应用中需要从无线网卡获取真实CSI
device_csi = measure_csi_from_wifi()  # 形状: (M_FRAMES, D_FEATURES)
# 示例：使用模拟数据
# device_csi = np.random.randn(6, 62)

# 2. 准备认证上下文
nonce = secrets.token_bytes(16)
context = AuthContext(
    src_mac=device_mac,       # 源MAC（设备）
    dst_mac=gateway_mac,      # 目标MAC（网关）
    epoch=0,                  # 会被sync_service自动更新
    nonce=nonce,              # 随机数
    seq=1,                    # 序列号
    alg_id='Mode2',           # 算法标识
    ver=1,                    # 版本
    csi_id=12345              # CSI测量ID
)

# 3. 创建认证请求
try:
    auth_req, session_key_device, feature_key = device_auth.create_auth_request(
        dev_id=device_mac,
        Z_frames=device_csi,
        context=context
    )

    print(f"✓ AuthReq generated")
    print(f"  Epoch: {auth_req.epoch}")
    print(f"  DevPseudo: {auth_req.dev_pseudo.hex()}")
    print(f"  Size: {len(auth_req.serialize())} bytes")

    # 4. 发送AuthReq到网关
    send_to_gateway(auth_req.serialize())

except Exception as e:
    print(f"✗ Failed to create AuthReq: {e}")
```

#### 网关端：验证认证请求
```python
import numpy as np

# 1. 接收AuthReq
auth_req_bytes = receive_from_device()
auth_req = AuthReq.deserialize(auth_req_bytes)

# 2. 采集网关端CSI（与设备测量同一信道）
gateway_csi = measure_csi_from_wifi()  # 形状: (M_FRAMES, D_FEATURES)
# 示例：使用模拟数据
# gateway_csi = device_csi.copy()  # 完美信道互惠性

# 3. 设备注册（首次认证需要）
# 注意：实际应用中应通过安全通道预先注册
gateway_auth.register_device(
    dev_id=device_mac,
    K=feature_key,  # 从带外渠道获取或首次注册时交换
    epoch=auth_req.epoch
)

# 4. 验证认证请求
try:
    result = gateway_auth.verify_auth_request(
        auth_req=auth_req,
        Z_frames=gateway_csi
    )

    if result.success:
        print(f"✓✓✓ Authentication SUCCESSFUL")
        print(f"  Session key: {result.session_key.hex()[:32]}...")
        print(f"  MAT token size: {len(result.mat_token.serialize())} bytes")

        # 5. 发送MAT token回设备
        send_to_device(result.mat_token.serialize())
    else:
        print(f"✗ Authentication FAILED")
        print(f"  Reason: {result.reason}")

except Exception as e:
    print(f"✗ Verification error: {e}")
```

---

### 多设备管理示例

```python
# 网关端管理多个设备
class GatewayManager:
    def __init__(self, gateway_mac, gateway_key):
        self.gateway_sync = SynchronizationService(
            node_type='validator',
            node_id=gateway_mac,
            delta_t=30000,
            domain="FeatureAuth"
        )

        self.gateway_auth = VerifierSide(
            config=AuthConfig(),
            issuer_id=gateway_mac,
            issuer_key=gateway_key,
            sync_service=self.gateway_sync
        )

        self.devices = {}  # device_mac -> device_info

    def register_device(self, device_mac, feature_key, epoch):
        """注册新设备"""
        self.gateway_auth.register_device(device_mac, feature_key, epoch)
        self.devices[device_mac] = {
            'registered_at': time.time(),
            'last_auth': None,
            'auth_count': 0
        }
        print(f"Device {device_mac.hex()} registered")

    def authenticate_device(self, auth_req, gateway_csi):
        """认证设备"""
        result = self.gateway_auth.verify_auth_request(auth_req, gateway_csi)

        if result.success:
            # 更新设备信息
            device_mac = self.locate_device_by_pseudo(auth_req.dev_pseudo)
            if device_mac in self.devices:
                self.devices[device_mac]['last_auth'] = time.time()
                self.devices[device_mac]['auth_count'] += 1

        return result

    def get_device_stats(self):
        """获取设备统计"""
        return {
            'total_devices': len(self.devices),
            'devices': self.devices
        }

# 使用示例
gateway_mgr = GatewayManager(gateway_mac, gateway_key)

# 注册设备
for device_mac in device_list:
    gateway_mgr.register_device(device_mac, feature_key, 0)

# 处理认证请求
result = gateway_mgr.authenticate_device(auth_req, gateway_csi)
```

---

## 故障排除

### 问题1: Digest不匹配
```
错误: ✗ Digest mismatch (configuration inconsistency)
```

**原因**: 设备和网关的domain配置不一致

**解决方案**:
```python
# 确保设备和网关使用相同的domain
device_sync = SynchronizationService(..., domain="FeatureAuth")
gateway_sync = SynchronizationService(..., domain="FeatureAuth")
```

---

### 问题2: Epoch超出范围
```
错误: ✗ Epoch 5 is out of valid range
```

**原因**: 设备和网关的时钟不同步

**解决方案**:
1. 使用NTP同步系统时间
2. 增加epoch周期delta_t
3. 实现beacon广播机制同步epoch

```python
# 网关定期广播beacon
def broadcast_beacon():
    beacon = gateway_sync.create_beacon()
    broadcast_to_network(beacon)

# 设备接收并处理beacon
def handle_beacon(beacon):
    device_sync.process_beacon(beacon)
```

---

### 问题3: Tag验证失败
```
错误: ✗ Tag verification failed
```

**可能原因**:
1. CSI测量差异过大（信道条件差）
2. nonce不一致
3. validator_mac不匹配

**解决方案**:
```python
# 1. 确保CSI测量质量
# - 在同一时间窗口测量
# - 避免障碍物移动
# - 选择稳定的信道

# 2. 确认nonce一致
# 设备端和网关端使用AuthReq中的相同nonce

# 3. 确认validator_mac一致
# 设备端: context.dst_mac = gateway_mac
# 网关端: self.issuer_id = gateway_mac
```

---

### 问题4: KeyRotation不可用
```
错误: RuntimeError: Key rotation manager not available
```

**原因**: SynchronizationService未正确初始化KeyRotationManager

**解决方案**:
```python
# 检查node_type是否正确
SynchronizationService(
    node_type='validator',  # 或 'device', 不能是其他值
    ...
)
```

---

## 最佳实践

### 1. 安全配置

#### 密钥管理
```python
# 不要硬编码密钥
# 错误示例:
gateway_key = bytes.fromhex('0123456789...')  # ❌

# 正确示例:
import secrets
gateway_key = secrets.token_bytes(32)  # ✓
# 或从安全存储加载:
gateway_key = load_from_secure_storage()  # ✓
```

#### 域隔离
```python
# 不同应用使用不同的domain
production_sync = SynchronizationService(..., domain="ProductionAuth")
testing_sync = SynchronizationService(..., domain="TestingAuth")
```

---

### 2. 性能优化

#### 密钥缓存
```python
# 避免重复派生相同的密钥
# generate_or_get_key_material已实现缓存
key_material = sync_service.generate_or_get_key_material(
    device_mac=device_mac,
    epoch=epoch,
    feature_vector=csi,
    nonce=nonce
)
```

#### 批量处理
```python
# 批量认证多个设备
def batch_authenticate(auth_requests, csi_measurements):
    results = []
    for auth_req, csi in zip(auth_requests, csi_measurements):
        result = gateway_auth.verify_auth_request(auth_req, csi)
        results.append(result)
    return results
```

---

### 3. 可靠性

#### 错误处理
```python
def robust_authentication(device_auth, device_mac, csi, context, max_retries=3):
    """带重试机制的认证"""
    for attempt in range(max_retries):
        try:
            auth_req, session_key, feature_key = device_auth.create_auth_request(
                dev_id=device_mac,
                Z_frames=csi,
                context=context
            )
            return auth_req, session_key, feature_key
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            print(f"Retry {attempt + 1}/{max_retries}: {e}")
            time.sleep(1)
```

#### 日志记录
```python
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('authentication.log'),
        logging.StreamHandler()
    ]
)

# 使用日志
logger = logging.getLogger(__name__)
logger.info(f"Device {device_mac.hex()} authenticated successfully")
```

---

### 4. 测试策略

#### 单元测试
```bash
# 测试单个模块
python -m pytest feature_synchronization/tests/
python -m pytest feature-authentication/tests/
```

#### 集成测试
```bash
# 测试模块间集成
python test_integration_3.2_3.3.py
```

#### 端到端测试
```bash
# 测试完整流程
python test_end_to_end.py
```

#### 压力测试
```python
def stress_test(num_devices=100, num_auth_per_device=10):
    """压力测试"""
    import time

    start = time.time()
    success_count = 0

    for i in range(num_devices):
        device_mac = secrets.token_bytes(6)
        for j in range(num_auth_per_device):
            try:
                # 执行认证
                result = perform_authentication(device_mac)
                if result.success:
                    success_count += 1
            except Exception as e:
                print(f"Error: {e}")

    elapsed = time.time() - start
    total = num_devices * num_auth_per_device

    print(f"Stress Test Results:")
    print(f"  Total authentications: {total}")
    print(f"  Successful: {success_count} ({100*success_count/total:.1f}%)")
    print(f"  Time: {elapsed:.2f}s")
    print(f"  Throughput: {total/elapsed:.1f} auth/s")
```

---

## 生产部署检查清单

### 部署前
- [ ] 所有测试通过（单元、集成、端到端）
- [ ] 密钥管理方案就绪
- [ ] 日志系统配置完成
- [ ] 监控告警设置完成
- [ ] 备份恢复方案制定

### 配置检查
- [ ] `deterministic_for_testing=False`（生产环境）
- [ ] domain配置一致（所有节点）
- [ ] delta_t合理（根据网络条件）
- [ ] beacon_interval合理（根据同步需求）

### 性能验证
- [ ] 认证延迟 < 100ms（需求）
- [ ] 吞吐量满足并发需求
- [ ] 内存使用合理（< 100MB per node）
- [ ] CPU使用合理（< 20% idle state）

### 安全审计
- [ ] 所有密钥安全存储
- [ ] 通信加密启用
- [ ] 访问控制配置
- [ ] 日志审计启用

---

## 附录

### A. AuthReq格式
```
AuthReq结构（71字节）:
├── dev_pseudo (12 bytes)   - 设备伪名
├── csi_id (4 bytes)        - CSI测量ID
├── epoch (4 bytes)         - 时间窗编号
├── nonce (16 bytes)        - 随机数
├── seq (4 bytes)           - 序列号
├── alg_id (5 bytes)        - 算法标识 "Mode2"
├── ver (2 bytes)           - 版本号
├── digest (8 bytes)        - 配置摘要
└── tag (16 bytes)          - 认证标签
```

### B. MAT Token格式
```
MAT结构（74字节）:
├── dev_id (6 bytes)        - 设备ID
├── issuer_id (6 bytes)     - 签发者ID
├── issued_at (8 bytes)     - 签发时间
├── expires_at (8 bytes)    - 过期时间
├── session_key (32 bytes)  - 会话密钥
└── signature (14 bytes)    - 签名
```

### C. 性能参数参考
```
推荐配置（室内IoT环境）:
- delta_t: 30000ms (30秒)
- beacon_interval: 5000ms (5秒)
- M_FRAMES: 6
- D_FEATURES: 62
- TARGET_BITS: 128

高性能配置（数据中心）:
- delta_t: 10000ms (10秒)
- beacon_interval: 2000ms (2秒)
- M_FRAMES: 3
- D_FEATURES: 62
- TARGET_BITS: 128
```

---

## 支持与反馈

### 问题报告
如遇到问题，请提供：
1. 错误信息和堆栈追踪
2. 配置参数
3. 日志文件
4. 测试结果

### 文档版本
- **版本**: 1.0
- **更新日期**: 2025-11-19
- **适用系统**: Feature-Algorithm三模块集成v1.0

---

**Happy Authenticating! 🚀**
