"""
3.1模块导入桥接

由于feature-authentication和feature-encryption都使用src作为包名，
会导致命名冲突。此模块通过在独立上下文中导入3.1模块来解决此问题。
"""

import sys
from pathlib import Path

# 保存当前sys.modules状态
_saved_modules = {}
_fe_modules_to_save = ['src', 'src.feature_encryption', 'src.config', 'src.key_derivation',
                       'src.fuzzy_extractor', 'src.quantizer', 'src.feature_processor']

def _save_and_clear_src_modules():
    """保存并清除src相关模块"""
    global _saved_modules
    for modname in list(sys.modules.keys()):
        if modname == 'src' or modname.startswith('src.'):
            _saved_modules[modname] = sys.modules.pop(modname)

def _restore_src_modules():
    """恢复保存的src模块"""
    global _saved_modules
    for modname in list(sys.modules.keys()):
        if modname == 'src' or modname.startswith('src.'):
            sys.modules.pop(modname, None)
    for modname, mod in _saved_modules.items():
        sys.modules[modname] = mod
    _saved_modules = {}

# 执行导入
_save_and_clear_src_modules()

try:
    # 添加3.1模块路径
    _fe_root = Path(__file__).parent.parent.parent / 'feature-encryption'
    if str(_fe_root) not in sys.path:
        sys.path.insert(0, str(_fe_root))

    # 导入3.1模块
    from src.feature_encryption import FeatureEncryption, Context as FEContext, KeyOutput
    from src.config import FeatureEncryptionConfig as FEConfig

    # 保存3.1模块的引用
    _fe_modules = {}
    for modname in _fe_modules_to_save:
        if modname in sys.modules:
            _fe_modules[modname] = sys.modules[modname]

finally:
    # 恢复feature-authentication的src模块
    _restore_src_modules()

    # 重新注册3.1模块（使用别名以避免冲突）
    for modname, mod in _fe_modules.items():
        aliased_name = modname.replace('src', '_fe3_1', 1)
        sys.modules[aliased_name] = mod

# 导出所需的类
__all__ = ['FeatureEncryption', 'FEContext', 'KeyOutput', 'FEConfig']
