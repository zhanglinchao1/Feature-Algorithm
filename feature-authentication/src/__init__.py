"""
Feature-based Authentication Module

基于特征的认证模块，提供两种认证模式：
1. 模式一：基于RFF的快速轻量认证
2. 模式二：基于特征加密的强认证
"""

__version__ = "0.1.0"
__author__ = "Feature-Algorithm Team"

from .config import AuthConfig
from .common import (
    DeviceIdentity,
    AuthContext,
    AuthResult,
    RFFJudgment,
    TokenFast,
    AuthReq,
    MAT,
)
from .token_manager import TokenFastManager, MATManager
from .mode2_strong_auth import DeviceSide, VerifierSide

__all__ = [
    'AuthConfig',
    'DeviceIdentity',
    'AuthContext',
    'AuthResult',
    'RFFJudgment',
    'TokenFast',
    'AuthReq',
    'MAT',
    'TokenFastManager',
    'MATManager',
    'DeviceSide',
    'VerifierSide',
]
