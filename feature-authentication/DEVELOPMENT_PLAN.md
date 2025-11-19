# 3.2模块开发计划

**创建时间**: 2025-11-19
**负责人**: Claude Code Agent
**预计工期**: 1个开发周期

---

## 一、开发目标

实现基于特征的两种认证模式：
1. **模式二（优先）**: 基于特征加密的强认证 - 密码学级别的身份验证
2. **模式一（可选）**: 基于RFF的快速轻量认证 - 毫秒级快速决策

---

## 二、模块架构设计

### 2.1 目录结构

```
feature-authentication/
├── src/
│   ├── __init__.py
│   ├── config.py              # 配置管理
│   ├── common.py              # 共同数据结构
│   ├── mode1_rff_auth.py      # 模式一：RFF快速认证
│   ├── mode2_strong_auth.py   # 模式二：强认证（核心）
│   ├── token_manager.py       # 令牌管理（Token_fast和MAT）
│   └── utils.py               # 工具函数
├── tests/
│   ├── test_mode1.py
│   ├── test_mode2.py
│   ├── test_integration.py
│   └── test_progressive.py    # 渐进式测试框架
├── docs/
│   ├── ALGORITHM_ANALYSIS.md  # 算法分析（已完成）
│   ├── DEVELOPMENT_PLAN.md    # 本文档
│   └── API_SPEC.md            # API规范
└── logs/                      # 测试日志输出

### 2.2 模块依赖关系

```
mode2_strong_auth.py
    ↓ 依赖
feature_encryption.py (3.1模块)
    ↓ 提供
K, Ks, S, digest

mode1_rff_auth.py
    ↓ 可选依赖
feature_encryption.py (仅当需要Ks时)
```

---

## 三、核心数据结构设计

### 3.1 共同数据结构 (common.py)

```python
@dataclass
class DeviceIdentity:
    """设备标识"""
    dev_id: bytes          # 真实MAC地址 (6 bytes)
    dev_pseudo: bytes      # 伪名 (12 bytes, 可选)
    epoch: int             # 时间窗编号

@dataclass
class AuthContext:
    """认证上下文"""
    src_mac: bytes         # 源MAC
    dst_mac: bytes         # 目标MAC
    epoch: int             # 时间窗编号
    nonce: bytes           # 随机数 (16 bytes)
    seq: int               # 序号
    alg_id: str            # 算法标识
    ver: int               # 版本号
    csi_id: int            # CSI窗口标识 (使用帧序号)

@dataclass
class AuthResult:
    """认证结果"""
    success: bool          # 是否成功
    mode: str              # 使用的模式 ("mode1" / "mode2")
    token: Optional[bytes] # 令牌 (Token_fast或MAT)
    session_key: Optional[bytes]  # 会话密钥Ks
    reason: Optional[str]  # 失败原因
```

### 3.2 模式一数据结构

```python
@dataclass
class RFFJudgment:
    """物理层RFF判定结果"""
    dev_id: bytes
    rff_pass: bool
    rff_score: float       # 0.0-1.0
    snr: float             # 信噪比
    ver: str               # RFF模型版本
    timestamp: int

@dataclass
class TokenFast:
    """快速令牌"""
    dev_id: bytes
    t_start: int           # 开始时间(Unix时间戳)
    t_expire: int          # 过期时间
    policy: str            # 策略标识
    mac: bytes             # 完整性校验值 (16 bytes)
```

### 3.3 模式二数据结构

```python
@dataclass
class AuthReq:
    """认证请求报文"""
    dev_pseudo: bytes      # 伪名 (12 bytes)
    csi_id: int            # CSI窗口标识 (4 bytes)
    epoch: int             # 时间窗编号 (4 bytes)
    nonce: bytes           # 随机数 (16 bytes)
    seq: int               # 序号 (4 bytes)
    alg_id: str            # 算法标识
    ver: int               # 版本号
    digest: bytes          # 配置摘要 (32 bytes)
    tag: bytes             # 认证标签 (16 bytes)

@dataclass
class MAT:
    """准入令牌 (MAC Admission Token)"""
    issuer: bytes          # 签发者标识
    dev_pseudo: bytes      # 设备伪名
    epoch: int             # 时间窗编号
    ttl: int               # 有效期(秒)
    mat_id: bytes          # 令牌唯一标识 (16 bytes)
    signature: bytes       # 签名 (32 bytes)
```

---

## 四、详细开发步骤

### 第一阶段：基础设施 (预计200行)

#### Step 1.1: 配置管理 (config.py)

```python
@dataclass
class AuthConfig:
    # 模式一配置
    MODE1_ENABLED: bool = False  # 默认不启用
    RFF_THRESHOLD: float = 0.8   # RFF得分阈值
    TOKEN_FAST_TTL: int = 60     # Token_fast有效期(秒)

    # 模式二配置
    MODE2_ENABLED: bool = True   # 默认启用
    TAG_LENGTH: int = 16         # Tag长度(字节)
    PSEUDO_LENGTH: int = 12      # DevPseudo长度
    MAT_TTL: int = 300           # MAT有效期(秒)

    # 密码学配置
    HASH_ALGORITHM: str = 'blake3'
    MAC_ALGORITHM: str = 'blake3'

    # 日志配置
    LOG_LEVEL: str = 'INFO'
    LOG_FILE: Optional[str] = None
```

**日志点**:
- ✅ 配置加载成功/失败
- ✅ 参数验证结果

#### Step 1.2: 共同数据结构 (common.py)

实现所有dataclass和基础验证逻辑。

**日志点**:
- ✅ 数据结构创建和验证

#### Step 1.3: 工具函数 (utils.py)

```python
def blake3_hash(data: bytes) -> bytes:
    """BLAKE3哈希"""

def blake3_mac(key: bytes, data: bytes) -> bytes:
    """BLAKE3-MAC"""

def truncate(data: bytes, length: int) -> bytes:
    """截断到指定长度"""

def constant_time_compare(a: bytes, b: bytes) -> bool:
    """常时比较（防时序攻击）"""
```

**日志点**:
- 🔍 DEBUG: 输入数据长度、输出长度
- ⚠️ WARNING: 长度异常

---

### 第二阶段：模式二核心实现 (预计500行)

#### Step 2.1: 设备端认证 (mode2_strong_auth.py - DeviceSide类)

```python
class DeviceSide:
    """设备端强认证"""

    def __init__(self, config: AuthConfig):
        self.config = config
        self.fe = FeatureEncryption(...)  # 集成3.1模块
        self.logger = logging.getLogger(__name__)

    def generate_pseudo(self, K: bytes, epoch: int) -> bytes:
        """生成伪名

        DevPseudo = Trunc₉₆(BLAKE3("Pseudo"‖K‖epoch))
        """
        self.logger.info(f"Generating DevPseudo for epoch={epoch}")
        # 实现...
        self.logger.debug(f"DevPseudo: {pseudo.hex()[:24]}...")
        return pseudo

    def compute_tag(self, K: bytes, context: AuthContext) -> bytes:
        """计算认证标签

        Tag = Trunc₁₂₈(BLAKE3-MAC(K, SrcMAC‖DstMAC‖epoch‖nonce‖seq‖algID‖csi_id))
        """
        self.logger.info("Computing authentication Tag")
        # 构造消息
        msg = context.src_mac + context.dst_mac + ...
        self.logger.debug(f"Tag message length: {len(msg)} bytes")

        tag = blake3_mac(K, msg)[:16]
        self.logger.info(f"Tag computed: {tag.hex()}")
        return tag

    def create_auth_request(
        self,
        dev_id: bytes,
        Z_frames: np.ndarray,
        context: AuthContext
    ) -> Tuple[AuthReq, bytes]:
        """创建认证请求

        Returns:
            (AuthReq, Ks): 认证请求和会话密钥
        """
        self.logger.info(f"Creating AuthReq for device {dev_id.hex()}")

        # Step 1: 调用3.1生成密钥
        self.logger.info("Step 1: Calling FeatureKeyGen...")
        key_output, metadata = self.fe.register(
            device_id=dev_id.hex(),
            Z_frames=Z_frames,
            context=...,  # 转换为3.1的Context
        )
        self.logger.info(f"FeatureKeyGen success, K={key_output.K.hex()[:20]}...")

        # Step 2: 生成伪名
        self.logger.info("Step 2: Generating DevPseudo...")
        dev_pseudo = self.generate_pseudo(key_output.K, context.epoch)

        # Step 3: 计算Tag
        self.logger.info("Step 3: Computing Tag...")
        tag = self.compute_tag(key_output.K, context)

        # Step 4: 构造AuthReq
        self.logger.info("Step 4: Constructing AuthReq...")
        auth_req = AuthReq(
            dev_pseudo=dev_pseudo,
            csi_id=context.csi_id,
            epoch=context.epoch,
            nonce=context.nonce,
            seq=context.seq,
            alg_id=context.alg_id,
            ver=context.ver,
            digest=key_output.digest,
            tag=tag
        )

        self.logger.info("AuthReq created successfully")
        return auth_req, key_output.Ks
```

**日志点**:
- ℹ️ INFO: 每个步骤的开始和完成
- 🔍 DEBUG: 中间值（前20字节）
- ⚠️ WARNING: 异常情况
- ❌ ERROR: 失败情况

#### Step 2.2: 验证端认证 (mode2_strong_auth.py - VerifierSide类)

```python
class VerifierSide:
    """验证端强认证"""

    def __init__(self, config: AuthConfig):
        self.config = config
        self.fe = FeatureEncryption(...)
        self.device_registry: Dict[bytes, DeviceInfo] = {}  # DevPseudo映射
        self.logger = logging.getLogger(__name__)

    def locate_device(self, dev_pseudo: bytes, epoch: int) -> Optional[bytes]:
        """根据伪名定位设备

        Returns:
            dev_id: 真实设备ID，如果未找到返回None
        """
        self.logger.info(f"Locating device for pseudo={dev_pseudo.hex()[:24]}...")

        # 遍历所有注册设备，计算伪名匹配
        for dev_id, info in self.device_registry.items():
            expected_pseudo = self.generate_pseudo(info.K, epoch)
            if constant_time_compare(expected_pseudo, dev_pseudo):
                self.logger.info(f"Device found: {dev_id.hex()}")
                return dev_id

        self.logger.warning("Device not found in registry")
        return None

    def verify_auth_request(
        self,
        auth_req: AuthReq,
        Z_frames: np.ndarray
    ) -> AuthResult:
        """验证认证请求

        Returns:
            AuthResult: 认证结果
        """
        self.logger.info("="*60)
        self.logger.info("Starting authentication verification")
        self.logger.info(f"AuthReq: pseudo={auth_req.dev_pseudo.hex()[:24]}..., epoch={auth_req.epoch}")

        # Step 1: 设备定位
        self.logger.info("Step 1: Locating device...")
        dev_id = self.locate_device(auth_req.dev_pseudo, auth_req.epoch)
        if dev_id is None:
            self.logger.error("Device not registered")
            return AuthResult(success=False, mode="mode2", reason="device_not_registered")

        # Step 2: 重构密钥
        self.logger.info("Step 2: Reconstructing keys...")
        key_output, success = self.fe.authenticate(
            device_id=dev_id.hex(),
            Z_frames=Z_frames,
            context=...,
        )

        if not success:
            self.logger.error("FeatureKeyGen failed (BCH decode failed)")
            return AuthResult(success=False, mode="mode2", reason="feature_mismatch")

        self.logger.info(f"Keys reconstructed: K'={key_output.K.hex()[:20]}...")

        # Step 3: 配置一致性检查
        self.logger.info("Step 3: Checking digest consistency...")
        if not constant_time_compare(key_output.digest, auth_req.digest):
            self.logger.error("Digest mismatch (config inconsistency)")
            return AuthResult(success=False, mode="mode2", reason="digest_mismatch")

        self.logger.info("Digest check passed")

        # Step 4: 标签校验
        self.logger.info("Step 4: Verifying Tag...")
        tag_prime = self.compute_tag(key_output.K, ...)

        if not constant_time_compare(tag_prime, auth_req.tag):
            self.logger.error("Tag verification failed")
            self.logger.debug(f"Expected Tag: {tag_prime.hex()}")
            self.logger.debug(f"Received Tag: {auth_req.tag.hex()}")
            return AuthResult(success=False, mode="mode2", reason="tag_mismatch")

        self.logger.info("Tag verification passed ✓")

        # Step 5: 签发MAT
        self.logger.info("Step 5: Issuing MAT...")
        mat = self.issue_mat(auth_req.dev_pseudo, auth_req.epoch)

        self.logger.info("Authentication successful ✓✓✓")
        self.logger.info("="*60)

        return AuthResult(
            success=True,
            mode="mode2",
            token=mat.serialize(),
            session_key=key_output.Ks,
            reason=None
        )
```

**日志点**:
- ℹ️ INFO: 每个步骤的边界、关键决策
- 🔍 DEBUG: 中间计算值
- ⚠️ WARNING: 边界情况
- ❌ ERROR: 失败原因详细记录

#### Step 2.3: MAT管理 (token_manager.py)

```python
class MATManager:
    """准入令牌管理"""

    def issue_mat(
        self,
        issuer_id: bytes,
        dev_pseudo: bytes,
        epoch: int,
        ttl: int
    ) -> MAT:
        """签发MAT"""
        self.logger.info(f"Issuing MAT for {dev_pseudo.hex()[:24]}...")

        mat_id = secrets.token_bytes(16)

        # 计算签名
        msg = issuer_id + dev_pseudo + struct.pack('<II', epoch, ttl) + mat_id
        signature = blake3_mac(self.issuer_key, msg)[:32]

        mat = MAT(
            issuer=issuer_id,
            dev_pseudo=dev_pseudo,
            epoch=epoch,
            ttl=ttl,
            mat_id=mat_id,
            signature=signature
        )

        self.logger.info(f"MAT issued: id={mat_id.hex()[:16]}..., ttl={ttl}s")
        return mat

    def verify_mat(self, mat: MAT) -> bool:
        """验证MAT"""
        self.logger.info(f"Verifying MAT: id={mat.mat_id.hex()[:16]}...")

        # 检查过期
        # 验证签名
        # ...

        self.logger.info("MAT verification passed ✓")
        return True
```

---

### 第三阶段：模式一实现 (可选，预计200行)

#### Step 3.1: RFF快速认证 (mode1_rff_auth.py)

```python
class RFFAuthenticator:
    """RFF快速认证"""

    def authenticate_rff(
        self,
        judgment: RFFJudgment,
        whitelist: Set[bytes]
    ) -> AuthResult:
        """RFF快速认证"""
        self.logger.info("="*60)
        self.logger.info("RFF Fast Authentication")
        self.logger.info(f"Device: {judgment.dev_id.hex()}, Score: {judgment.rff_score:.3f}")

        # Step 1: 白名单检查
        if judgment.dev_id not in whitelist:
            self.logger.warning("Device not in whitelist")
            return AuthResult(success=False, mode="mode1", reason="not_in_whitelist")

        # Step 2: RFF判定检查
        if not judgment.rff_pass:
            self.logger.warning("RFF judgment failed")
            return AuthResult(success=False, mode="mode1", reason="rff_failed")

        if judgment.rff_score < self.config.RFF_THRESHOLD:
            self.logger.warning(f"RFF score below threshold ({judgment.rff_score} < {self.config.RFF_THRESHOLD})")
            return AuthResult(success=False, mode="mode1", reason="score_too_low")

        # Step 3: 签发Token_fast
        self.logger.info("Issuing Token_fast...")
        token = self.issue_token_fast(judgment.dev_id)

        self.logger.info("RFF authentication successful ✓")
        return AuthResult(success=True, mode="mode1", token=token.serialize())
```

---

### 第四阶段：测试 (预计400行)

#### Step 4.1: 模式二集成测试 (test_mode2.py)

```python
def test_mode2_success():
    """测试模式二成功场景"""
    logger.info("Test: Mode2 Success Scenario")

    # 模拟设备端和验证端
    device = DeviceSide(config)
    verifier = VerifierSide(config)

    # 生成模拟特征
    Z_frames = simulate_csi_features()

    # 设备端创建AuthReq
    auth_req, Ks_device = device.create_auth_request(dev_id, Z_frames, context)

    # 验证端验证
    result = verifier.verify_auth_request(auth_req, Z_frames)

    assert result.success == True
    assert result.session_key == Ks_device
    logger.info("✓ Test passed")

def test_mode2_tag_mismatch():
    """测试Tag不匹配"""
    logger.info("Test: Tag Mismatch")

    # 篡改Tag
    auth_req.tag = secrets.token_bytes(16)

    result = verifier.verify_auth_request(auth_req, Z_frames)

    assert result.success == False
    assert result.reason == "tag_mismatch"
    logger.info("✓ Test passed (correctly rejected)")
```

#### Step 4.2: 渐进式测试框架 (test_progressive.py)

类似3.1的test_progressive.py，逐步测试每个模块。

---

## 五、关键技术决策

### 5.1 已明确的设计决策

| 问题 | 决策 | 理由 |
|------|------|------|
| K_mgmt来源 | 使用issuer_key，从安全存储加载 | 简化实现，符合实际部署 |
| csi_id定义 | 使用帧序号seq | 简单明确，易于同步 |
| MAT签名算法 | 单验证者使用BLAKE3-MAC | 简化实现，性能好 |
| 多验证者聚合 | 暂不实现 | 复杂度高，非核心功能 |
| 模式一优先级 | 可选，后期实现 | 聚焦核心模式二 |

### 5.2 参数配置

| 参数 | 值 | 说明 |
|------|-----|------|
| TAG_LENGTH | 16 bytes | 128位安全强度 |
| PSEUDO_LENGTH | 12 bytes | 96位，足够唯一性 |
| MAT_TTL | 300秒 | 5分钟有效期 |
| RFF_THRESHOLD | 0.8 | 80%置信度 |
| TOKEN_FAST_TTL | 60秒 | 1分钟快速令牌 |

---

## 六、开发时间表

| 阶段 | 任务 | 预计时间 | 状态 |
|------|------|----------|------|
| 第1阶段 | 基础设施(config, common, utils) | 1小时 | ⏳ 待开始 |
| 第2阶段 | 模式二核心实现 | 2小时 | ⏳ 待开始 |
| 第3阶段 | 模式一实现(可选) | 1小时 | ⏸️ 暂缓 |
| 第4阶段 | 测试和调试 | 1-2小时 | ⏳ 待开始 |
| 第5阶段 | 代码审查和文档 | 1小时 | ⏳ 待开始 |

---

## 七、风险和缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 3.1集成问题 | 高 | 先验证3.1接口，确保兼容 |
| 时间窗口同步 | 中 | 依赖3.3模块(暂时使用固定epoch测试) |
| 性能问题 | 中 | 充分日志，性能监控点 |
| DevPseudo反查慢 | 低 | 维护映射表(epoch更新) |

---

## 八、验收标准

### 8.1 功能完整性
- ✅ 模式二设备端AuthReq生成正确
- ✅ 模式二验证端Tag校验正确
- ✅ MAT签发和验证正确
- ✅ 与3.1模块集成成功
- ✅ digest一致性检查工作
- ⏸️ 模式一(可选)

### 8.2 测试覆盖率
- ✅ 单元测试覆盖所有核心函数
- ✅ 集成测试覆盖完整流程
- ✅ 边界情况测试(Tag错误、digest不一致等)
- ✅ 日志完整，便于调试

### 8.3 代码质量
- ✅ 符合PEP 8规范
- ✅ 完整的类型提示
- ✅ 详细的文档字符串
- ✅ 充分的日志覆盖

---

## 九、下一步行动

1. ✅ 实现config.py
2. ✅ 实现common.py
3. ✅ 实现utils.py
4. ✅ 实现mode2_strong_auth.py (DeviceSide)
5. ✅ 实现mode2_strong_auth.py (VerifierSide)
6. ✅ 实现token_manager.py
7. ✅ 编写测试用例
8. ✅ 执行测试和调试
9. ✅ 代码审查

---

**计划完成时间**: 2025-11-19
**开始实施**: 立即开始
