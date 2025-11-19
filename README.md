# Feature-Algorithm - 基于特征加密的MAC身份认证系统

## 项目概述

本项目实现了一个分布式自组网环境下的MAC层身份认证系统，采用物理层特征（信道特征/射频指纹）作为身份根，实现抗重放、抗伪造、防跟踪的安全接入认证。

### 核心模块

- **3.3.1 基于特征的加密算法**：将物理层特征转换为密钥
- **3.3.2 基于特征的认证方法**：两种认证模式（RFF快速认证/特征密钥强认证）
- **3.3.3 周期变化同步机制**：时间窗同步、密钥轮换、分布式状态管理（本项目实现）

## 项目结构

```
Feature-Algorithm/
├── docs/                           # 文档目录
│   └── 3.3-feature-synchronization.md  # 3.3.3模块开发文档
├── prd.docx                        # 产品需求文档
├── feature_sync/                   # 主代码目录
│   ├── core/                       # 核心数据结构
│   │   ├── __init__.py
│   │   ├── beacon.py              # 同步信标
│   │   ├── feature_config.py      # 特征参数配置
│   │   ├── epoch_state.py         # 周期状态
│   │   └── key_material.py        # 密钥材料
│   ├── sync/                       # 同步机制
│   │   ├── __init__.py
│   │   ├── cluster_head.py        # 簇首节点
│   │   ├── validator_node.py      # 验证节点
│   │   ├── device_node.py         # 设备节点
│   │   ├── key_rotation.py        # 密钥轮换
│   │   └── mat_manager.py         # MAT令牌管理
│   ├── auth/                       # 认证相关
│   │   ├── __init__.py
│   │   └── mat_token.py           # MAT令牌定义
│   ├── crypto/                     # 密码学原语
│   │   ├── __init__.py
│   │   ├── hkdf.py               # 密钥派生
│   │   └── signatures.py          # 签名/验签
│   ├── network/                    # 网络通信
│   │   ├── __init__.py
│   │   ├── gossip.py             # Gossip协议
│   │   ├── election.py            # 簇首选举
│   │   └── transport.py           # 传输层
│   ├── utils/                      # 工具类
│   │   ├── __init__.py
│   │   ├── serialization.py       # 序列化
│   │   └── logging_config.py      # 日志配置
│   └── tests/                      # 测试代码
│       ├── __init__.py
│       ├── test_beacon.py
│       ├── test_key_rotation.py
│       ├── test_election.py
│       └── test_integration.py
├── examples/                       # 示例代码
│   └── two_validators_one_device.py
├── requirements.txt                # 依赖包
└── README.md                       # 本文件
```

## 快速开始

### 环境要求

- Python 3.8+
- NumPy 1.20+
- cryptography 3.4+

### 安装

```bash
pip install -r requirements.txt
```

### 运行测试

```bash
# 运行所有单元测试
python -m pytest feature_sync/tests/ -v

# 运行集成测试（2验证节点+1设备节点）
python -m pytest feature_sync/tests/test_integration.py -v
```

### 示例：启动2验证节点+1设备节点

```python
from feature_sync.sync import SynchronizationService

# 初始化验证节点
validator1 = SynchronizationService(
    node_type='validator',
    node_id=b'\x00\x00\x00\x00\x00\x01',
    peer_validators=[b'\x00\x00\x00\x00\x00\x02']
)

validator2 = SynchronizationService(
    node_type='validator',
    node_id=b'\x00\x00\x00\x00\x00\x02',
    peer_validators=[b'\x00\x00\x00\x00\x00\x01']
)

# 启动同步服务
validator1.start()
validator2.start()

# 查询当前epoch
print(f"Current epoch: {validator1.get_current_epoch()}")
```

## 核心功能

### 1. 时间窗同步

- 基于信标（Beacon）的epoch同步
- 支持±1 epoch容忍窗口
- 簇首失效自动重选举

### 2. 密钥轮换

- 每个epoch自动轮换特征密钥和会话密钥
- 伪名周期性变化，防止长期跟踪
- 新旧密钥短时并存，平滑切换

### 3. MAT令牌管理

- 准入令牌（MAT）签发与验证
- 令牌吊销列表同步
- 基于epoch的自动过期

### 4. 分布式状态同步

- Gossip协议同步吊销信息
- 验证节点间状态一致性
- 容忍网络分区和时钟偏差

## 测试场景

本项目针对以下测试拓扑进行验证：

```
      验证节点1 (Validator 1)
            |
            |  信标广播/Gossip
            |
      验证节点2 (Validator 2)
            |
            |  认证请求/应答
            |
       设备节点 (Device)
```

- **验证节点数量**：2个（支持簇首选举和互备）
- **设备节点数量**：≥1个
- **网络类型**：分布式自组网，无中心化控制

## 性能指标

- **信标广播周期**：5秒
- **Epoch周期**：30秒
- **信标超时**：15秒
- **选举超时**：5秒
- **Gossip间隔**：3秒

## 开发路线图

- [x] 开发文档编写
- [x] 项目结构设计
- [ ] 核心数据结构实现
- [ ] 时间窗同步机制
- [ ] 密钥轮换机制
- [ ] MAT令牌管理
- [ ] 簇首选举和失步处理
- [ ] Gossip协议
- [ ] 单元测试
- [ ] 集成测试
- [ ] 性能优化

## 接口依赖

### 对3.3.1的依赖

需要3.3.1模块提供特征密钥派生接口：

```python
def derive_keys(feature_vector, src_mac, dst_mac, domain, version,
                epoch, nonce, hash_chain_counter) -> (S, L, K, Ks, digest)
```

当前使用Mock实现，后续替换为真实接口。

### 对3.3.2的支持

为3.3.2认证模块提供以下接口：

```python
# 获取当前epoch
get_current_epoch() -> int

# 检查epoch有效性
is_epoch_valid(epoch: int) -> bool

# 获取/生成密钥材料
get_key_material(device_mac, epoch) -> KeyMaterial

# 签发/验证MAT令牌
issue_mat_token(pseudonym, epoch, session_key) -> MATToken
verify_mat_token(mat) -> bool
```

## 贡献指南

1. Fork本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

## 许可证

待定

## 联系方式

项目负责人：[待补充]

---

**当前开发状态**：开发中
**最后更新**：2025-11-19
