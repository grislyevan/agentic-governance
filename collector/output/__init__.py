from .emitter import EventEmitter

__all__ = ["EventEmitter"]

try:
    from .tcp_emitter import TcpEmitter
    __all__.append("TcpEmitter")
except ImportError:
    pass
