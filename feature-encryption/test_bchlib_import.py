"""
测试 bchlib 导入
"""
import sys
import traceback

print("测试1: 直接导入 bchlib")
try:
    import bchlib
    print(f"✓ bchlib 导入成功: {bchlib.__file__}")
except Exception as e:
    print(f"✗ bchlib 导入失败: {e}")
    traceback.print_exc()

print("\n测试2: 导入 fuzzy_extractor 模块")
try:
    from src.fuzzy_extractor import FuzzyExtractor
    print("✓ fuzzy_extractor 模块导入成功")
except Exception as e:
    print(f"✗ fuzzy_extractor 模块导入失败: {e}")
    traceback.print_exc()

print("\n测试3: 创建 FuzzyExtractor 实例")
try:
    from src.config import FeatureEncryptionConfig
    config = FeatureEncryptionConfig()
    extractor = FuzzyExtractor(config)
    print("✓ FuzzyExtractor 实例创建成功")
except Exception as e:
    print(f"✗ FuzzyExtractor 实例创建失败: {e}")
    traceback.print_exc()

