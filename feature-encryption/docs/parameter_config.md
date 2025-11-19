# 参数配置说明

## 参数分类

### 1. 特征采集参数

| 参数名 | 类型 | 默认值 | 范围 | 说明 |
|--------|------|--------|------|------|
| `M_FRAMES` | int | 6 | [4, 10] | 采集的特征帧数 |
| `N_SUBCARRIER_TOTAL` | int | 64 | [32, 128] | OFDM子载波总数 |
| `N_SUBCARRIER_SELECTED` | int | 32 | [16, 64] | 选择的高SNR子载波数 |
| `FEATURE_DIM_CSI` | int | 64 | - | CSI特征维度（幅度32+相位32） |
| `FEATURE_DIM_RFF` | int | 16 | - | RFF特征维度（CFO+SCO+IQ等） |

### 2. 量化与投票参数

| 参数名 | 类型 | 默认值 | 范围 | 说明 |
|--------|------|--------|------|------|
| `QUANTIZE_METHOD` | str | 'percentile' | ['percentile', 'fixed'] | 门限计算方法 |
| `THETA_L_PERCENTILE` | float | 0.25 | [0.1, 0.4] | 下门限分位数 |
| `THETA_H_PERCENTILE` | float | 0.75 | [0.6, 0.9] | 上门限分位数 |
| `VOTE_THRESHOLD` | int | 4 | [M_FRAMES//2+1, M_FRAMES] | 投票通过阈值 |
| `TARGET_BITS` | int | 256 | [128, 512] | 目标比特串长度 |

### 3. BCH纠错码参数

| 参数名 | 类型 | 默认值 | 范围 | 说明 |
|--------|------|--------|------|------|
| `BCH_N` | int | 255 | - | BCH码字长度 |
| `BCH_K` | int | 131 | - | BCH消息长度 |
| `BCH_T` | int | 18 | - | BCH纠错能力（可纠正18位错误） |
| `BCH_BLOCKS` | int | 2 | - | 分块数（256/131≈2） |
| `BCH_POLY` | int | 0x187 | - | BCH生成多项式 |

### 4. 密钥派生参数

| 参数名 | 类型 | 默认值 | 范围 | 说明 |
|--------|------|--------|------|------|
| `HASH_ALGORITHM` | str | 'blake3' | ['blake3', 'sha256'] | 哈希算法 |
| `KEY_LENGTH` | int | 32 | [16, 64] | 密钥长度（字节） |
| `DIGEST_LENGTH` | int | 8 | [4, 16] | 一致性摘要长度（字节） |
| `HKDF_SALT_DOM` | bytes | b'domain' | - | HKDF盐值（域标识） |
| `SESSION_KEY_INFO` | str | 'SessionKey' | - | 会话密钥派生标识 |

### 5. 上下文参数

| 参数名 | 类型 | 默认值 | 范围 | 说明 |
|--------|------|--------|------|------|
| `MAC_LENGTH` | int | 6 | - | MAC地址长度（字节） |
| `EPOCH_LENGTH` | int | 4 | - | 时间窗编号长度（字节） |
| `NONCE_LENGTH` | int | 16 | - | 随机数长度（字节） |
| `VERSION` | int | 1 | - | 算法版本号 |
| `HASH_CHAIN_COUNTER` | int | 0 | [0, 2^32-1] | 哈希链计数器Ci |

## 参数依赖关系

### 特征维度计算
```python
# CSI模式
D_CSI = (N_SUBCARRIER_SELECTED - 1) * 2  # 幅度差分+相位差分
# 例如：32个子载波 → 31个差分 × 2 = 62维

# RFF模式
D_RFF = FEATURE_DIM_RFF  # 直接使用定义的维度
```

### BCH分块计算
```python
J_BLOCKS = ceil(TARGET_BITS / BCH_K)
# 256 bits / 131 bits ≈ 1.95 → 2块
```

### 投票阈值约束
```python
assert VOTE_THRESHOLD >= M_FRAMES // 2 + 1  # 必须超过半数
assert VOTE_THRESHOLD <= M_FRAMES           # 不能超过总帧数
```

## 参数调优指南

### 场景1：高噪声环境
```python
M_FRAMES = 8              # 增加采样帧数
VOTE_THRESHOLD = 6        # 提高投票阈值
BCH_T = 24                # 增强纠错能力
```

### 场景2：低时延要求
```python
M_FRAMES = 4              # 减少采样帧数
VOTE_THRESHOLD = 3        # 降低投票阈值（但保持>半数）
BCH_BLOCKS = 1            # 减少分块
TARGET_BITS = 128         # 缩短比特串
```

### 场景3：高安全要求
```python
TARGET_BITS = 512         # 增加密钥熵
N_SUBCARRIER_SELECTED = 64  # 使用更多特征
KEY_LENGTH = 64           # 增加密钥长度
```

## 默认配置文件

```python
# default_config.py
DEFAULT_CONFIG = {
    # 特征采集
    'M_FRAMES': 6,
    'N_SUBCARRIER_TOTAL': 64,
    'N_SUBCARRIER_SELECTED': 32,
    'FEATURE_DIM_CSI': 64,
    'FEATURE_DIM_RFF': 16,

    # 量化与投票
    'QUANTIZE_METHOD': 'percentile',
    'THETA_L_PERCENTILE': 0.25,
    'THETA_H_PERCENTILE': 0.75,
    'VOTE_THRESHOLD': 4,
    'TARGET_BITS': 256,

    # BCH纠错
    'BCH_N': 255,
    'BCH_K': 131,
    'BCH_T': 18,
    'BCH_BLOCKS': 2,
    'BCH_POLY': 0x187,

    # 密钥派生
    'HASH_ALGORITHM': 'blake3',
    'KEY_LENGTH': 32,
    'DIGEST_LENGTH': 8,
    'HKDF_SALT_DOM': b'FeatureAuth',
    'SESSION_KEY_INFO': 'SessionKey',

    # 上下文
    'MAC_LENGTH': 6,
    'EPOCH_LENGTH': 4,
    'NONCE_LENGTH': 16,
    'VERSION': 1,
    'HASH_CHAIN_COUNTER': 0,
}
```

## 参数验证规则

```python
def validate_config(config):
    """验证配置参数的合法性"""
    assert config['M_FRAMES'] >= 4, "采样帧数至少为4"
    assert config['VOTE_THRESHOLD'] > config['M_FRAMES'] // 2, "投票阈值必须超过半数"
    assert config['N_SUBCARRIER_SELECTED'] <= config['N_SUBCARRIER_TOTAL'], "选择的子载波数不能超过总数"
    assert config['TARGET_BITS'] > 0 and config['TARGET_BITS'] % 8 == 0, "目标比特数必须是8的倍数"
    assert config['BCH_K'] < config['BCH_N'], "BCH消息长度必须小于码字长度"
    assert config['KEY_LENGTH'] in [16, 24, 32, 48, 64], "密钥长度必须是标准值"
    return True
```

## 性能与安全平衡

| 参数 | 增加后的影响 | 建议调整方向 |
|------|------------|------------|
| M_FRAMES | ↑稳定性 ↓速度 | 平衡：6帧 |
| TARGET_BITS | ↑安全性 ↑计算量 | 平衡：256 bits |
| BCH_T | ↑容错性 ↓吞吐 | 根据误码率调整 |
| N_SUBCARRIER_SELECTED | ↑唯一性 ↑计算量 | 根据场景调整 |

## 环境适配建议

### 室内环境
- N_SUBCARRIER_SELECTED: 24-32（信道变化较小）
- M_FRAMES: 4-6（稳定性较高）
- BCH_T: 12-18（误码率较低）

### 室外环境
- N_SUBCARRIER_SELECTED: 32-48（信道变化大，需更多特征）
- M_FRAMES: 6-8（需要更多采样）
- BCH_T: 18-24（误码率较高）

### 移动场景
- M_FRAMES: 4（快速采集）
- VOTE_THRESHOLD: 3（允许更多变化）
- BCH_T: 24（高纠错能力）
