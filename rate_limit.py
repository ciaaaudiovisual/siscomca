import time
from functools import wraps
from typing import Dict, Optional
import threading


class RateLimiter:
    """Rate limiter em memória"""
    
    def __init__(self):
        self._requests: Dict[str, list] = {}
        self._lock = threading.Lock()
    
    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """Verifica se request é permitido"""
        with self._lock:
            now = time.time()
            
            if key not in self._requests:
                self._requests[key] = []
            
            requests = self._requests[key]
            requests = [t for t in requests if now - t < window_seconds]
            self._requests[key] = requests
            
            if len(requests) >= max_requests:
                return False
            
            requests.append(now)
            return True
    
    def get_remaining(self, key: str, max_requests: int, window_seconds: int) -> int:
        """Retorna requests restantes"""
        with self._lock:
            now = time.time()
            if key not in self._requests:
                return max_requests
            
            requests = self._requests[key]
            requests = [t for t in requests if now - t < window_seconds]
            return max(0, max_requests - len(requests))
    
    def reset(self, key: str):
        """Reseta contador para chave"""
        with self._lock:
            if key in self._requests:
                del self._requests[key]
    
    def cleanup(self):
        """Remove entradas antigas"""
        with self._lock:
            now = time.time()
            for key in list(self._requests.keys()):
                self._requests[key] = [t for t in self._requests[key] if now - t < 3600]
                if not self._requests[key]:
                    del self._requests[key]


rate_limiter = RateLimiter()


def rate_limit(max_requests: int = 60, window_seconds: int = 60, key_func=None):
    """Decorator para rate limiting"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from nicegui import app
            
            client_ip = app.storage.user.get('client_ip', 'anonymous')
            if key_func:
                key = f"{client_ip}:{key_func(*args, **kwargs)}"
            else:
                key = f"{client_ip}:{func.__name__}"
            
            if not rate_limiter.is_allowed(key, max_requests, window_seconds):
                remaining = rate_limiter.get_remaining(key, max_requests, window_seconds)
                return {
                    'error': 'Rate limit excedido',
                    'retry_after': window_seconds,
                    'remaining': remaining
                }, 429
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


class Cache:
    """Cache simples em memória (sem Redis)"""
    
    def __init__(self):
        self._cache: Dict[str, tuple] = {}
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[any]:
        with self._lock:
            if key in self._cache:
                value, expires = self._cache[key]
                if expires is None or time.time() < expires:
                    return value
                del self._cache[key]
        return None
    
    def set(self, key: str, value: any, ttl: int = 300):
        with self._lock:
            expires = time.time() + ttl if ttl else None
            self._cache[key] = (value, expires)
    
    def delete(self, key: str):
        with self._lock:
            if key in self._cache:
                del self._cache[key]
    
    def clear(self):
        with self._lock:
            self._cache.clear()
    
    def cleanup(self):
        with self._lock:
            now = time.time()
            for key in list(self._cache.keys()):
                _, expires = self._cache[key]
                if expires and now >= expires:
                    del self._cache[key]


cache = Cache()


def cached(ttl: int = 300, key_func=None):
    """Decorator para caching de funções"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if key_func:
                cache_key = f"{func.__name__}:{key_func(*args, **kwargs)}"
            else:
                cache_key = f"{func.__name__}:{str(args)}"
            
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator


def get_cache_stats():
    """Retorna estatísticas do cache"""
    return {
        'keys': len(cache._cache),
        'memory_items': len(rate_limiter._requests),
    }


def clear_cache():
    """Limpa todo o cache"""
    cache.clear()
    ui.notify('Cache limpo', color='info')
