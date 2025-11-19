# 3.1 基于特征的加密算法

## 模块说明

本模块实现"基于特征的加密算法"，是连接物理层特征与链路层认证的核心引擎。

## 功能概述

将物理层的设备/信道特征转换为稳定的密钥：
- **输入**：特征向量（CSI或RFF）、上下文信息（MAC、epoch等）
- **输出**：稳定特征串S、特征密钥K、会话密钥Ks、一致性摘要digest

## 算法流程

1. **特征预处理与规整**：处理CSI或RFF特征，规整为统一格式
2. **稳健量化与投票**：多帧投票机制，提高稳定性
3. **纠错与模糊提取**：使用BCH码纠错，生成稳定特征串
4. **上下文绑定与密钥派生**：使用HKDF派生特征密钥和会话密钥

## 目录结构

```
feature-encryption/
├── README.md           # 本文件
├── requirements.md     # 详细需求文档（从3.1.md复制）
├── src/               # 源代码
│   ├── __init__.py
│   ├── feature_processor.py    # 特征预处理
│   ├── quantizer.py            # 量化与投票
│   ├── fuzzy_extractor.py      # 模糊提取器
│   └── key_derivation.py       # 密钥派生
├── tests/             # 测试代码
│   ├── __init__.py
│   ├── test_feature_processor.py
│   ├── test_quantizer.py
│   ├── test_fuzzy_extractor.py
│   └── test_key_derivation.py
└── docs/              # 开发文档
    ├── algorithm_spec.md       # 算法规范
    ├── parameter_config.md     # 参数配置说明
    └── development_plan.md     # 开发计划
```

## 开发状态

- [ ] 需求分析与算法规范编写
- [ ] 参数边界定义
- [ ] 代码实现
- [ ] 单元测试
- [ ] 集成测试
- [ ] 代码审查

## 参考文档

- [3.1.md](../3.1.md) - 原始需求文档
- [README.md](../README.md) - 项目总体说明
