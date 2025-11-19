# 开发指南

## 项目组织结构

本项目将"基于特征加密的MAC身份认证方案"分为三个独立模块进行开发：

```
Feature-Algorithm/
├── README.md                      # 项目总体说明
├── DEVELOPMENT.md                 # 本文件 - 开发指南
├── prd.docx                       # 原始需求文档
├── 3.1.md                         # 需求文档：特征加密算法
├── 3.2.md                         # 需求文档：认证方法
├── 3.3.md                         # 需求文档：同步机制
│
├── feature-encryption/            # 模块1：基于特征的加密算法
│   ├── README.md                  # 模块说明
│   ├── requirements.md            # 需求文档副本
│   ├── src/                       # 源代码
│   ├── tests/                     # 测试代码
│   └── docs/                      # 开发文档
│
├── feature-authentication/        # 模块2：基于特征的认证方法
│   ├── README.md                  # 模块说明
│   ├── requirements.md            # 需求文档副本
│   ├── src/                       # 源代码
│   ├── tests/                     # 测试代码
│   └── docs/                      # 开发文档
│
└── feature-synchronization/       # 模块3：周期变化同步机制
    ├── README.md                  # 模块说明
    ├── requirements.md            # 需求文档副本
    ├── src/                       # 源代码
    ├── tests/                     # 测试代码
    └── docs/                      # 开发文档
```

## 开发顺序

按照依赖关系，建议的开发顺序为：

### 第一阶段：特征加密算法（feature-encryption）

这是整个系统的基础，为后续模块提供密钥派生功能。

**开发步骤**：
1. 分析需求文档，明确参数边界
2. 编写算法规范文档
3. 实现核心算法
4. 编写单元测试
5. 代码审查与优化

**关键文件**：
- `src/feature_processor.py` - 特征预处理
- `src/quantizer.py` - 量化与投票
- `src/fuzzy_extractor.py` - 模糊提取器
- `src/key_derivation.py` - 密钥派生

### 第二阶段：认证方法（feature-authentication）

依赖第一阶段的密钥派生功能。

**开发步骤**：
1. 分析需求文档，定义协议规范
2. 设计报文格式
3. 实现模式一（RFF快速认证）
4. 实现模式二（强认证）
5. 编写单元测试和集成测试
6. 代码审查与优化

**关键文件**：
- `src/mode1_rff_auth.py` - 模式一实现
- `src/mode2_strong_auth.py` - 模式二实现
- `src/device_side.py` - 设备端逻辑
- `src/verifier_side.py` - 验证端逻辑

### 第三阶段：同步机制（feature-synchronization）

依赖前两个模块，实现分布式同步。

**开发步骤**：
1. 分析需求文档，设计同步协议
2. 实现信标管理
3. 实现时间窗同步
4. 实现凭证轮换
5. 实现失步处理
6. 编写单元测试和集成测试
7. 代码审查与优化

**关键文件**：
- `src/beacon_manager.py` - 信标管理
- `src/time_sync.py` - 时间窗同步
- `src/config_sync.py` - 参数同步
- `src/credential_rotation.py` - 凭证轮换

## 开发规范

### 代码风格

- 使用Python 3.8+
- 遵循PEP 8编码规范
- 使用类型提示（Type Hints）
- 编写清晰的文档字符串

### 测试要求

- 单元测试覆盖率 ≥ 80%
- 关键算法需要边界测试
- 提供集成测试用例
- 使用pytest框架

### 文档要求

每个模块需要包含：
- **算法规范文档**：详细的算法描述和伪代码
- **参数配置说明**：所有参数的定义、边界和默认值
- **开发计划**：任务分解和进度跟踪
- **API文档**：接口说明和使用示例

### 代码审查检查清单

- [ ] 算法逻辑正确性
- [ ] 参数边界检查
- [ ] 错误处理完备
- [ ] 代码可读性
- [ ] 性能优化
- [ ] 安全性考虑
- [ ] 测试覆盖率
- [ ] 文档完整性

## 技术栈

### 密码学库

- **hashlib** / **pycryptodome**：BLAKE3哈希（或使用blake3-py）
- **cryptography**：HKDF密钥派生
- **bchlib**：BCH纠错码

### 数值计算

- **numpy**：数值计算和矩阵运算
- **scipy**：信号处理

### 测试工具

- **pytest**：测试框架
- **pytest-cov**：覆盖率统计
- **hypothesis**：属性测试

### 开发工具

- **black**：代码格式化
- **pylint** / **flake8**：代码检查
- **mypy**：类型检查

## 当前进度

### 模块1：feature-encryption
- [x] 创建目录结构
- [x] 编写模块README
- [ ] 分析需求并明确参数
- [ ] 编写算法规范
- [ ] 实现代码
- [ ] 编写测试
- [ ] 代码审查

### 模块2：feature-authentication
- [x] 创建目录结构
- [x] 编写模块README
- [ ] 待开发

### 模块3：feature-synchronization
- [x] 创建目录结构
- [x] 编写模块README
- [ ] 待开发

## 下一步工作

当前优先级：**开始模块1（feature-encryption）的开发**

具体任务：
1. 分析3.1.md需求文档
2. 明确所有参数的边界和默认值
3. 编写详细的算法规范文档
4. 设计开发步骤
5. 实现核心算法
6. 编写测试用例
7. 代码审查

## 联系与协作

- 需求变更：更新对应模块的requirements.md
- 接口变更：及时通知依赖模块
- 问题讨论：在对应模块的docs目录下记录决策

## 参考资料

- [README.md](./README.md) - 项目总体说明
- [3.1.md](./3.1.md) - 特征加密算法需求
- [3.2.md](./3.2.md) - 认证方法需求
- [3.3.md](./3.3.md) - 同步机制需求
