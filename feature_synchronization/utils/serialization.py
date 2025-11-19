"""
序列化工具模块
"""
import struct
from typing import Any, Dict, List


class TLVEncoder:
    """TLV (Type-Length-Value) 编码器"""

    @staticmethod
    def encode_uint8(value: int) -> bytes:
        """编码uint8"""
        return struct.pack('!B', value)

    @staticmethod
    def encode_uint16(value: int) -> bytes:
        """编码uint16"""
        return struct.pack('!H', value)

    @staticmethod
    def encode_uint32(value: int) -> bytes:
        """编码uint32"""
        return struct.pack('!I', value)

    @staticmethod
    def encode_uint64(value: int) -> bytes:
        """编码uint64"""
        return struct.pack('!Q', value)

    @staticmethod
    def encode_bytes(value: bytes) -> bytes:
        """编码字节串（带长度前缀）"""
        length = len(value)
        return struct.pack('!H', length) + value

    @staticmethod
    def encode_bytes_fixed(value: bytes, size: int) -> bytes:
        """编码固定长度字节串"""
        if len(value) != size:
            raise ValueError(f"Expected {size} bytes, got {len(value)}")
        return value

    @staticmethod
    def encode_float(value: float) -> bytes:
        """编码float"""
        return struct.pack('!f', value)

    @staticmethod
    def encode_double(value: float) -> bytes:
        """编码double"""
        return struct.pack('!d', value)

    @staticmethod
    def encode_tlv(type_id: int, value: bytes) -> bytes:
        """
        编码TLV结构

        Args:
            type_id: 类型ID (1字节)
            value: 值（字节串）

        Returns:
            TLV编码的字节串
        """
        length = len(value)
        return struct.pack('!BH', type_id, length) + value


class TLVDecoder:
    """TLV解码器"""

    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0

    def decode_uint8(self) -> int:
        """解码uint8"""
        value = struct.unpack_from('!B', self.data, self.offset)[0]
        self.offset += 1
        return value

    def decode_uint16(self) -> int:
        """解码uint16"""
        value = struct.unpack_from('!H', self.data, self.offset)[0]
        self.offset += 2
        return value

    def decode_uint32(self) -> int:
        """解码uint32"""
        value = struct.unpack_from('!I', self.data, self.offset)[0]
        self.offset += 4
        return value

    def decode_uint64(self) -> int:
        """解码uint64"""
        value = struct.unpack_from('!Q', self.data, self.offset)[0]
        self.offset += 8
        return value

    def decode_bytes(self) -> bytes:
        """解码字节串（带长度前缀）"""
        length = self.decode_uint16()
        value = self.data[self.offset:self.offset + length]
        self.offset += length
        return value

    def decode_bytes_fixed(self, size: int) -> bytes:
        """解码固定长度字节串"""
        value = self.data[self.offset:self.offset + size]
        if len(value) != size:
            raise ValueError(f"Expected {size} bytes, got {len(value)}")
        self.offset += size
        return value

    def decode_float(self) -> float:
        """解码float"""
        value = struct.unpack_from('!f', self.data, self.offset)[0]
        self.offset += 4
        return value

    def decode_double(self) -> float:
        """解码double"""
        value = struct.unpack_from('!d', self.data, self.offset)[0]
        self.offset += 8
        return value

    def decode_tlv(self) -> tuple[int, bytes]:
        """
        解码TLV结构

        Returns:
            (type_id, value)元组
        """
        type_id = self.decode_uint8()
        length = self.decode_uint16()
        value = self.data[self.offset:self.offset + length]
        self.offset += length
        return type_id, value

    def has_remaining(self) -> bool:
        """检查是否还有剩余数据"""
        return self.offset < len(self.data)

    def remaining_bytes(self) -> int:
        """返回剩余字节数"""
        return len(self.data) - self.offset
