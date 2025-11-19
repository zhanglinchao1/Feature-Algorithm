"""
集成测试：2验证节点 + 1设备节点
"""
import pytest
import time
from feature_sync.sync import SynchronizationService


class TestIntegrationTwoValidatorsOneDevice:
    """集成测试：2个验证节点 + 1个设备节点"""

    def test_basic_setup(self):
        """测试基本的节点初始化"""
        # 节点ID
        validator1_id = b'\x00\x00\x00\x00\x00\x01'
        validator2_id = b'\x00\x00\x00\x00\x00\x02'
        device_id = b'\x00\x00\x00\x00\x00\x03'

        # 创建验证节点
        validator1 = SynchronizationService(
            node_type='validator',
            node_id=validator1_id,
            peer_validators=[validator2_id]
        )

        validator2 = SynchronizationService(
            node_type='validator',
            node_id=validator2_id,
            peer_validators=[validator1_id]
        )

        # 创建设备节点
        device = SynchronizationService(
            node_type='device',
            node_id=device_id
        )

        # 验证初始化
        assert validator1.node_id == validator1_id
        assert validator2.node_id == validator2_id
        assert device.node_id == device_id

    def test_cluster_head_beacon_generation(self):
        """测试簇首信标生成"""
        cluster_head = SynchronizationService(
            node_type='cluster_head',
            node_id=b'\x00\x00\x00\x00\x00\x01'
        )

        # 启动簇首
        cluster_head.start()

        # 等待一小段时间让信标生成
        time.sleep(0.5)

        # 验证epoch
        epoch = cluster_head.get_current_epoch()
        assert epoch >= 0

        # 获取特征配置
        config = cluster_head.get_feature_config()
        assert config is not None
        assert config.version >= 1

        # 停止
        cluster_head.stop()

    def test_key_material_generation_and_retrieval(self):
        """测试密钥材料生成和获取"""
        validator = SynchronizationService(
            node_type='validator',
            node_id=b'\x00\x00\x00\x00\x00\x01',
            peer_validators=[]
        )

        device_mac = b'\x00\x00\x00\x00\x00\x03'
        epoch = 1

        # 生成密钥材料
        key_material = validator.generate_or_get_key_material(
            device_mac=device_mac,
            epoch=epoch
        )

        assert key_material is not None
        assert key_material.epoch == epoch
        assert len(key_material.pseudonym) == 12

        # 再次获取应该返回相同的
        key_material2 = validator.get_key_material(device_mac, epoch)
        assert key_material2 is not None
        assert key_material2.pseudonym == key_material.pseudonym

    def test_mat_token_issuance_and_verification(self):
        """测试MAT令牌签发和验证"""
        validator1_id = b'\x00\x00\x00\x00\x00\x01'
        validator2_id = b'\x00\x00\x00\x00\x00\x02'

        validator = SynchronizationService(
            node_type='validator',
            node_id=validator1_id,
            peer_validators=[validator2_id]
        )

        # 生成设备伪名
        device_pseudonym = b'\xaa\xbb\xcc\xdd\xee\xff\x11\x22\x33\x44\x55\x66'
        epoch = 1
        session_key = b'\x00' * 32

        # 签发MAT
        mat = validator.issue_mat_token(device_pseudonym, epoch, session_key)

        assert mat is not None
        assert mat.device_pseudonym == device_pseudonym
        assert mat.epoch == epoch

        # 验证MAT
        is_valid = validator.verify_mat_token(mat)
        assert is_valid is True

    def test_mat_token_revocation(self):
        """测试MAT令牌吊销"""
        validator = SynchronizationService(
            node_type='validator',
            node_id=b'\x00\x00\x00\x00\x00\x01',
            peer_validators=[]
        )

        # 签发MAT
        device_pseudonym = b'\xaa\xbb\xcc\xdd\xee\xff\x11\x22\x33\x44\x55\x66'
        mat = validator.issue_mat_token(device_pseudonym, 1, b'\x00' * 32)

        # 验证应该通过
        assert validator.verify_mat_token(mat) is True

        # 吊销
        validator.revoke_mat_token(mat.mat_id)

        # 验证应该失败
        assert validator.verify_mat_token(mat) is False

    def test_epoch_validation(self):
        """测试epoch验证"""
        validator = SynchronizationService(
            node_type='validator',
            node_id=b'\x00\x00\x00\x00\x00\x01',
            peer_validators=[]
        )

        # 模拟同步到epoch 5
        validator.validator.epoch_state.update_epoch(5, 1000000, 30000)

        # 应该接受epoch 4, 5, 6
        assert validator.is_epoch_valid(4) is True
        assert validator.is_epoch_valid(5) is True
        assert validator.is_epoch_valid(6) is True

        # 应该拒绝epoch 2, 8
        assert validator.is_epoch_valid(2) is False
        assert validator.is_epoch_valid(8) is False


@pytest.fixture(scope="module")
def setup_logging():
    """设置日志"""
    from feature_sync.utils.logging_config import setup_logging
    import logging
    setup_logging(level=logging.DEBUG)


def test_full_integration_scenario(setup_logging):
    """完整集成测试场景"""
    # 节点ID
    validator1_id = b'\x00\x00\x00\x00\x00\x01'
    validator2_id = b'\x00\x00\x00\x00\x00\x02'
    device_id = b'\x00\x00\x00\x00\x00\x03'

    # 创建验证节点（validator2的ID更大，会成为簇首）
    validator1 = SynchronizationService(
        node_type='validator',
        node_id=validator1_id,
        peer_validators=[validator2_id],
        delta_t=5000,  # 5秒epoch用于测试
        beacon_interval=1000  # 1秒信标间隔
    )

    validator2 = SynchronizationService(
        node_type='validator',
        node_id=validator2_id,
        peer_validators=[validator1_id],
        delta_t=5000,
        beacon_interval=1000
    )

    # 创建设备节点
    device = SynchronizationService(
        node_type='device',
        node_id=device_id
    )

    try:
        # 启动验证节点
        validator1.start()
        validator2.start()

        # 等待选举完成
        time.sleep(2)

        # 验证选举结果（validator2应该成为簇首）
        if validator1.is_cluster_head:
            cluster_head = validator1
            follower = validator2
        else:
            cluster_head = validator2
            follower = validator1

        print(f"Cluster head: {cluster_head.node_id.hex()}")
        print(f"Follower: {follower.node_id.hex()}")

        # 等待几次信标广播
        time.sleep(3)

        # 验证epoch同步
        epoch_ch = cluster_head.get_current_epoch()
        epoch_follower = follower.get_current_epoch()
        print(f"Cluster head epoch: {epoch_ch}")
        print(f"Follower epoch: {epoch_follower}")

        # epoch应该相同或差1（取决于同步时机）
        assert abs(epoch_ch - epoch_follower) <= 1

        # 测试密钥生成和MAT签发
        key_material = cluster_head.generate_or_get_key_material(
            device_mac=device_id,
            epoch=epoch_ch
        )

        mat = cluster_head.issue_mat_token(
            device_pseudonym=key_material.pseudonym,
            epoch=epoch_ch,
            session_key=key_material.session_key
        )

        # 验证MAT
        assert cluster_head.verify_mat_token(mat) is True

        print("Integration test passed!")

    finally:
        # 清理
        validator1.stop()
        validator2.stop()
