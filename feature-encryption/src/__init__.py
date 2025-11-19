"""
Feature-based Encryption Algorithm

基于特征的加密算法模块，用于将物理层特征转换为稳定的密钥。
"""

__version__ = "0.1.0"
__author__ = "Feature-Algorithm Team"

from .config import FeatureEncryptionConfig
from .feature_encryption import FeatureEncryption

__all__ = [
    "FeatureEncryptionConfig",
    "FeatureEncryption",
]
