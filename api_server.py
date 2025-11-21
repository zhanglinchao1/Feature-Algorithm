"""
基于特征的身份认证 - Flask API服务器

提供RESTful API接口用于测试模式1（RFF快速认证）和模式2（强认证）。
可通过Postman等工具进行测试。

运行方式:
    python api_server.py

API端点:
    POST /api/device/mode1/register    - 模式1: 注册设备
    POST /api/device/mode1/authenticate - 模式1: RFF快速认证
    POST /api/device/mode2/create_request - 模式2: 设备端创建认证请求
    POST /api/verifier/mode2/register   - 模式2: 验证端注册设备
    POST /api/verifier/mode2/verify     - 模式2: 验证端验证请求
    GET  /api/status                    - 获取服务器状态
    POST /api/reset                     - 重置所有状态
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
import secrets
import numpy as np
from pathlib import Path
from typing import Dict, Any
import logging
import base64

# 添加模块路径
feature_auth_path = Path(__file__).parent / 'feature-authentication'
if str(feature_auth_path) not in sys.path:
    sys.path.insert(0, str(feature_auth_path))

from feature_synchronization.sync.synchronization_service import SynchronizationService
from src.mode1_rff_auth import Mode1FastAuth
from src.mode2_strong_auth import DeviceSide, VerifierSide
from src.config import AuthConfig
from src.common import AuthContext, AuthReq

# 配置日志
import sys
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # 强制输出到stdout
    ]
)
logger = logging.getLogger(__name__)

# 设置Flask的werkzeug日志级别
logging.getLogger('werkzeug').setLevel(logging.INFO)

# 创建Flask应用
app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 请求日志中间件
@app.before_request
def log_request():
    """记录每个请求的详细信息"""
    logger.info("=" * 80)
    logger.info(f"收到请求: {request.method} {request.path}")
    logger.info(f"  客户端地址: {request.remote_addr}")
    logger.info(f"  Content-Type: {request.content_type}")
    
    if request.method in ['POST', 'PUT', 'PATCH']:
        try:
            request_data = request.get_json()
            if request_data:
                # 隐藏敏感字段
                safe_data = {}
                for key, value in request_data.items():
                    if key in ['feature_key', 'session_key', 'issuer_key', 'rff_template']:
                        safe_data[key] = f"<{len(str(value))} chars>"
                    elif key == 'csi':
                        if isinstance(value, list):
                            safe_data[key] = f"<array {len(value)}x{len(value[0]) if value else 0}>"
                        else:
                            safe_data[key] = f"<{len(str(value))} chars>"
                    else:
                        safe_data[key] = value
                logger.info(f"  请求体: {safe_data}")
        except Exception as e:
            logger.debug(f"  无法解析请求体: {e}")
    
    logger.info("-" * 80)

@app.after_request
def log_response(response):
    """记录每个响应的详细信息"""
    logger.info("-" * 80)
    logger.info(f"响应: {request.method} {request.path}")
    logger.info(f"  状态码: {response.status_code}")
    logger.info(f"  Content-Type: {response.content_type}")
    
    if response.content_type and 'application/json' in response.content_type:
        try:
            response_data = response.get_json()
            if response_data:
                # 隐藏敏感字段
                safe_data = {}
                for key, value in response_data.items():
                    if key == 'data' and isinstance(value, dict):
                        safe_data_inner = {}
                        for k, v in value.items():
                            if k in ['feature_key', 'session_key', 'token_fast', 'mat_token']:
                                safe_data_inner[k] = f"<{len(str(v))} chars>" if v else None
                            elif k in ['auth_req']:
                                safe_data_inner[k] = f"<{len(str(v))} chars>" if v else None
                            else:
                                safe_data_inner[k] = v
                        safe_data[key] = safe_data_inner
                    else:
                        safe_data[key] = value
                logger.info(f"  响应体: {safe_data}")
        except Exception as e:
            logger.debug(f"  无法解析响应体: {e}")
    
    logger.info("=" * 80)
    return response

# 全局状态存储
class ServerState:
    """服务器状态管理"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """重置所有状态"""
        # 模式1状态
        self.mode1_auth = None
        self.mode1_devices = {}  # dev_id -> rff_template
        
        # 模式2状态
        self.sync_service = None
        self.device_side = None
        self.verifier_side = None
        self.mode2_devices = {}  # dev_id -> (feature_key, epoch)
        self.mode2_sessions = {}  # dev_id -> (session_key, auth_req)
        
        # 配置（启用两种模式）
        self.auth_config = AuthConfig()
        self.auth_config.MODE1_ENABLED = True  # 启用模式1
        self.auth_config.MODE2_ENABLED = True  # 启用模式2
        self.issuer_key = secrets.token_bytes(32)
        self.issuer_mac = bytes.fromhex('AABBCCDDEEFF')
        
        logger.info("服务器状态已重置")

state = ServerState()


# ============================================================================
# 工具函数
# ============================================================================

def parse_bytes(data: str, name: str = "data") -> bytes:
    """解析十六进制字符串或base64编码为字节"""
    if not data:
        raise ValueError(f"{name} is required")
    
    try:
        # 尝试十六进制解码
        return bytes.fromhex(data.replace(' ', '').replace('-', ''))
    except ValueError:
        try:
            # 尝试base64解码
            return base64.b64decode(data)
        except Exception:
            raise ValueError(f"Invalid {name} format (expected hex or base64)")


def parse_csi(csi_data: Any) -> np.ndarray:
    """解析CSI数据"""
    if isinstance(csi_data, str):
        # base64编码的numpy数组
        try:
            import io
            buffer = io.BytesIO(base64.b64decode(csi_data))
            return np.load(buffer)
        except Exception:
            raise ValueError("Invalid CSI format (expected base64-encoded numpy array)")
    elif isinstance(csi_data, list):
        # JSON数组
        return np.array(csi_data, dtype=np.float64)
    else:
        raise ValueError("CSI data must be base64 string or JSON array")


def format_response(success: bool, data: Dict[str, Any] = None, 
                   error: str = None, code: int = 200) -> tuple:
    """格式化响应"""
    response = {
        'success': success,
        'timestamp': __import__('time').time()
    }
    
    if success and data:
        response['data'] = data
    elif not success and error:
        response['error'] = error
    
    return jsonify(response), code


# ============================================================================
# 模式1: RFF快速认证 API
# ============================================================================

@app.route('/api/device/mode1/register', methods=['POST'])
def mode1_register_device():
    """
    模式1: 注册设备
    
    Request Body:
        {
            "dev_id": "001122334455",           # 设备MAC地址（hex）
            "rff_template": "base64..."         # RFF模板（可选，base64）
        }
    
    Response:
        {
            "success": true,
            "data": {
                "dev_id": "001122334455",
                "registered": true
            }
        }
    """
    try:
        data = request.get_json()
        
        # 解析参数
        dev_id = parse_bytes(data.get('dev_id'), 'dev_id')
        rff_template = None
        if 'rff_template' in data and data['rff_template']:
            rff_template = parse_bytes(data['rff_template'], 'rff_template')
        else:
            # 如果没有提供rff_template，生成一个确定性的模板
            # 使用设备ID作为种子，确保相同设备总是生成相同的模板
            import hashlib
            rff_template = hashlib.sha256(dev_id + b"_rff_template_seed").digest()
            logger.info(f"使用确定性模板进行注册: {dev_id.hex()}")
        
        # 初始化Mode1（如果需要）
        if state.mode1_auth is None:
            k_mgmt = secrets.token_bytes(32)
            state.mode1_auth = Mode1FastAuth(state.auth_config, k_mgmt)
            logger.info("模式1认证器已初始化")
        
        # 注册设备
        state.mode1_auth.register_device(dev_id, rff_template)
        state.mode1_devices[dev_id.hex()] = rff_template
        
        logger.info(f"模式1: 设备已注册 - {dev_id.hex()}")
        
        return format_response(True, {
            'dev_id': dev_id.hex(),
            'registered': True,
            'total_devices': len(state.mode1_devices)
        })
        
    except ValueError as e:
        logger.error(f"模式1注册失败: {e}")
        return format_response(False, error=str(e), code=400)
    except Exception as e:
        logger.error(f"模式1注册错误: {e}")
        return format_response(False, error=str(e), code=500)


@app.route('/api/device/mode1/authenticate', methods=['POST'])
def mode1_authenticate():
    """
    模式1: RFF快速认证
    
    Request Body:
        {
            "dev_id": "001122334455",           # 设备MAC地址（hex）
            "rff_score": 0.85,                  # RFF匹配分数（0-1）
            "rff_confidence": 0.90,             # RFF置信度（0-1）
            "snr": 20.0                         # 信噪比（dB，可选）
        }
    
    Response:
        {
            "success": true,
            "data": {
                "authenticated": true,
                "dev_id": "001122334455",
                "decision": "ACCEPT",
                "token_fast": "base64...",
                "token_size": 64,
                "latency_ms": 12.5
            }
        }
    """
    try:
        data = request.get_json()
        
        # 解析参数
        dev_id = parse_bytes(data.get('dev_id'), 'dev_id')
        rff_score = float(data.get('rff_score', 0.0))
        rff_confidence = float(data.get('rff_confidence', 0.0))  # 保留但不使用
        snr = float(data.get('snr', 20.0))
        policy = data.get('policy', 'default')
        
        # 检查Mode1是否初始化
        if state.mode1_auth is None:
            return format_response(False, error="Mode1 not initialized. Please register a device first.", code=400)
        
        # 模拟RFF特征数据
        # 在实际系统中，这应该是从物理层获取的RFF特征字节串
        # 为API测试，我们使用确定性的方式生成特征数据
        # 如果RFF分数高（>= 0.8），使用与注册时相同的模板；否则使用不同的数据
        import hashlib
        import time
        if rff_score >= 0.8:
            # 高RFF分数：使用与注册模板相同的数据
            observed_features = hashlib.sha256(dev_id + b"_rff_template_seed").digest()
        else:
            # 低RFF分数：使用不同的数据来模拟不匹配
            feature_str = f"{dev_id.hex()}{rff_score:.4f}{snr:.2f}".encode()
            observed_features = hashlib.sha256(feature_str).digest()
        
        # 执行认证
        start_time = time.time()
        result = state.mode1_auth.authenticate(
            dev_id=dev_id,
            observed_features=observed_features,
            snr=snr,
            policy=policy
        )
        latency_ms = (time.time() - start_time) * 1000
        
        # 生成决策字段（基于认证结果）
        decision = "ACCEPT" if result.success else "REJECT"
        
        logger.info(f"模式1认证: {dev_id.hex()} - {decision} (延迟: {latency_ms:.2f}ms)")
        
        return format_response(True, {
            'authenticated': result.success,
            'dev_id': dev_id.hex(),
            'decision': decision,
            'reason': result.reason,
            'token_fast': base64.b64encode(result.token).decode() if result.token else None,
            'token_size': len(result.token) if result.token else 0,
            'latency_ms': round(latency_ms, 2)
        })
        
    except ValueError as e:
        logger.error(f"模式1认证失败: {e}")
        return format_response(False, error=str(e), code=400)
    except Exception as e:
        logger.error(f"模式1认证错误: {e}")
        return format_response(False, error=str(e), code=500)


# ============================================================================
# 模式2: 强认证 API
# ============================================================================

@app.route('/api/device/mode2/create_request', methods=['POST'])
def mode2_create_request():
    """
    模式2: 设备端创建认证请求
    
    Request Body:
        {
            "dev_id": "001122334455",           # 设备MAC地址（hex）
            "dst_mac": "AABBCCDDEEFF",          # 目标验证器MAC（hex）
            "csi": [[...], [...], ...],         # CSI数据（6x62矩阵）或base64
            "nonce": "hex...",                  # 随机数（可选，16字节hex）
            "seq": 1,                           # 序列号（可选）
            "csi_id": 12345                     # CSI标识（可选）
        }
    
    Response:
        {
            "success": true,
            "data": {
                "auth_req": "base64...",        # 序列化的AuthReq
                "session_key": "hex...",        # 会话密钥
                "feature_key": "hex...",        # 特征密钥（用于注册）
                "epoch": 0,
                "dev_pseudo": "hex...",
                "latency_ms": 15.3
            }
        }
    """
    try:
        data = request.get_json()
        
        # 解析参数
        dev_id = parse_bytes(data.get('dev_id'), 'dev_id')
        dst_mac = parse_bytes(data.get('dst_mac'), 'dst_mac')
        csi = parse_csi(data.get('csi'))
        nonce = parse_bytes(data.get('nonce')) if data.get('nonce') else secrets.token_bytes(16)
        seq = int(data.get('seq', 1))
        csi_id = int(data.get('csi_id', 12345))
        
        # 初始化Mode2（如果需要）
        if state.device_side is None:
            # 初始化同步服务
            state.sync_service = SynchronizationService(
                node_type="device",
                node_id=dev_id,
                domain="FeatureAuth",
                delta_t=30000,
                deterministic_for_testing=True
            )
            state.device_side = DeviceSide(
                config=state.auth_config,
                sync_service=state.sync_service
            )
            logger.info("模式2设备端已初始化")
        
        # 创建认证上下文
        context = AuthContext(
            src_mac=dev_id,
            dst_mac=dst_mac,
            epoch=state.sync_service.get_current_epoch(),
            nonce=nonce,
            seq=seq,
            alg_id='Mode2',
            ver=1,
            csi_id=csi_id
        )
        
        # 创建认证请求
        import time
        start_time = time.time()
        auth_req, session_key, feature_key = state.device_side.create_auth_request(
            dev_id=dev_id,
            Z_frames=csi,
            context=context
        )
        latency_ms = (time.time() - start_time) * 1000
        
        # 保存会话
        state.mode2_sessions[dev_id.hex()] = (session_key, auth_req)
        
        logger.info(f"模式2: 认证请求已创建 - {dev_id.hex()} (延迟: {latency_ms:.2f}ms)")
        
        return format_response(True, {
            'auth_req': base64.b64encode(auth_req.serialize()).decode(),
            'session_key': session_key.hex(),
            'feature_key': feature_key.hex(),
            'epoch': auth_req.epoch,
            'dev_pseudo': auth_req.dev_pseudo.hex(),
            'digest': auth_req.digest.hex(),
            'latency_ms': round(latency_ms, 2)
        })
        
    except ValueError as e:
        logger.error(f"模式2创建请求失败: {e}")
        return format_response(False, error=str(e), code=400)
    except Exception as e:
        logger.error(f"模式2创建请求错误: {e}")
        return format_response(False, error=str(e), code=500)


@app.route('/api/verifier/mode2/register', methods=['POST'])
def mode2_register_device():
    """
    模式2: 验证端注册设备
    
    Request Body:
        {
            "dev_id": "001122334455",           # 设备MAC地址（hex）
            "feature_key": "hex...",            # 特征密钥（32字节hex）
            "epoch": 0                          # Epoch编号
        }
    
    Response:
        {
            "success": true,
            "data": {
                "dev_id": "001122334455",
                "registered": true
            }
        }
    """
    try:
        data = request.get_json()
        
        # 解析参数
        dev_id = parse_bytes(data.get('dev_id'), 'dev_id')
        feature_key = parse_bytes(data.get('feature_key'), 'feature_key')
        epoch = int(data.get('epoch', 0))
        
        # 初始化Mode2验证端（如果需要）
        if state.verifier_side is None:
            # 初始化同步服务
            verifier_sync = SynchronizationService(
                node_type="validator",
                node_id=state.issuer_mac,
                domain="FeatureAuth",
                delta_t=30000,
                deterministic_for_testing=True
            )
            state.verifier_side = VerifierSide(
                config=state.auth_config,
                issuer_id=state.issuer_mac,
                issuer_key=state.issuer_key,
                sync_service=verifier_sync
            )
            logger.info("模式2验证端已初始化")
        
        # 注册设备
        state.verifier_side.register_device(dev_id, feature_key, epoch)
        state.mode2_devices[dev_id.hex()] = (feature_key, epoch)
        
        logger.info(f"模式2: 设备已注册 - {dev_id.hex()}")
        
        return format_response(True, {
            'dev_id': dev_id.hex(),
            'registered': True,
            'total_devices': len(state.mode2_devices)
        })
        
    except ValueError as e:
        logger.error(f"模式2注册失败: {e}")
        return format_response(False, error=str(e), code=400)
    except Exception as e:
        logger.error(f"模式2注册错误: {e}")
        return format_response(False, error=str(e), code=500)


@app.route('/api/verifier/mode2/verify', methods=['POST'])
def mode2_verify():
    """
    模式2: 验证端验证认证请求
    
    Request Body:
        {
            "auth_req": "base64...",            # 序列化的AuthReq（base64）
            "csi": [[...], [...], ...]          # CSI数据（6x62矩阵）或base64
        }
    
    Response:
        {
            "success": true,
            "data": {
                "authenticated": true,
                "dev_id": "001122334455",
                "session_key": "hex...",
                "mat_token": "base64...",
                "token_size": 74,
                "epoch": 0,
                "latency_ms": 18.7
            }
        }
    """
    try:
        data = request.get_json()
        
        # 解析参数
        auth_req_bytes = parse_bytes(data.get('auth_req'), 'auth_req')
        csi = parse_csi(data.get('csi'))
        
        # 检查Mode2验证端是否初始化
        if state.verifier_side is None:
            return format_response(False, error="Mode2 verifier not initialized. Please register a device first.", code=400)
        
        # 反序列化AuthReq
        auth_req = AuthReq.deserialize(auth_req_bytes)
        
        # 先尝试定位设备（获取真实的dev_id）
        dev_id = state.verifier_side.locate_device(auth_req.dev_pseudo, auth_req.epoch)
        
        # 执行验证
        import time
        start_time = time.time()
        result = state.verifier_side.verify_auth_request(auth_req, csi)
        latency_ms = (time.time() - start_time) * 1000
        
        # 如果验证成功但dev_id未知（理论上verify_auth_request内部能找到，但外部不知道）
        # 如果locate_device找到了，就使用它
        dev_id_hex = dev_id.hex() if dev_id else "unknown"
        
        logger.info(f"模式2验证: {dev_id_hex} - {'SUCCESS' if result.success else 'FAIL'} (延迟: {latency_ms:.2f}ms)")
        
        return format_response(True, {
            'authenticated': result.success,
            'dev_id': dev_id_hex,
            'reason': result.reason,
            'session_key': result.session_key.hex() if result.session_key else None,
            'mat_token': base64.b64encode(result.token).decode() if result.token else None,
            'token_size': len(result.token) if result.token else 0,
            'epoch': auth_req.epoch,
            'latency_ms': round(latency_ms, 2)
        })
        
    except ValueError as e:
        logger.error(f"模式2验证失败: {e}")
        return format_response(False, error=str(e), code=400)
    except Exception as e:
        logger.error(f"模式2验证错误: {e}")
        return format_response(False, error=str(e), code=500)


# ============================================================================
# 管理 API
# ============================================================================

@app.route('/api/status', methods=['GET'])
def get_status():
    """
    获取服务器状态
    
    Response:
        {
            "success": true,
            "data": {
                "mode1": {
                    "initialized": true,
                    "devices_count": 2
                },
                "mode2": {
                    "device_side_initialized": true,
                    "verifier_side_initialized": true,
                    "devices_count": 1,
                    "sessions_count": 1
                }
            }
        }
    """
    return format_response(True, {
        'mode1': {
            'initialized': state.mode1_auth is not None,
            'devices_count': len(state.mode1_devices)
        },
        'mode2': {
            'device_side_initialized': state.device_side is not None,
            'verifier_side_initialized': state.verifier_side is not None,
            'devices_count': len(state.mode2_devices),
            'sessions_count': len(state.mode2_sessions)
        },
        'server_version': '1.0.0'
    })


@app.route('/api/reset', methods=['POST'])
def reset_state():
    """
    重置所有状态
    
    Response:
        {
            "success": true,
            "data": {
                "message": "Server state reset successfully"
            }
        }
    """
    state.reset()
    return format_response(True, {
        'message': 'Server state reset successfully'
    })


@app.route('/', methods=['GET'])
def index():
    """根路径 - API文档"""
    return jsonify({
        'name': '基于特征的身份认证 API',
        'version': '1.0.0',
        'description': '提供模式1（RFF快速认证）和模式2（强认证）的RESTful API',
        'endpoints': {
            'mode1': {
                'POST /api/device/mode1/register': '注册设备',
                'POST /api/device/mode1/authenticate': 'RFF快速认证'
            },
            'mode2': {
                'POST /api/device/mode2/create_request': '设备端创建认证请求',
                'POST /api/verifier/mode2/register': '验证端注册设备',
                'POST /api/verifier/mode2/verify': '验证端验证请求'
            },
            'management': {
                'GET /api/status': '获取服务器状态',
                'POST /api/reset': '重置所有状态'
            }
        },
        'documentation': 'https://github.com/your-repo/README.md'
    })


# ============================================================================
# 启动服务器
# ============================================================================

if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("基于特征的身份认证 - API服务器")
    print("=" * 80)
    print()
    print("API端点:")
    print("  模式1 (RFF快速认证):")
    print("    POST http://localhost:5000/api/device/mode1/register")
    print("    POST http://localhost:5000/api/device/mode1/authenticate")
    print()
    print("  模式2 (强认证):")
    print("    POST http://localhost:5000/api/device/mode2/create_request")
    print("    POST http://localhost:5000/api/verifier/mode2/register")
    print("    POST http://localhost:5000/api/verifier/mode2/verify")
    print()
    print("  管理:")
    print("    GET  http://localhost:5000/api/status")
    print("    POST http://localhost:5000/api/reset")
    print()
    print("=" * 80)
    print()
    
    # 启动Flask服务器
    app.run(host='0.0.0.0', port=5000, debug=True)

