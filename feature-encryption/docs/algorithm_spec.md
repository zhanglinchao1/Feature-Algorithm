# 基于特征的加密算法 - 完整规范

## 算法概述

将物理层特征转换为稳定密钥的完整流程。

**输入**：
- 特征向量 X（CSI或RFF）
- 上下文信息（srcMAC, dstMAC, dom, ver, epoch, Ci, nonce）

**输出**：
- 稳定特征串 S (256 bits)
- 随机扰动值 L (256 bits)
- 特征密钥 K (256 bits)
- 会话密钥 Ks (256 bits)
- 一致性摘要 digest (64 bits)

## 步骤1：特征预处理与规整

### 1.1 CSI特征提取（路径一）

#### 输入
- 原始信道估计：H[k], k=0..N-1（N=64个子载波）
- 噪声功率估计：σ²

#### 处理流程

**Step 1.1.1: 计算SNR并选择子载波**
```python
# 计算每个子载波的SNR
for k in range(N_SUBCARRIER_TOTAL):
    SNR[k] = |H[k]|² / σ²

# 选择SNR最高的32个子载波
indices = argsort(SNR, descending=True)[:N_SUBCARRIER_SELECTED]
indices_sorted = sort(indices)  # 保持频域顺序

# 提取选中的子载波
H_selected = [H[k] for k in indices_sorted]
```

**Step 1.1.2: 计算幅度特征**
```python
# 幅度差分（31维）
A = []
for d in range(1, N_SUBCARRIER_SELECTED):
    amp_diff = |H_selected[d]| - |H_selected[d-1]|
    A.append(amp_diff)
```

**Step 1.1.3: 计算相位特征**
```python
# 相位差分（31维）
P = []
for d in range(1, N_SUBCARRIER_SELECTED):
    phase_diff = angle(H_selected[d]) - angle(H_selected[d-1])
    # 相位展开到[-π, π]
    phase_diff = ((phase_diff + π) % (2π)) - π
    P.append(phase_diff)
```

**Step 1.1.4: 拼接特征向量**
```python
# 拼接得到62维实向量
Z_csi = concatenate([A, P])  # shape: (62,)

# 如果需要扩展到64维，补充统计特征
mean_amp = mean(|H_selected|)
std_amp = std(|H_selected|)
Z_csi = concatenate([Z_csi, [mean_amp, std_amp]])  # shape: (64,)
```

### 1.2 RFF特征提取（路径二）

#### 输入
- 载波频偏（CFO）：Δf
- 采样频偏（SCO）：Δs
- I/Q失衡：α, φ
- 功率放大器非线性参数：β₁, β₂, β₃

#### 处理流程

**Step 1.2.1: 提取原始RFF参数**
```python
raw_features = [
    CFO,           # 载波频偏
    SCO,           # 采样频偏
    IQ_amp_imb,    # I/Q幅度失衡
    IQ_phase_imb,  # I/Q相位失衡
    PA_beta1,      # PA非线性系数1
    PA_beta2,      # PA非线性系数2
    PA_beta3,      # PA非线性系数3
    DC_offset_I,   # 直流偏移I
    DC_offset_Q,   # 直流偏移Q
    # ... 其他射频参数，总共16个
]
```

**Step 1.2.2: Z-score标准化**
```python
# 对每个参数进行标准化
μ = mean(raw_features_history)  # 历史均值
σ = std(raw_features_history)   # 历史标准差

Z_rff = []
for i, x in enumerate(raw_features):
    z = (x - μ[i]) / (σ[i] + ε)  # ε=1e-8防止除零
    Z_rff.append(z)

Z_rff = array(Z_rff)  # shape: (16,)
```

### 1.3 特征选择掩码生成

```python
# 生成选择掩码（用于digest计算）
if mode == 'CSI':
    mask = {
        'mode': 'CSI',
        'indices': indices_sorted,  # 选中的子载波索引
        'N_selected': N_SUBCARRIER_SELECTED
    }
elif mode == 'RFF':
    mask = {
        'mode': 'RFF',
        'feature_ids': list(range(16))
    }

# 序列化掩码
mask_bytes = serialize(mask)
```

## 步骤2：稳健量化与多帧投票

### 2.1 多帧采集

```python
# 采集M=6帧特征
Z_frames = []
for m in range(M_FRAMES):
    Z_m = extract_feature()  # 调用步骤1
    Z_frames.append(Z_m)

Z_frames = array(Z_frames)  # shape: (M, D)
```

### 2.2 计算量化门限

#### 方法1：基于分位数（默认）
```python
for d in range(D):
    # 对每个维度，计算M帧的统计量
    values_d = Z_frames[:, d]  # shape: (M,)

    # 计算门限
    θ_L[d] = percentile(values_d, 25)  # 下四分位数
    θ_H[d] = percentile(values_d, 75)  # 上四分位数
```

#### 方法2：基于固定倍数
```python
for d in range(D):
    values_d = Z_frames[:, d]
    μ_d = mean(values_d)
    σ_d = std(values_d)

    θ_L[d] = μ_d - 0.5 * σ_d
    θ_H[d] = μ_d + 0.5 * σ_d
```

### 2.3 量化为三值

```python
# 对每一帧的每个维度进行量化
Q_frames = []
for m in range(M_FRAMES):
    Q_m = []
    for d in range(D):
        x = Z_frames[m, d]
        if x > θ_H[d]:
            q = 1
        elif x < θ_L[d]:
            q = 0
        else:
            q = -1  # 擦除标记
        Q_m.append(q)
    Q_frames.append(Q_m)

Q_frames = array(Q_frames)  # shape: (M, D)
```

### 2.4 多数投票

```python
r_bits = []
selected_dims = []

for d in range(D):
    votes_d = Q_frames[:, d]  # shape: (M,)

    # 统计0和1的票数（忽略-1）
    count_0 = sum(votes_d == 0)
    count_1 = sum(votes_d == 1)

    # 投票决策
    if count_1 >= VOTE_THRESHOLD:
        r_bits.append(1)
        selected_dims.append(d)
    elif count_0 >= VOTE_THRESHOLD:
        r_bits.append(0)
        selected_dims.append(d)
    else:
        # 票数不足，丢弃该维度
        pass

# 如果比特数不足TARGET_BITS，按SNR补充
while len(r_bits) < TARGET_BITS:
    # 从未选中的维度中，选择SNR最高的
    unused_dims = set(range(D)) - set(selected_dims)
    if not unused_dims:
        # 所有维度都用完了，填充随机比特（由TRNG生成）
        r_bits.extend(random_bits(TARGET_BITS - len(r_bits)))
        break

    # 选择SNR最高的未使用维度
    next_dim = max(unused_dims, key=lambda d: compute_snr(Z_frames[:, d]))
    # 简单多数投票
    votes = Q_frames[:, next_dim]
    bit = 1 if sum(votes == 1) >= sum(votes == 0) else 0
    r_bits.append(bit)
    selected_dims.append(next_dim)

# 截断到TARGET_BITS
r = r_bits[:TARGET_BITS]  # 256 bits
```

## 步骤3：纠错与模糊提取

### 3.1 注册阶段：生成辅助数据

```python
# 将256 bits分成2块，每块128 bits
J = BCH_BLOCKS  # 2
k = BCH_K       # 131
n = BCH_N       # 255

# 分块
r_blocks = split(r, J)  # 两块：[0:128], [128:256]

# 对每块进行BCH编码
P_blocks = []
for j in range(J):
    # 取出该块的消息位（最多k位）
    msg = r_blocks[j][:k]  # 128 bits，补3位0到131
    msg_padded = pad(msg, k)  # 补齐到131 bits

    # BCH编码
    codeword = bch_encode(msg_padded, n, k, t=BCH_T)  # 255 bits

    # 计算辅助串
    helper = xor(codeword, pad(r_blocks[j], n))  # 对齐到255 bits
    P_blocks.append(helper)

# 拼接辅助数据
P = concatenate(P_blocks)  # shape: (J * n,) bits

# 存储P（仅在验证端安全存储）
store_helper_data(device_id, P)
```

### 3.2 认证阶段：恢复稳定特征

```python
# 读取辅助数据
P = load_helper_data(device_id)
P_blocks = split(P, J)

# 重新测量并量化，得到含噪比特串r'
r_prime = measure_and_quantize()  # 步骤1-2
r_prime_blocks = split(r_prime, J)

# 对每块进行纠错
S_blocks = []
for j in range(J):
    # 恢复码字
    noisy_codeword = xor(P_blocks[j], pad(r_prime_blocks[j], n))

    # BCH解码
    corrected_msg, success = bch_decode(noisy_codeword, n, k, t=BCH_T)

    if not success:
        raise Exception(f"BCH decoding failed for block {j}")

    S_blocks.append(corrected_msg[:128])  # 取前128位

# 拼接得到稳定特征串
S = concatenate(S_blocks)  # 256 bits
```

## 步骤4：上下文绑定与密钥派生

### 4.1 计算随机扰动值

```python
# 拼接epoch和nonce
data = epoch || nonce  # epoch: 4 bytes, nonce: 16 bytes

# BLAKE3哈希
hash_output = BLAKE3(data)  # 32 bytes = 256 bits

# 截断到256 bits
L = hash_output[:32]  # 32 bytes = 256 bits
```

### 4.2 派生特征密钥

```python
# 准备输入密钥材料
IKM = S || L  # 拼接：32 bytes + 32 bytes = 64 bytes

# HKDF-Extract
salt = dom  # 域标识作为盐值
PRK = HKDF_Extract(salt, IKM)  # 输出32 bytes

# HKDF-Expand
info = ver || srcMAC || dstMAC || epoch
# ver: 1 byte, srcMAC: 6 bytes, dstMAC: 6 bytes, epoch: 4 bytes
# info总共: 17 bytes

K = HKDF_Expand(PRK, info, L=32)  # 输出32 bytes = 256 bits
```

### 4.3 派生会话密钥

```python
# 使用特征密钥作为PRK
PRK = K

# 构造info
info = "SessionKey" || epoch || Ci
# "SessionKey": 10 bytes, epoch: 4 bytes, Ci: 4 bytes
# info总共: 18 bytes

Ks = HKDF_Expand(PRK, info, L=32)  # 输出32 bytes = 256 bits
```

### 4.4 生成一致性摘要

```python
# 拼接配置信息
config_data = (
    mask_bytes ||              # 特征选择掩码
    θ_L.tobytes() ||          # 下门限数组
    θ_H.tobytes() ||          # 上门限数组
    algID.to_bytes(1) ||      # 算法ID
    ver.to_bytes(1)           # 版本号
)

# BLAKE3哈希
digest_full = BLAKE3(config_data)

# 截断到64 bits
digest = digest_full[:8]  # 8 bytes = 64 bits
```

## 完整算法伪代码

```python
def feature_key_gen(X, context, config):
    """
    完整的特征密钥生成算法

    Args:
        X: 特征向量或原始测量数据
        context: {srcMAC, dstMAC, dom, ver, epoch, Ci, nonce}
        config: 算法配置参数

    Returns:
        {S, L, K, Ks, digest}
    """
    # Step 1: 特征预处理
    if X.mode == 'CSI':
        Z, mask = process_csi_feature(X, config)
    else:  # RFF
        Z, mask = process_rff_feature(X, config)

    # Step 2: 稳健量化与投票
    Z_frames = collect_multi_frames(config.M_FRAMES)
    θ_L, θ_H = compute_thresholds(Z_frames, config)
    Q_frames = quantize_frames(Z_frames, θ_L, θ_H)
    r = majority_vote(Q_frames, config)

    # Step 3: 纠错与模糊提取
    if is_registration_phase():
        P = generate_helper_data(r, config)
        store_helper_data(context.device_id, P)
        S = r  # 注册时直接使用r
    else:  # 认证阶段
        P = load_helper_data(context.device_id)
        S = error_correction(r, P, config)

    # Step 4: 密钥派生
    L = BLAKE3(context.epoch || context.nonce)[:32]

    IKM = S || L
    PRK = HKDF_Extract(context.dom, IKM)
    info_K = context.ver || context.srcMAC || context.dstMAC || context.epoch
    K = HKDF_Expand(PRK, info_K, 32)

    info_Ks = b"SessionKey" || context.epoch || context.Ci
    Ks = HKDF_Expand(K, info_Ks, 32)

    # 生成一致性摘要
    config_data = mask || θ_L || θ_H || algID || ver
    digest = BLAKE3(config_data)[:8]

    return {
        'S': S,
        'L': L,
        'K': K,
        'Ks': Ks,
        'digest': digest
    }
```

## 数据类型定义

```python
# 类型定义
BitString = List[int]  # 0或1的列表
ByteArray = bytes
MAC = bytes  # 6 bytes
Epoch = int  # 4 bytes (uint32)
Nonce = bytes  # 16 bytes

# 输入输出结构
class FeatureInput:
    mode: str  # 'CSI' or 'RFF'
    data: np.ndarray  # 原始特征数据
    snr: np.ndarray  # 信噪比（可选）

class Context:
    srcMAC: MAC
    dstMAC: MAC
    dom: bytes
    ver: int
    epoch: Epoch
    Ci: int
    nonce: Nonce

class KeyOutput:
    S: BitString  # 256 bits
    L: ByteArray  # 32 bytes
    K: ByteArray  # 32 bytes
    Ks: ByteArray  # 32 bytes
    digest: ByteArray  # 8 bytes
```

## 边界情况处理

### 情况1：投票比特数不足
```python
if len(r_bits) < TARGET_BITS:
    # 策略1：补充随机比特（降低安全性）
    r_bits.extend(secure_random(TARGET_BITS - len(r_bits)))

    # 策略2：降低投票阈值重新投票
    # （需要在digest中记录降级）

    # 策略3：拒绝本次认证，要求重新测量
    raise InsufficientFeatureBitsError()
```

### 情况2：BCH解码失败
```python
if not bch_decode_success:
    # 策略1：要求重新测量
    raise BCHDecodingError("Too many bit errors")

    # 策略2：降级到无纠错模式（不推荐）
    S = r_prime  # 直接使用含噪比特串
```

### 情况3：digest不匹配
```python
if digest_device != digest_verifier:
    # 配置不一致，拒绝认证
    raise ConfigMismatchError("Feature configuration mismatch")
```

## 性能分析

### 计算复杂度
- 特征提取：O(N) - 线性复杂度
- 量化投票：O(M × D) - M帧×D维
- BCH编码/解码：O(n²) - n=255
- HKDF：O(1) - 固定哈希次数

### 存储需求
- 辅助数据P：J × n bits = 2 × 255 = 510 bits ≈ 64 bytes
- 门限数组：2 × D × 4 bytes ≈ 512 bytes（D=64，float32）
- 掩码：~100 bytes

### 时延估算（参考值）
- 特征采集：~10ms（M=6帧）
- 量化投票：<1ms
- BCH编解码：<5ms
- HKDF：<1ms
- **总计**：<20ms

## 安全性分析

### 熵估计
- 原始特征熵：~0.7 bit/dimension
- 量化后熵：~0.5 bit/bit（考虑投票）
- BCH纠错后熵：≥128 bits（有效密钥长度）
- HKDF输出熵：256 bits（理论最大值）

### 攻击抵抗
- **重放攻击**：L绑定epoch和nonce，每次不同
- **克隆攻击**：S绑定物理特征，难以复制
- **建模攻击**：辅助数据P不泄露r，难以反推
- **侧信道攻击**：使用常时算法，防止时序泄露
