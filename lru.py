# Simple LRU cache implementation to replace lru-dict
from functools import lru_cache
import threading

class LRU:
    def __init__(self, max_size=128):
        self.max_size = max_size
        self.cache = {}
        self.lock = threading.Lock()
    
    def get(self, key, default=None):
        with self.lock:
            return self.cache.get(key, default)
    
    def set(self, key, value):
        with self.lock:
            if len(self.cache) >= self.max_size:
                # Remove oldest item
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
            self.cache[key] = value
    
    def __getitem__(self, key):
        return self.cache[key]
    
    def __setitem__(self, key, value):
        self.set(key, value)
    
    def __contains__(self, key):
        return key in self.cache
    
    def __len__(self):
        return len(self.cache)
