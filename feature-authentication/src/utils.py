"""
工具函数模块

提供密码学相关的工具函数。
"""

import hashlib
import hmac
import secrets
from typing import Optional
import logging

# 尝试导入blake3
try:
    import blake3
    BLAKE3_AVAILABLE = True
except ImportError:
    BLAKE3_AVAILABLE = False
    logging.warning("blake3 not available, falling back to SHA256")


logger = logging.getLogger(__name__)


# ==================== 哈希函数 ====================

def blake3_hash(data: bytes, length: Optional[int] = None) -> bytes:
    """BLAKE3哈希

    Args:
        data: 输入数据
        length: 输出长度（字节），None表示使用默认32字节

    Returns:
        bytes: 哈希值

    Raises:
        ImportError: 如果blake3不可用
    """
    if not BLAKE3_AVAILABLE:
        raise ImportError("blake3 not available, install with: pip install blake3")

    if length is None:
        length = 32

    hasher = blake3.blake3(data)
    return hasher.digest(length=length)


def sha256_hash(data: bytes) -> bytes:
    """SHA256哈希

    Args:
        data: 输入数据

    Returns:
        bytes: 哈希值（32字节）
    """
    return hashlib.sha256(data).digest()


def hash_data(data: bytes, algorithm: str = 'blake3', length: Optional[int] = None) -> bytes:
    """通用哈希函数

    Args:
        data: 输入数据
        algorithm: 哈希算法（'blake3' 或 'sha256'）
        length: 输出长度（仅blake3支持）

    Returns:
        bytes: 哈希值

    Raises:
        ValueError: 算法不支持
    """
    logger.debug(f"Hashing {len(data)} bytes with {algorithm}")

    if algorithm == 'blake3':
        if not BLAKE3_AVAILABLE:
            logger.warning("blake3 not available, falling back to sha256")
            return sha256_hash(data)
        return blake3_hash(data, length)
    elif algorithm == 'sha256':
        if length is not None and length != 32:
            logger.warning(f"SHA256 always outputs 32 bytes, ignoring length={length}")
        return sha256_hash(data)
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


# ==================== MAC函数 ====================

def blake3_mac(key: bytes, data: bytes, length: Optional[int] = None) -> bytes:
    """BLAKE3-MAC (Keyed Hash)

    Args:
        key: 密钥（至少32字节）
        data: 输入数据
        length: 输出长度（字节），None表示使用默认32字节

    Returns:
        bytes: MAC值

    Raises:
        ImportError: 如果blake3不可用
        ValueError: 密钥长度不足
    """
    if not BLAKE3_AVAILABLE:
        raise ImportError("blake3 not available, install with: pip install blake3")

    if len(key) < 32:
        raise ValueError(f"Key length must be at least 32 bytes, got {len(key)}")

    if length is None:
        length = 32

    hasher = blake3.blake3(data, key=key)
    return hasher.digest(length=length)


def hmac_sha256_mac(key: bytes, data: bytes) -> bytes:
    """HMAC-SHA256

    Args:
        key: 密钥
        data: 输入数据

    Returns:
        bytes: MAC值（32字节）
    """
    return hmac.new(key, data, hashlib.sha256).digest()


def compute_mac(key: bytes, data: bytes, algorithm: str = 'blake3', length: Optional[int] = None) -> bytes:
    """通用MAC函数

    Args:
        key: 密钥
        data: 输入数据
        algorithm: MAC算法（'blake3' 或 'hmac-sha256'）
        length: 输出长度（仅blake3支持）

    Returns:
        bytes: MAC值

    Raises:
        ValueError: 算法不支持
    """
    logger.debug(f"Computing MAC for {len(data)} bytes with {algorithm}")

    if algorithm == 'blake3':
        if not BLAKE3_AVAILABLE:
            logger.warning("blake3 not available, falling back to hmac-sha256")
            return hmac_sha256_mac(key, data)
        return blake3_mac(key, data, length)
    elif algorithm == 'hmac-sha256':
        if length is not None and length != 32:
            logger.warning(f"HMAC-SHA256 always outputs 32 bytes, ignoring length={length}")
        return hmac_sha256_mac(key, data)
    else:
        raise ValueError(f"Unsupported MAC algorithm: {algorithm}")


# ==================== 截断函数 ====================

def truncate(data: bytes, length: int) -> bytes:
    """截断到指定长度

    Args:
        data: 输入数据
        length: 目标长度（字节）

    Returns:
        bytes: 截断后的数据

    Raises:
        ValueError: 数据长度不足
    """
    if len(data) < length:
        raise ValueError(f"Data length {len(data)} < required length {length}")

    return data[:length]


# ==================== 比较函数 ====================

def constant_time_compare(a: bytes, b: bytes) -> bool:
    """常时比较（防时序攻击）

    Args:
        a: 第一个字节串
        b: 第二个字节串

    Returns:
        bool: 是否相等

    Note:
        使用Python内置的secrets.compare_digest，提供常时比较。
    """
    if len(a) != len(b):
        # 长度不同时也要做常时比较，避免泄露长度信息
        # 但Python的secrets.compare_digest会立即返回False
        # 我们仍然使用它，因为这是推荐做法
        return False

    return secrets.compare_digest(a, b)


# ==================== 随机数生成 ====================

def generate_nonce(length: int = 16) -> bytes:
    """生成随机nonce

    Args:
        length: nonce长度（字节）

    Returns:
        bytes: 随机nonce
    """
    return secrets.token_bytes(length)


def generate_random_key(length: int = 32) -> bytes:
    """生成随机密钥

    Args:
        length: 密钥长度（字节）

    Returns:
        bytes: 随机密钥
    """
    return secrets.token_bytes(length)


# ==================== 编码/解码 ====================

def bytes_to_hex(data: bytes, sep: str = '') -> str:
    """字节串转十六进制字符串

    Args:
        data: 字节串
        sep: 分隔符（如':'）

    Returns:
        str: 十六进制字符串
    """
    if sep:
        return sep.join(f'{b:02x}' for b in data)
    else:
        return data.hex()


def hex_to_bytes(hex_str: str) -> bytes:
    """十六进制字符串转字节串

    Args:
        hex_str: 十六进制字符串（可包含分隔符）

    Returns:
        bytes: 字节串

    Raises:
        ValueError: 格式错误
    """
    # 移除常见分隔符
    hex_str = hex_str.replace(':', '').replace('-', '').replace(' ', '')
    return bytes.fromhex(hex_str)


# ==================== 调试辅助 ====================

def format_bytes_preview(data: bytes, max_len: int = 20) -> str:
    """格式化字节串预览（用于日志）

    Args:
        data: 字节串
        max_len: 最大显示长度（十六进制字符）

    Returns:
        str: 格式化的预览字符串
    """
    hex_str = data.hex()
    if len(hex_str) > max_len:
        return f"{hex_str[:max_len]}... ({len(data)} bytes)"
    else:
        return f"{hex_str} ({len(data)} bytes)"


def log_key_material(key_name: str, key_data: bytes, logger_obj: logging.Logger):
    """安全地记录密钥材料（仅记录前几个字节）

    Args:
        key_name: 密钥名称
        key_data: 密钥数据
        logger_obj: 日志对象
    """
    preview = format_bytes_preview(key_data, max_len=16)
    logger_obj.debug(f"{key_name}: {preview}")


# 导出
__all__ = [
    'blake3_hash',
    'sha256_hash',
    'hash_data',
    'blake3_mac',
    'hmac_sha256_mac',
    'compute_mac',
    'truncate',
    'constant_time_compare',
    'generate_nonce',
    'generate_random_key',
    'bytes_to_hex',
    'hex_to_bytes',
    'format_bytes_preview',
    'log_key_material',
    'BLAKE3_AVAILABLE',
]
