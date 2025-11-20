# Feature Authentication Module - 测试说明

## 📋 测试概述

本模块提供了完整的测试套件，覆盖两种认证模式及其集成功能。

## 🚀 快速开始

### 运行所有测试

```bash
cd feature-authentication
python run_all_tests.py
```

### 运行单个测试套件

```bash
# 模式一测试
python -m tests.test_mode1

# 模式二测试
python -m tests.test_mode2

# 集成测试
python -m tests.test_integration
```

## 📦 测试结构

```
feature-authentication/
├── run_all_tests.py          # 🎯 全局测试脚本（推荐使用）
├── tests/
│   ├── test_mode1.py         # 模式一：RFF快速认证测试
│   ├── test_mode2.py         # 模式二：强认证测试
│   └── test_integration.py   # 两种模式集成测试
└── src/                      # 源代码
```

## 🧪 测试覆盖

### `run_all_tests.py` - 全局测试脚本

**功能：** 一键运行所有测试套件，提供完整的模块功能验证

**测试内容：**
- ✅ 模式一（RFF快速认证）- 5个测试场景
- ✅ 模式二（强认证）- 3个测试场景
- ✅ 双模式集成 - 3个测试场景
- ✅ **总计：11个测试场景**

**输出示例：**
```
================================================================================
COMPREHENSIVE TEST SUMMARY
================================================================================

[OK] Mode 1: RFF Fast Authentication Tests
[OK] Mode 2: Strong Authentication Tests
[OK] Integration: Dual-Mode Tests

Total Test Suites: 3
Passed: 3
Failed: 0

================================================================================
[OK][OK][OK] ALL TEST SUITES PASSED [OK][OK][OK]
================================================================================

Feature Authentication Module is fully functional:
  [OK] Mode 1 (RFF Fast Auth) - Working
  [OK] Mode 2 (Strong Auth) - Working
  [OK] Dual-Mode Integration - Working
```

### 测试详情

#### 1. 模式一测试 (`tests/test_mode1.py`)

**测试场景：**

| 测试名称 | 验证内容 | 状态 |
|---------|---------|------|
| `test_mode1_success` | 成功认证流程 | ✅ 通过 |
| `test_mode1_device_not_registered` | 未注册设备拒绝 | ✅ 通过 |
| `test_mode1_rff_score_below_threshold` | 低RFF得分拒绝 | ✅ 通过 |
| `test_mode1_low_snr` | 低信噪比处理 | ✅ 通过 |
| `test_mode1_token_revocation` | 令牌撤销机制 | ✅ 通过 |

**覆盖功能点：**
- 设备注册与管理
- RFF匹配与判定
- TokenFast签发与验证
- 阈值判断逻辑
- SNR因子影响
- 设备撤销机制

#### 2. 模式二测试 (`tests/test_mode2.py`)

**测试场景：**

| 测试名称 | 验证内容 | 状态 |
|---------|---------|------|
| `test_mode2_success` | 成功认证流程 | ✅ 通过 |
| `test_mode2_tag_mismatch` | Tag篡改检测 | ✅ 通过 |
| `test_mode2_digest_mismatch` | Digest不匹配检测 | ✅ 通过 |

**覆盖功能点：**
- 特征密钥生成（调用3.1模块）
- DevPseudo伪名生成
- AuthReq构造与验证
- Tag计算与校验
- Digest一致性检查
- MAT签发与管理
- 会话密钥Ks派生

#### 3. 集成测试 (`tests/test_integration.py`)

**测试场景：**

| 测试名称 | 验证内容 | 状态 |
|---------|---------|------|
| `test_mode1_then_mode2_success` | "先快后稳"策略 | ✅ 通过 |
| `test_mode1_fail_fallback_mode2` | 模式一失败回退 | ✅ 通过 |
| `test_dual_mode_independent` | 双模式独立运行 | ✅ 通过 |

**覆盖功能点：**
- 模式一 → 模式二升级流程
- 模式一失败后回退到模式二
- 两种模式独立无干扰运行
- TokenFast与MAT的协同
- 不同TTL的令牌管理

## 📊 测试统计

### 当前测试结果

```
运行日期: 2025-11-20
测试套件: 3个
测试场景: 11个
通过率: 100% ✅✅✅
失败: 0
```

### 测试执行时间

```
模式一测试: ~0.2秒
模式二测试: ~0.05秒
集成测试: ~0.08秒
总计: ~0.35秒
```

## 🔍 测试方法

### 单元测试方法

所有测试都遵循标准的"Arrange-Act-Assert"模式：

```python
def test_example():
    # Arrange: 设置测试环境
    config = AuthConfig(MODE1_ENABLED=True)
    auth = Mode1FastAuth(config)
    
    # Act: 执行被测试的操作
    result = auth.authenticate(dev_id, features, snr)
    
    # Assert: 验证结果
    assert result.success == True
    assert result.mode == "mode1"
```

### 集成测试方法

集成测试验证多个组件的协同工作：

```python
def test_integration():
    # 阶段一：模式一快速认证
    mode1_result = mode1_auth.authenticate(...)
    
    # 阶段二：升级到模式二
    mode2_result = mode2_auth.authenticate(...)
    
    # 验证：两种模式协同工作
    assert mode1_result.success
    assert mode2_result.success
    assert mode2_result.session_key is not None
```

## 🛠️ 测试依赖

### 必需依赖

- Python 3.7+
- numpy
- secrets (标准库)
- logging (标准库)

### 外部模块依赖

- `feature-encryption` - 3.1特征加密模块（用于模式二）
  - 通过`src/_fe_bridge.py`桥接导入

### 测试环境

测试使用了以下模拟组件：

1. **RFF匹配器模拟** (`RFFMatcher`)
   - 模拟物理层RFF判定
   - 字节级相似度计算
   - SNR因子调整

2. **确定性量化器** (用于模式二)
   - 使用`deterministic_for_testing=True`
   - 确保测试结果可复现

## 📝 测试配置

### 默认配置

```python
AuthConfig(
    MODE1_ENABLED=True,
    MODE2_ENABLED=True,
    RFF_THRESHOLD=0.8,
    TOKEN_FAST_TTL=60,
    MAT_TTL=300,
    TAG_LENGTH=16,
    PSEUDO_LENGTH=12
)
```

### 测试用配置

在不同测试中会使用不同的配置参数来验证边界条件：

- **高阈值测试**: `RFF_THRESHOLD=0.95`
- **低延迟配置**: `TOKEN_FAST_TTL=30`
- **高安全配置**: `TAG_LENGTH=32, MAT_TTL=180`

## 🐛 故障排查

### 常见问题

#### 1. 模块导入错误

**问题:** `ModuleNotFoundError: No module named 'src'`

**解决:** 确保从`feature-authentication`目录运行测试
```bash
cd feature-authentication
python run_all_tests.py
```

#### 2. feature-encryption模块未找到

**问题:** `ModuleNotFoundError: No module named 'src.feature_encryption'`

**解决:** 确保`feature-encryption`文件夹与`feature-authentication`在同一父目录
```
Feature-Algorithm/
├── feature-authentication/
└── feature-encryption/
```

#### 3. bchlib警告

**问题:** `Warning: bchlib import failed`

**解决:** 这是已知问题，fuzzy_extractor会自动回退到reedsolo，不影响测试
```bash
# 可选：安装bchlib（但可能在Windows上有编码问题）
pip install bchlib
```

## 📈 持续集成

### CI/CD集成示例

```yaml
# .github/workflows/test.yml
name: Test Feature Authentication

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.8
      - name: Install dependencies
        run: |
          pip install -r feature-encryption/requirements.txt
      - name: Run tests
        run: |
          cd feature-authentication
          python run_all_tests.py
```

## 🎯 测试最佳实践

1. **始终使用全局测试脚本**
   - 运行`run_all_tests.py`确保完整验证
   - 避免只运行部分测试

2. **测试前清理环境**
   - 删除旧的`__pycache__`目录
   - 确保使用最新代码

3. **查看详细日志**
   - 测试失败时检查完整日志输出
   - 日志包含详细的步骤信息

4. **验证所有模式**
   - 确保模式一和模式二都通过
   - 验证双模式集成功能

## 📚 参考文档

- [3.2-feature-authentication.md](../3.2-feature-authentication.md) - 功能需求文档
- [implementation_review.md](docs/implementation_review.md) - 实现审查报告
- [mode1_implementation_report.md](docs/mode1_implementation_report.md) - 模式一实现报告
- [README.md](README.md) - 模块总体说明

## ✅ 验收标准

模块被认为完全通过测试，当：

- ✅ 所有3个测试套件通过
- ✅ 所有11个测试场景通过
- ✅ 无异常或错误
- ✅ 通过率达到100%

**当前状态:** ✅✅✅ **全部通过！**

