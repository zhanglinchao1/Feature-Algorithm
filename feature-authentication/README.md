# 3.2 基于特征的认证方法（两种模式）

## 模块说明

本模块实现两种并行的认证模式，用于链路层身份认证。

## 功能概述

### 模式一：基于射频指纹（RFF）的快速认证
- 毫秒级快速放行
- 适用于时延敏感场景

### 模式二：基于特征密钥的强认证
- 单报文完成密码学验证
- 抗重放、抗克隆、抗跟踪

## 目录结构

```
feature-authentication/
├── README.md           # 本文件
├── requirements.md     # 详细需求文档（从3.2.md复制）
├── src/               # 源代码
│   ├── __init__.py
│   ├── mode1_rff_auth.py      # 模式一：RFF快速认证
│   ├── mode2_strong_auth.py   # 模式二：强认证
│   ├── device_side.py         # 设备端逻辑
│   ├── verifier_side.py       # 验证端逻辑
│   └── token_manager.py       # 令牌管理
├── tests/             # 测试代码
│   ├── __init__.py
│   ├── test_mode1.py
│   ├── test_mode2.py
│   └── test_integration.py
└── docs/              # 开发文档
    ├── protocol_spec.md        # 协议规范
    ├── message_format.md       # 报文格式定义
    └── development_plan.md     # 开发计划
```

## 开发状态

- [ ] 需求分析与协议规范编写
- [ ] 报文格式定义
- [ ] 模式一实现
- [ ] 模式二实现
- [ ] 单元测试
- [ ] 集成测试
- [ ] 代码审查

## 依赖模块

- feature-encryption: 提供密钥派生功能

## 参考文档

- [3.2.md](../3.2.md) - 原始需求文档
- [README.md](../README.md) - 项目总体说明
