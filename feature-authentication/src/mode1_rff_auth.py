"""
模式一：基于射频指纹（RFF）的快速轻量认证

实现快速认证流程，直接消费物理层RFF判定结果。
"""

import logging
import time
from typing import Optional, Dict, List
from dataclasses import dataclass

from .config import AuthConfig
from .common import RFFJudgment, TokenFast, AuthResult, DeviceIdentity
from .token_manager import TokenFastManager
from .utils import generate_random_key, format_bytes_preview


logger = logging.getLogger(__name__)


@dataclass
class RFFTemplate:
    """RFF模板数据
    
    在实际部署中，这应该包含从物理层提取的射频指纹特征。
    当前实现提供一个简化的接口用于测试。
    
    Attributes:
        dev_id: 设备标识（6字节）
        template_data: 模板特征数据（模拟）
        created_at: 创建时间戳
        ver: RFF模型版本
    """
    dev_id: bytes
    template_data: bytes  # 模拟的RFF模板数据
    created_at: int
    ver: str = "1.0"
    
    def __post_init__(self):
        if len(self.dev_id) != 6:
            raise ValueError(f"dev_id must be 6 bytes, got {len(self.dev_id)}")


class RFFMatcher:
    """RFF匹配器（物理层模拟）
    
    在实际部署中，这应该是物理层提供的RFF匹配模块。
    当前实现提供一个简化的模拟器用于测试和演示。
    """
    
    def __init__(self):
        """初始化RFF匹配器"""
        # 模板存储：dev_id -> RFFTemplate
        self._templates: Dict[bytes, RFFTemplate] = {}
        
        logger.info("RFFMatcher initialized (simulation mode)")
    
    def register_template(self, dev_id: bytes, template_data: Optional[bytes] = None):
        """注册RFF模板
        
        Args:
            dev_id: 设备标识（6字节）
            template_data: 模板数据（None表示自动生成模拟数据）
        
        Raises:
            ValueError: dev_id无效
        """
        if len(dev_id) != 6:
            raise ValueError(f"dev_id must be 6 bytes, got {len(dev_id)}")
        
        if template_data is None:
            # 生成模拟模板数据（64字节随机数据）
            template_data = generate_random_key(64)
        
        template = RFFTemplate(
            dev_id=dev_id,
            template_data=template_data,
            created_at=int(time.time()),
            ver="1.0"
        )
        
        self._templates[dev_id] = template
        
        logger.info(f"RFF template registered for device {dev_id.hex()}")
        logger.debug(f"  Template data: {format_bytes_preview(template_data, 32)}")
    
    def match(
        self,
        dev_id: bytes,
        observed_features: bytes,
        snr: float = 20.0
    ) -> RFFJudgment:
        """执行RFF匹配
        
        在实际部署中，这会使用复杂的信号处理和机器学习算法。
        当前实现使用简化的模拟逻辑。
        
        Args:
            dev_id: 声明的设备标识
            observed_features: 观察到的RFF特征数据
            snr: 信噪比（dB）
        
        Returns:
            RFFJudgment: RFF判定结果
        """
        logger.info(f"RFF matching for device {dev_id.hex()}")
        logger.debug(f"  Observed features: {format_bytes_preview(observed_features, 32)}")
        logger.debug(f"  SNR: {snr} dB")
        
        # 检查设备是否已注册
        if dev_id not in self._templates:
            logger.warning(f"  Device not registered")
            return RFFJudgment(
                dev_id=dev_id,
                rff_pass=False,
                rff_score=0.0,
                snr=snr,
                ver="1.0",
                timestamp=int(time.time())
            )
        
        template = self._templates[dev_id]
        
        # 模拟匹配逻辑：计算简单的相似度
        # 实际中会使用复杂的距离度量（欧氏距离、余弦相似度等）
        score = self._simulate_matching(
            template.template_data,
            observed_features,
            snr
        )
        
        rff_pass = score >= 0.8  # 简单阈值判断
        
        logger.info(f"  RFF match result: pass={rff_pass}, score={score:.3f}")
        
        return RFFJudgment(
            dev_id=dev_id,
            rff_pass=rff_pass,
            rff_score=score,
            snr=snr,
            ver=template.ver,
            timestamp=int(time.time())
        )
    
    def _simulate_matching(
        self,
        template_data: bytes,
        observed_data: bytes,
        snr: float
    ) -> float:
        """模拟匹配算法
        
        使用简化的相似度计算模拟真实的RFF匹配。
        
        Args:
            template_data: 模板数据
            observed_data: 观察数据
            snr: 信噪比
        
        Returns:
            float: 匹配得分 [0.0, 1.0]
        """
        # 基础得分：如果数据完全相同，基础得分为1.0
        if template_data == observed_data:
            base_score = 1.0
        else:
            # 计算字节级别的相似度
            min_len = min(len(template_data), len(observed_data))
            matching_bytes = sum(
                1 for i in range(min_len)
                if template_data[i] == observed_data[i]
            )
            base_score = matching_bytes / max(len(template_data), len(observed_data))
        
        # 根据SNR调整得分（SNR越高，得分越可靠）
        # SNR < 10dB: 大幅降低得分
        # SNR 10-20dB: 中等降低
        # SNR > 20dB: 轻微影响
        if snr < 10:
            snr_factor = 0.5
        elif snr < 20:
            snr_factor = 0.8
        else:
            snr_factor = 0.95 + (min(snr, 30) - 20) * 0.005  # 最高0.95 + 0.05 = 1.0
        
        final_score = base_score * snr_factor
        
        logger.debug(f"    Matching simulation: base={base_score:.3f}, snr_factor={snr_factor:.3f}, final={final_score:.3f}")
        
        return final_score
    
    def remove_template(self, dev_id: bytes) -> bool:
        """移除RFF模板
        
        Args:
            dev_id: 设备标识
        
        Returns:
            bool: 是否成功移除
        """
        if dev_id in self._templates:
            del self._templates[dev_id]
            logger.info(f"RFF template removed for device {dev_id.hex()}")
            return True
        else:
            logger.warning(f"No RFF template found for device {dev_id.hex()}")
            return False


class Mode1FastAuth:
    """模式一：RFF快速认证
    
    实现基于射频指纹的快速轻量认证流程。
    """
    
    def __init__(
        self,
        config: AuthConfig,
        k_mgmt: Optional[bytes] = None,
        rff_matcher: Optional[RFFMatcher] = None
    ):
        """初始化
        
        Args:
            config: 认证配置
            k_mgmt: 管理密钥（32字节），None表示自动生成
            rff_matcher: RFF匹配器，None表示使用默认模拟器
        
        Raises:
            ValueError: 模式一未启用或参数无效
        """
        if not config.MODE1_ENABLED:
            raise ValueError("MODE1_ENABLED is False, cannot initialize Mode1FastAuth")
        
        self.config = config
        
        # 初始化管理密钥
        if k_mgmt is None:
            k_mgmt = generate_random_key(config.K_MGMT_LENGTH)
            logger.info(f"Generated management key: {format_bytes_preview(k_mgmt, 16)}")
        elif len(k_mgmt) != config.K_MGMT_LENGTH:
            raise ValueError(f"k_mgmt must be {config.K_MGMT_LENGTH} bytes, got {len(k_mgmt)}")
        
        # 初始化令牌管理器
        self.token_manager = TokenFastManager(config, k_mgmt)
        
        # 初始化RFF匹配器
        if rff_matcher is None:
            rff_matcher = RFFMatcher()
        
        self.rff_matcher = rff_matcher
        
        # 设备注册表：dev_id -> DeviceIdentity
        self._device_registry: Dict[bytes, DeviceIdentity] = {}
        
        logger.info("="*80)
        logger.info("Mode1FastAuth initialized")
        logger.info(f"  RFF_THRESHOLD: {config.RFF_THRESHOLD}")
        logger.info(f"  TOKEN_FAST_TTL: {config.TOKEN_FAST_TTL}s")
        logger.info("="*80)
    
    def register_device(
        self,
        dev_id: bytes,
        template_data: Optional[bytes] = None
    ):
        """注册设备
        
        Args:
            dev_id: 设备标识（6字节）
            template_data: RFF模板数据（None表示自动生成）
        
        Raises:
            ValueError: dev_id无效
        """
        if len(dev_id) != 6:
            raise ValueError(f"dev_id must be 6 bytes, got {len(dev_id)}")
        
        # 注册到设备列表
        device = DeviceIdentity(dev_id=dev_id)
        self._device_registry[dev_id] = device
        
        # 注册RFF模板
        self.rff_matcher.register_template(dev_id, template_data)
        
        logger.info(f"Device registered: {dev_id.hex()}")
    
    def authenticate(
        self,
        dev_id: bytes,
        observed_features: bytes,
        snr: float = 20.0,
        policy: str = "default"
    ) -> AuthResult:
        """执行快速认证
        
        实现文档中的三步流程：
        1. 接收RFF判定
        2. 链路层快速决策
        3. 签发快速令牌
        
        Args:
            dev_id: 声明的设备标识
            observed_features: 观察到的RFF特征
            snr: 信噪比（dB）
            policy: 令牌策略
        
        Returns:
            AuthResult: 认证结果
        """
        logger.info("="*80)
        logger.info("MODE 1 FAST AUTHENTICATION")
        logger.info(f"  Device ID: {dev_id.hex()}")
        logger.info(f"  SNR: {snr} dB")
        logger.info("="*80)
        
        # 步骤一：接收RFF判定
        logger.info("Step 1: Receiving RFF judgment from PHY layer...")
        rff_judgment = self.rff_matcher.match(dev_id, observed_features, snr)
        
        logger.info(f"  RFF result: pass={rff_judgment.rff_pass}, score={rff_judgment.rff_score:.3f}")
        
        # 步骤二：链路层快速决策
        logger.info("Step 2: Link layer fast decision...")
        
        # 2.1 检查设备是否在注册列表
        if dev_id not in self._device_registry:
            logger.error("  [FAIL] Device not in registry")
            logger.info("="*80)
            return AuthResult(
                success=False,
                mode="mode1",
                reason="device_not_registered"
            )
        
        logger.debug("  [OK] Device found in registry")
        
        # 2.2 检查RFF判定结果
        if not rff_judgment.rff_pass:
            logger.error(f"  [FAIL] RFF judgment failed (pass=False)")
            logger.info("="*80)
            return AuthResult(
                success=False,
                mode="mode1",
                reason="rff_failed"
            )
        
        logger.debug("  [OK] RFF judgment passed")
        
        # 2.3 检查RFF得分是否满足阈值
        if rff_judgment.rff_score < self.config.RFF_THRESHOLD:
            logger.warning(f"  [FAIL] RFF score {rff_judgment.rff_score:.3f} < threshold {self.config.RFF_THRESHOLD}")
            logger.info("="*80)
            return AuthResult(
                success=False,
                mode="mode1",
                reason="rff_score_below_threshold"
            )
        
        logger.info(f"  [OK] RFF score {rff_judgment.rff_score:.3f} >= threshold {self.config.RFF_THRESHOLD}")
        
        # 步骤三：签发快速令牌
        logger.info("Step 3: Issuing TokenFast...")
        token_fast = self.token_manager.issue_token_fast(dev_id, policy)
        
        logger.info("[OK][OK][OK] Authentication successful!")
        logger.info(f"  Token size: {len(token_fast.serialize())} bytes")
        logger.info(f"  Valid until: {token_fast.t_expire} (TTL={self.config.TOKEN_FAST_TTL}s)")
        logger.info("="*80)
        
        return AuthResult(
            success=True,
            mode="mode1",
            token=token_fast.serialize(),
            session_key=None,  # 模式一不生成会话密钥（可选）
            reason=None
        )
    
    def verify_token(
        self,
        token: TokenFast,
        current_time: Optional[int] = None
    ) -> bool:
        """验证快速令牌
        
        Args:
            token: 待验证的令牌
            current_time: 当前时间（Unix时间戳）
        
        Returns:
            bool: 是否验证通过
        """
        return self.token_manager.verify_token_fast(token, current_time)
    
    def revoke_device(self, dev_id: bytes) -> bool:
        """撤销设备
        
        Args:
            dev_id: 设备标识
        
        Returns:
            bool: 是否成功撤销
        """
        # 从注册表移除
        removed_from_registry = dev_id in self._device_registry
        if removed_from_registry:
            del self._device_registry[dev_id]
        
        # 移除RFF模板
        removed_template = self.rff_matcher.remove_template(dev_id)
        
        # 撤销令牌
        revoked_token = self.token_manager.revoke_token(dev_id)
        
        if removed_from_registry or removed_template or revoked_token:
            logger.info(f"Device revoked: {dev_id.hex()}")
            return True
        else:
            logger.warning(f"Device not found: {dev_id.hex()}")
            return False


# 导出
__all__ = [
    'RFFTemplate',
    'RFFMatcher',
    'Mode1FastAuth',
]

