"""
Feature-based Authentication Module

基于特征的认证模块，提供两种认证模式：
1. 模式一：基于RFF的快速轻量认证
2. 模式二：基于特征加密的强认证
"""

# 添加3.1模块路径（必须在任何导入之前）
import sys
from pathlib import Path
_fe_root = Path(__file__).parent.parent.parent / 'feature-encryption'
if str(_fe_root) not in sys.path:
    sys.path.insert(0, str(_fe_root))

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
from .mode1_rff_auth import Mode1FastAuth, RFFMatcher, RFFTemplate
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
    'Mode1FastAuth',
    'RFFMatcher',
    'RFFTemplate',
    'DeviceSide',
    'VerifierSide',
]
