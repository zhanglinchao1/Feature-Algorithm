"""
模式二：基于特征加密的强认证

实现设备端和验证端的强认证流程。
"""

import sys
import secrets
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict
import struct
import numpy as np

# 导入3.1模块（特征加密）- 使用桥接模块避免命名冲突
from ._fe_bridge import FeatureEncryption, FEContext, KeyOutput, FEConfig

from .config import AuthConfig
from .common import AuthContext, AuthReq, AuthResult, MAT, DeviceIdentity
from .token_manager import MATManager
from .utils import (
    hash_data,
    compute_mac,
    truncate,
    constant_time_compare,
    generate_nonce,
    format_bytes_preview,
    log_key_material,
)


logger = logging.getLogger(__name__)


class DeviceSide:
    """设备端强认证

    负责生成AuthReq并发送给验证端。
    """

    def __init__(self, config: AuthConfig, fe_config: Optional[FEConfig] = None):
        """初始化

        Args:
            config: 认证配置
            fe_config: 特征加密配置（None表示使用默认）
        """
        self.config = config

        if fe_config is None:
            fe_config = FEConfig()

        self.fe = FeatureEncryption(fe_config)
        self.fe_config = fe_config

        logger.info("="*80)
        logger.info("DeviceSide initialized")
        logger.info(f"  Auth config: Mode2={self.config.MODE2_ENABLED}")
        logger.info(f"  FE config: M_FRAMES={self.fe_config.M_FRAMES}, TARGET_BITS={self.fe_config.TARGET_BITS}")
        logger.info("="*80)

    def generate_pseudo(self, K: bytes, epoch: int) -> bytes:
        """生成设备伪名

        DevPseudo = Trunc₉₆(BLAKE3("Pseudo"‖K‖epoch))

        Args:
            K: 特征密钥（32字节）
            epoch: 时间窗编号

        Returns:
            bytes: 伪名（12字节）
        """
        logger.info(f"Generating DevPseudo for epoch={epoch}")
        log_key_material("K", K, logger)

        # 构造消息
        msg = b"Pseudo" + K + struct.pack('<I', epoch)

        # BLAKE3哈希并截断到12字节
        hash_val = hash_data(msg, algorithm=self.config.HASH_ALGORITHM, length=32)
        pseudo = truncate(hash_val, self.config.PSEUDO_LENGTH)

        logger.debug(f"  DevPseudo: {format_bytes_preview(pseudo, 24)}")

        return pseudo

    def compute_tag(self, K: bytes, context: AuthContext) -> bytes:
        """计算认证标签

        Tag = Trunc₁₂₈(BLAKE3-MAC(K, SrcMAC‖DstMAC‖epoch‖nonce‖seq‖algID‖csi_id))

        Args:
            K: 特征密钥
            context: 认证上下文

        Returns:
            bytes: 认证标签（16字节）
        """
        logger.info("Computing authentication Tag")
        log_key_material("K", K, logger)

        # 构造消息（按照规范的字段顺序）
        alg_id_bytes = context.alg_id.encode('utf-8')
        msg = (
            context.src_mac +                      # 6 bytes
            context.dst_mac +                      # 6 bytes
            struct.pack('<I', context.epoch) +     # 4 bytes
            context.nonce +                        # 16 bytes
            struct.pack('<I', context.seq) +       # 4 bytes
            alg_id_bytes +                         # variable
            struct.pack('<I', context.csi_id)      # 4 bytes
        )

        logger.debug(f"  Tag message: {len(msg)} bytes")
        logger.debug(f"    SrcMAC: {context.src_mac.hex()}")
        logger.debug(f"    DstMAC: {context.dst_mac.hex()}")
        logger.debug(f"    Epoch: {context.epoch}")
        logger.debug(f"    Nonce: {format_bytes_preview(context.nonce, 32)}")
        logger.debug(f"    Seq: {context.seq}")
        logger.debug(f"    AlgID: {context.alg_id}")
        logger.debug(f"    CSI_ID: {context.csi_id}")

        # 计算MAC并截断
        mac = compute_mac(
            key=K,
            data=msg,
            algorithm=self.config.MAC_ALGORITHM,
            length=32
        )

        tag = truncate(mac, self.config.TAG_LENGTH)

        logger.info(f"  Tag computed: {format_bytes_preview(tag, 32)}")

        return tag

    def create_auth_request(
        self,
        dev_id: bytes,
        Z_frames: np.ndarray,
        context: AuthContext
    ) -> Tuple[AuthReq, bytes]:
        """创建认证请求

        完整的设备端认证流程：
        1. 调用3.1模块生成密钥
        2. 生成伪名
        3. 计算Tag
        4. 构造AuthReq

        Args:
            dev_id: 设备标识（6字节MAC地址）
            Z_frames: 特征帧（M x D的numpy数组）
            context: 认证上下文

        Returns:
            (AuthReq, Ks, K): 认证请求、会话密钥和特征密钥

        Raises:
            ValueError: 参数无效或密钥生成失败
        """
        logger.info("="*80)
        logger.info("DEVICE SIDE: Creating AuthReq")
        logger.info(f"  Device ID: {dev_id.hex()}")
        logger.info(f"  Z_frames shape: {Z_frames.shape}")
        logger.info(f"  Epoch: {context.epoch}, Seq: {context.seq}")
        logger.info("="*80)

        if len(dev_id) != 6:
            raise ValueError(f"dev_id must be 6 bytes, got {len(dev_id)}")

        # Step 1: 调用3.1生成密钥
        logger.info("Step 1: Calling FeatureKeyGen (3.1 module)...")

        # 转换为3.1的Context
        fe_context = FEContext(
            srcMAC=context.src_mac,
            dstMAC=context.dst_mac,
            dom=b'FeatureAuth',  # 域标识
            ver=context.ver,
            epoch=context.epoch,
            Ci=0,  # 会话计数器
            nonce=context.nonce
        )

        try:
            key_output, metadata = self.fe.register(
                device_id=dev_id.hex(),
                Z_frames=Z_frames,
                context=fe_context,
                mask_bytes=b'device_mask'
            )
        except Exception as e:
            logger.error(f"✗ FeatureKeyGen failed: {e}")
            raise ValueError(f"FeatureKeyGen failed: {e}")

        logger.info(f"✓ FeatureKeyGen success")
        log_key_material("K", key_output.K, logger)
        log_key_material("Ks", key_output.Ks, logger)
        log_key_material("S", key_output.S, logger)
        logger.debug(f"  digest: {format_bytes_preview(key_output.digest, 32)}")
        logger.debug(f"  Bit count: {metadata['bit_count']}")

        # Step 2: 生成伪名
        logger.info("Step 2: Generating DevPseudo...")
        dev_pseudo = self.generate_pseudo(key_output.K, context.epoch)
        logger.info(f"✓ DevPseudo: {format_bytes_preview(dev_pseudo, 24)}")

        # Step 3: 计算Tag
        logger.info("Step 3: Computing authentication Tag...")
        tag = self.compute_tag(key_output.K, context)
        logger.info(f"✓ Tag: {format_bytes_preview(tag, 32)}")

        # Step 4: 构造AuthReq
        logger.info("Step 4: Constructing AuthReq...")
        auth_req = AuthReq(
            dev_pseudo=dev_pseudo,
            csi_id=context.csi_id,
            epoch=context.epoch,
            nonce=context.nonce,
            seq=context.seq,
            alg_id=context.alg_id,
            ver=context.ver,
            digest=key_output.digest,
            tag=tag
        )

        logger.info("✓✓✓ AuthReq created successfully")
        logger.info(f"  Total size: {len(auth_req.serialize())} bytes")
        logger.info("="*80)

        return auth_req, key_output.Ks, key_output.K


class VerifierSide:
    """验证端强认证

    负责验证AuthReq并签发MAT。
    """

    def __init__(
        self,
        config: AuthConfig,
        issuer_id: bytes,
        issuer_key: bytes,
        fe_config: Optional[FEConfig] = None
    ):
        """初始化

        Args:
            config: 认证配置
            issuer_id: 签发者标识（6字节MAC地址）
            issuer_key: 签发者密钥（32字节）
            fe_config: 特征加密配置（None表示使用默认）

        Raises:
            ValueError: 参数无效
        """
        self.config = config

        if len(issuer_id) != 6:
            raise ValueError(f"issuer_id must be 6 bytes, got {len(issuer_id)}")

        if len(issuer_key) != 32:
            raise ValueError(f"issuer_key must be 32 bytes, got {len(issuer_key)}")

        self.issuer_id = issuer_id
        self.issuer_key = issuer_key

        if fe_config is None:
            fe_config = FEConfig()

        self.fe = FeatureEncryption(fe_config)
        self.fe_config = fe_config

        # MAT管理器
        self.mat_manager = MATManager(config, issuer_id, issuer_key)

        # 设备注册表：dev_id -> (K, epoch)
        # 用于DevPseudo反向查找
        self.device_registry: Dict[bytes, Tuple[bytes, int]] = {}

        logger.info("="*80)
        logger.info("VerifierSide initialized")
        logger.info(f"  Issuer ID: {issuer_id.hex()}")
        logger.info(f"  Auth config: Mode2={self.config.MODE2_ENABLED}")
        logger.info(f"  FE config: M_FRAMES={self.fe_config.M_FRAMES}")
        logger.info("="*80)

    def generate_pseudo(self, K: bytes, epoch: int) -> bytes:
        """生成设备伪名（与DeviceSide相同的算法）

        Args:
            K: 特征密钥
            epoch: 时间窗编号

        Returns:
            bytes: 伪名（12字节）
        """
        msg = b"Pseudo" + K + struct.pack('<I', epoch)
        hash_val = hash_data(msg, algorithm=self.config.HASH_ALGORITHM, length=32)
        return truncate(hash_val, self.config.PSEUDO_LENGTH)

    def locate_device(self, dev_pseudo: bytes, epoch: int) -> Optional[bytes]:
        """根据伪名定位设备

        遍历注册表，为每个设备计算期望的DevPseudo并匹配。

        Args:
            dev_pseudo: 设备伪名
            epoch: 时间窗编号

        Returns:
            bytes: 设备ID，如果未找到返回None
        """
        logger.info(f"Locating device for pseudo={format_bytes_preview(dev_pseudo, 24)}, epoch={epoch}")

        for dev_id, (K, registered_epoch) in self.device_registry.items():
            expected_pseudo = self.generate_pseudo(K, epoch)

            logger.debug(f"  Checking dev_id={dev_id.hex()}")
            logger.debug(f"    Expected pseudo: {format_bytes_preview(expected_pseudo, 24)}")

            if constant_time_compare(expected_pseudo, dev_pseudo):
                logger.info(f"✓ Device found: {dev_id.hex()}")
                return dev_id

        logger.warning(f"✗ Device not found in registry")
        return None

    def register_device(self, dev_id: bytes, K: bytes, epoch: int):
        """注册设备（用于测试/演示）

        实际部署中，设备信息应在注册阶段获取并持久化存储。

        Args:
            dev_id: 设备标识
            K: 特征密钥
            epoch: 时间窗编号
        """
        self.device_registry[dev_id] = (K, epoch)
        logger.info(f"Device registered: {dev_id.hex()}, epoch={epoch}")

    def compute_tag(self, K: bytes, context: AuthContext) -> bytes:
        """计算认证标签（与DeviceSide相同）

        Args:
            K: 特征密钥
            context: 认证上下文

        Returns:
            bytes: 认证标签
        """
        alg_id_bytes = context.alg_id.encode('utf-8')
        msg = (
            context.src_mac +
            context.dst_mac +
            struct.pack('<I', context.epoch) +
            context.nonce +
            struct.pack('<I', context.seq) +
            alg_id_bytes +
            struct.pack('<I', context.csi_id)
        )

        mac = compute_mac(
            key=K,
            data=msg,
            algorithm=self.config.MAC_ALGORITHM,
            length=32
        )

        return truncate(mac, self.config.TAG_LENGTH)

    def verify_auth_request(
        self,
        auth_req: AuthReq,
        Z_frames: np.ndarray
    ) -> AuthResult:
        """验证认证请求

        完整的验证端认证流程：
        1. 设备定位
        2. 重构密钥
        3. 配置一致性检查
        4. Tag校验
        5. 签发MAT

        Args:
            auth_req: 认证请求
            Z_frames: 特征帧（M x D的numpy数组）

        Returns:
            AuthResult: 认证结果
        """
        logger.info("="*80)
        logger.info("VERIFIER SIDE: Verifying AuthReq")
        logger.info(f"  DevPseudo: {format_bytes_preview(auth_req.dev_pseudo, 24)}")
        logger.info(f"  Epoch: {auth_req.epoch}, Seq: {auth_req.seq}")
        logger.info(f"  Z_frames shape: {Z_frames.shape}")
        logger.info("="*80)

        # Step 1: 设备定位
        logger.info("Step 1: Locating device...")
        dev_id = self.locate_device(auth_req.dev_pseudo, auth_req.epoch)

        if dev_id is None:
            logger.error("✗ Device not registered")
            logger.info("="*80)
            return AuthResult(
                success=False,
                mode="mode2",
                reason="device_not_registered"
            )

        logger.info(f"✓ Device located: {dev_id.hex()}")

        # Step 2: 重构密钥
        logger.info("Step 2: Reconstructing keys with FeatureKeyGen...")

        # 转换为3.1的Context - 使用实际的dev_id而不是伪名
        fe_context = FEContext(
            srcMAC=dev_id,  # 使用实际的设备ID，与注册时一致
            dstMAC=self.issuer_id,
            dom=b'FeatureAuth',
            ver=auth_req.ver,
            epoch=auth_req.epoch,
            Ci=0,
            nonce=auth_req.nonce
        )

        try:
            key_output, success = self.fe.authenticate(
                device_id=dev_id.hex(),
                Z_frames=Z_frames,
                context=fe_context,
                mask_bytes=b'device_mask'
            )
        except Exception as e:
            logger.error(f"✗ FeatureKeyGen failed: {e}")
            logger.info("="*80)
            return AuthResult(
                success=False,
                mode="mode2",
                reason=f"feature_keygen_failed: {e}"
            )

        if not success:
            logger.error("✗ FeatureKeyGen failed (BCH decode failed)")
            logger.info("="*80)
            return AuthResult(
                success=False,
                mode="mode2",
                reason="feature_mismatch"
            )

        logger.info(f"✓ Keys reconstructed successfully")
        log_key_material("K'", key_output.K, logger)
        log_key_material("Ks'", key_output.Ks, logger)
        log_key_material("S'", key_output.S, logger)
        logger.debug(f"  digest': {format_bytes_preview(key_output.digest, 32)}")

        # Step 3: 配置一致性检查
        logger.info("Step 3: Checking digest consistency...")
        logger.debug(f"  Expected digest: {format_bytes_preview(key_output.digest, 32)}")
        logger.debug(f"  Received digest: {format_bytes_preview(auth_req.digest, 32)}")

        if not constant_time_compare(key_output.digest, auth_req.digest):
            logger.error("✗ Digest mismatch (configuration inconsistency)")
            logger.info("="*80)
            return AuthResult(
                success=False,
                mode="mode2",
                reason="digest_mismatch"
            )

        logger.info("✓ Digest check passed")

        # Step 4: Tag校验
        logger.info("Step 4: Verifying authentication Tag...")

        # 构造AuthContext
        context = AuthContext(
            src_mac=auth_req.dev_pseudo[:6],  # 临时
            dst_mac=self.issuer_id,
            epoch=auth_req.epoch,
            nonce=auth_req.nonce,
            seq=auth_req.seq,
            alg_id=auth_req.alg_id,
            ver=auth_req.ver,
            csi_id=auth_req.csi_id
        )

        tag_prime = self.compute_tag(key_output.K, context)

        logger.debug(f"  Expected Tag: {format_bytes_preview(tag_prime, 32)}")
        logger.debug(f"  Received Tag: {format_bytes_preview(auth_req.tag, 32)}")

        if not constant_time_compare(tag_prime, auth_req.tag):
            logger.error("✗ Tag verification failed")
            logger.info("="*80)
            return AuthResult(
                success=False,
                mode="mode2",
                reason="tag_mismatch"
            )

        logger.info("✓ Tag verification passed")

        # Step 5: 签发MAT
        logger.info("Step 5: Issuing MAT...")
        mat = self.mat_manager.issue_mat(
            dev_pseudo=auth_req.dev_pseudo,
            epoch=auth_req.epoch
        )

        logger.info("✓✓✓ Authentication successful")
        logger.info("="*80)

        return AuthResult(
            success=True,
            mode="mode2",
            token=mat.serialize(),
            session_key=key_output.Ks,
            reason=None
        )


# 导出
__all__ = [
    'DeviceSide',
    'VerifierSide',
]
