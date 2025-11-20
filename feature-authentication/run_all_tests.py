"""
Feature Authentication Module - 全局测试脚本

测试认证模块的两种模式及其集成功能。
"""

import sys
import logging
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def run_test_suite(test_module_name, test_description):
    """运行单个测试套件
    
    Args:
        test_module_name: 测试模块名称（如 'tests.test_mode1'）
        test_description: 测试描述
    
    Returns:
        tuple: (passed, failed, total)
    """
    logger.info("\n" + "="*80)
    logger.info(f"Running: {test_description}")
    logger.info("="*80)
    
    try:
        # 动态导入测试模块
        test_module = __import__(test_module_name, fromlist=['main'])
        
        # 运行测试
        if hasattr(test_module, 'main'):
            exit_code = test_module.main()
            
            if exit_code == 0:
                logger.info(f"[通过] {test_description} - 所有测试通过")
                return (True, 0)
            else:
                logger.error(f"[失败] {test_description} - 部分测试失败")
                return (False, 1)
        else:
            logger.error(f"[失败] {test_description} - 未找到main()函数")
            return (False, 1)
            
    except Exception as e:
        logger.error(f"[失败] {test_description} - 异常: {e}")
        import traceback
        traceback.print_exc()
        return (False, 1)


def main():
    """运行所有测试"""
    logger.info("\n")
    logger.info("="*80)
    logger.info("特征认证模块 - 综合测试套件")
    logger.info("="*80)
    logger.info("")
    logger.info("测试两种认证模式：")
    logger.info("  - 模式一：RFF快速认证")
    logger.info("  - 模式二：强认证（基于特征加密）")
    logger.info("  - 集成测试：双模式协同")
    logger.info("")
    
    test_suites = [
        ("tests.test_mode1", "模式一：RFF快速认证测试"),
        ("tests.test_mode2", "模式二：强认证测试"),
        ("tests.test_integration", "集成测试：双模式协同"),
    ]
    
    total_suites = len(test_suites)
    passed_suites = 0
    failed_suites = 0
    
    results = []
    
    for module_name, description in test_suites:
        success, fail_count = run_test_suite(module_name, description)
        results.append((description, success))
        
        if success:
            passed_suites += 1
        else:
            failed_suites += 1
    
    # 打印总结
    logger.info("\n")
    logger.info("="*80)
    logger.info("综合测试总结")
    logger.info("="*80)
    logger.info("")
    
    for description, success in results:
        status = "[通过]" if success else "[失败]"
        logger.info(f"{status} {description}")
    
    logger.info("")
    logger.info(f"测试套件总数: {total_suites}")
    logger.info(f"通过: {passed_suites}")
    logger.info(f"失败: {failed_suites}")
    logger.info("")
    
    if failed_suites == 0:
        logger.info("="*80)
        logger.info("[通过][通过][通过] 所有测试套件通过 [通过][通过][通过]")
        logger.info("="*80)
        logger.info("")
        logger.info("特征认证模块功能完整：")
        logger.info("  [通过] 模式一（RFF快速认证）- 正常工作")
        logger.info("  [通过] 模式二（强认证）- 正常工作")
        logger.info("  [通过] 双模式集成 - 正常工作")
        logger.info("")
        return 0
    else:
        logger.error("="*80)
        logger.error("[失败][失败][失败] 部分测试套件失败 [失败][失败][失败]")
        logger.error("="*80)
        logger.error("")
        return 1


if __name__ == "__main__":
    exit(main())

