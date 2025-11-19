#!/usr/bin/env python3
"""
演示程序：2个验证节点的同步机制

运行方式：
    python examples/demo_two_validators.py
"""
import time
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from feature_sync.sync import SynchronizationService
from feature_sync.utils.logging_config import setup_logging
import logging


def main():
    """主函数"""
    # 设置日志
    setup_logging(level=logging.INFO)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("3.3.3周期变化同步机制演示程序")
    logger.info("场景：2个验证节点 + 1个设备节点")
    logger.info("=" * 60)

    # 定义节点ID
    validator1_id = b'\x00\x00\x00\x00\x00\x01'
    validator2_id = b'\x00\x00\x00\x00\x00\x02'
    device_id = b'\x00\x00\x00\x00\x00\x03'

    logger.info(f"验证节点1 ID: {validator1_id.hex()}")
    logger.info(f"验证节点2 ID: {validator2_id.hex()}")
    logger.info(f"设备节点 ID: {device_id.hex()}")
    logger.info("")

    # 创建验证节点（使用较短的epoch和信标间隔用于演示）
    logger.info("初始化验证节点...")
    validator1 = SynchronizationService(
        node_type='validator',
        node_id=validator1_id,
        peer_validators=[validator2_id],
        delta_t=10000,  # 10秒epoch
        beacon_interval=2000  # 2秒信标间隔
    )

    validator2 = SynchronizationService(
        node_type='validator',
        node_id=validator2_id,
        peer_validators=[validator1_id],
        delta_t=10000,
        beacon_interval=2000
    )

    # 创建设备节点
    logger.info("初始化设备节点...")
    device = SynchronizationService(
        node_type='device',
        node_id=device_id
    )

    try:
        # 启动验证节点
        logger.info("\n" + "=" * 60)
        logger.info("启动验证节点并进行簇首选举...")
        logger.info("=" * 60)

        validator1.start()
        validator2.start()

        # 等待选举完成
        time.sleep(3)

        # 确定簇首和跟随者
        if validator1.is_cluster_head:
            cluster_head = validator1
            follower = validator2
        else:
            cluster_head = validator2
            follower = validator1

        logger.info(f"\n✓ 簇首选举完成: {cluster_head.node_id.hex()}")
        logger.info(f"✓ 跟随节点: {follower.node_id.hex()}")

        # 等待信标同步
        logger.info("\n" + "=" * 60)
        logger.info("等待信标广播和epoch同步...")
        logger.info("=" * 60)
        time.sleep(5)

        # 显示同步状态
        epoch_ch = cluster_head.get_current_epoch()
        epoch_follower = follower.get_current_epoch()

        logger.info(f"\n当前epoch状态:")
        logger.info(f"  簇首 epoch: {epoch_ch}")
        logger.info(f"  跟随者 epoch: {epoch_follower}")
        logger.info(f"  同步状态: {'✓ 已同步' if abs(epoch_ch - epoch_follower) <= 1 else '✗ 未同步'}")

        # 获取特征配置
        config = cluster_head.get_feature_config()
        if config:
            logger.info(f"\n特征配置信息:")
            logger.info(f"  版本: {config.version}")
            logger.info(f"  子载波数量: {config.subcarrier_count}")
            logger.info(f"  采样帧数: {config.sample_count}")
            logger.info(f"  量化参数α: {config.quantization_alpha}")

        # 测试密钥生成
        logger.info("\n" + "=" * 60)
        logger.info("测试密钥生成和伪名派生...")
        logger.info("=" * 60)

        key_material = cluster_head.generate_or_get_key_material(
            device_mac=device_id,
            epoch=epoch_ch
        )

        logger.info(f"\n密钥材料生成成功:")
        logger.info(f"  设备MAC: {device_id.hex()}")
        logger.info(f"  Epoch: {key_material.epoch}")
        logger.info(f"  伪名: {key_material.pseudonym.hex()}")
        logger.info(f"  特征密钥: {key_material.feature_key[:8].hex()}... (前8字节)")
        logger.info(f"  会话密钥: {key_material.session_key[:8].hex()}... (前8字节)")
        logger.info(f"  哈希链计数器: {key_material.hash_chain_counter}")

        # 测试MAT签发
        logger.info("\n" + "=" * 60)
        logger.info("测试MAT令牌签发和验证...")
        logger.info("=" * 60)

        mat = cluster_head.issue_mat_token(
            device_pseudonym=key_material.pseudonym,
            epoch=epoch_ch,
            session_key=key_material.session_key,
            ttl=10000
        )

        logger.info(f"\nMAT令牌签发成功:")
        logger.info(f"  令牌ID: {mat.mat_id.hex()}")
        logger.info(f"  设备伪名: {mat.device_pseudonym.hex()}")
        logger.info(f"  绑定epoch: {mat.epoch}")
        logger.info(f"  有效期: {mat.ttl}ms")
        logger.info(f"  签发者数量: {len(mat.issuer_set)}")

        # 验证MAT
        is_valid = cluster_head.verify_mat_token(mat)
        logger.info(f"\nMAT验证结果: {'✓ 通过' if is_valid else '✗ 失败'}")

        # 测试MAT吊销
        logger.info("\n" + "=" * 60)
        logger.info("测试MAT令牌吊销...")
        logger.info("=" * 60)

        logger.info(f"吊销MAT: {mat.mat_id.hex()}")
        cluster_head.revoke_mat_token(mat.mat_id)

        is_valid_after_revoke = cluster_head.verify_mat_token(mat)
        logger.info(f"吊销后验证结果: {'✓ 通过' if is_valid_after_revoke else '✗ 失败'}")

        # 测试epoch推进
        logger.info("\n" + "=" * 60)
        logger.info("等待epoch推进（10秒）...")
        logger.info("=" * 60)

        time.sleep(11)

        new_epoch_ch = cluster_head.get_current_epoch()
        new_epoch_follower = follower.get_current_epoch()

        logger.info(f"\nEpoch推进结果:")
        logger.info(f"  簇首 epoch: {epoch_ch} -> {new_epoch_ch}")
        logger.info(f"  跟随者 epoch: {epoch_follower} -> {new_epoch_follower}")
        logger.info(f"  推进状态: {'✓ 成功' if new_epoch_ch > epoch_ch else '✗ 失败'}")

        # 测试新epoch的密钥轮换
        logger.info("\n" + "=" * 60)
        logger.info("测试新epoch的密钥轮换...")
        logger.info("=" * 60)

        new_key_material = cluster_head.generate_or_get_key_material(
            device_mac=device_id,
            epoch=new_epoch_ch
        )

        logger.info(f"\n新epoch密钥材料:")
        logger.info(f"  旧伪名: {key_material.pseudonym.hex()}")
        logger.info(f"  新伪名: {new_key_material.pseudonym.hex()}")
        logger.info(f"  伪名已变化: {'✓ 是' if new_key_material.pseudonym != key_material.pseudonym else '✗ 否'}")

        # 总结
        logger.info("\n" + "=" * 60)
        logger.info("演示完成！")
        logger.info("=" * 60)
        logger.info("\n已验证功能:")
        logger.info("  ✓ 簇首选举（2选1）")
        logger.info("  ✓ 信标广播与同步")
        logger.info("  ✓ Epoch时间窗管理")
        logger.info("  ✓ 特征配置同步")
        logger.info("  ✓ 密钥材料生成")
        logger.info("  ✓ 伪名派生")
        logger.info("  ✓ MAT令牌签发/验证")
        logger.info("  ✓ MAT令牌吊销")
        logger.info("  ✓ Epoch自动推进")
        logger.info("  ✓ 密钥周期轮换")

    except KeyboardInterrupt:
        logger.info("\n\n用户中断，正在退出...")

    except Exception as e:
        logger.error(f"\n发生错误: {e}", exc_info=True)

    finally:
        # 清理
        logger.info("\n清理资源...")
        validator1.stop()
        validator2.stop()
        logger.info("程序退出\n")


if __name__ == '__main__':
    main()
