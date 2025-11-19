"""
网络通信模块
"""
from .election import ClusterElection, ElectionMessage, ElectionMessageType
from .gossip import GossipProtocol, GossipMessage

__all__ = [
    'ClusterElection',
    'ElectionMessage',
    'ElectionMessageType',
    'GossipProtocol',
    'GossipMessage',
]
