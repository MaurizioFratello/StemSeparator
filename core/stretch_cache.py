"""
Stretch Cache - LRU cache for time-stretched audio loops

PURPOSE: Cache time-stretched loops in memory for instant preview and export.
         Implements LRU (Least Recently Used) eviction with size management.

CONTEXT: Used by BackgroundStretchManager to store results.
         Prevents re-processing when user previews loops or exports.

ALGORITHM: LRU (Least Recently Used) eviction
           - Tracks access order
           - Evicts oldest items when cache is full
           - Efficient O(1) access with dict + list

SIZE CALCULATION:
    Typical loop: 10 seconds, 44100 Hz, stereo, float32
    Size = 10s × 44100 Hz × 2 channels × 4 bytes = 3.5 MB

    4 stems × 8 loops × 3.5 MB = ~112 MB per song

    Recommended cache size:
    - 500 MB (default): ~4-5 songs
    - 200 MB (minimum): ~2 songs

USAGE:
    >>> cache = StretchCache(max_size_mb=500)
    >>>
    >>> # Store stretched loop
    >>> cache.put('drums_0_120', stretched_audio)
    >>>
    >>> # Retrieve loop
    >>> audio = cache.get('drums_0_120')  # Updates LRU order
    >>>
    >>> # Check if cached
    >>> if cache.has('vocals_3_120'):
    ...     audio = cache.get('vocals_3_120')
    >>>
    >>> # Get statistics
    >>> stats = cache.get_stats()
    >>> print(f"Cache: {stats['size_mb']:.1f} MB, {stats['hit_rate']:.1%} hit rate")
"""

from typing import Dict, List, Optional
import numpy as np

from utils.logger import get_logger

logger = get_logger()


class StretchCache:
    """
    LRU cache for time-stretched audio loops.

    Features:
    - Size-based eviction (MB limit)
    - LRU (Least Recently Used) algorithm
    - Memory estimation for numpy arrays
    - Statistics tracking (hits, misses, hit rate)
    """

    def __init__(self, max_size_mb: int = 500):
        """
        Initialize stretch cache.

        Args:
            max_size_mb: Maximum cache size in megabytes
                        Default: 500 MB (~4-5 songs)
                        Minimum: 200 MB (~2 songs)

        Example:
            >>> cache = StretchCache(max_size_mb=500)
            >>> # Can store ~140 loops (4 stems × 8 loops × ~4 songs)
        """

        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.cache: Dict[str, np.ndarray] = {}
        self.access_order: List[str] = []  # LRU tracking
        self.current_size_bytes = 0

        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0

        logger.info(f"StretchCache initialized: max size = {max_size_mb} MB")

    def _estimate_size(self, audio: np.ndarray) -> int:
        """
        Estimate memory size of audio array in bytes.

        Args:
            audio: Audio numpy array

        Returns:
            Size in bytes

        Example:
            >>> audio = np.zeros((441000, 2), dtype=np.float32)  # 10s stereo
            >>> cache._estimate_size(audio)
            3528000  # ~3.5 MB
        """

        return audio.nbytes

    def put(self, key: str, audio: np.ndarray):
        """
        Add audio to cache.

        If cache is full, evicts least recently used items until
        there is enough space.

        Args:
            key: Cache key (e.g., 'drums_0_120')
            audio: Audio array to cache

        Example:
            >>> cache.put('drums_0_120', stretched_audio)
        """

        audio_size = self._estimate_size(audio)

        # Check if key already exists
        if key in self.cache:
            # Update existing entry
            old_size = self._estimate_size(self.cache[key])
            self.current_size_bytes -= old_size

            # Update access order
            if key in self.access_order:
                self.access_order.remove(key)

        # Evict if necessary
        while (
            self.current_size_bytes + audio_size > self.max_size_bytes
            and self.access_order
        ):
            # Evict LRU item
            lru_key = self.access_order.pop(0)
            if lru_key in self.cache:
                evicted_audio = self.cache.pop(lru_key)
                evicted_size = self._estimate_size(evicted_audio)
                self.current_size_bytes -= evicted_size
                self.evictions += 1

                logger.debug(
                    f"Evicted LRU item: {lru_key} ({evicted_size / (1024**2):.2f} MB)"
                )

        # Add to cache
        self.cache[key] = audio
        self.access_order.append(key)
        self.current_size_bytes += audio_size

        logger.debug(
            f"Cached: {key} ({audio_size / (1024**2):.2f} MB), "
            f"total: {self.current_size_bytes / (1024**2):.1f} MB"
        )

    def get(self, key: str) -> Optional[np.ndarray]:
        """
        Get audio from cache.

        Updates LRU order (marks as recently used).

        Args:
            key: Cache key

        Returns:
            Audio array or None if not in cache

        Example:
            >>> audio = cache.get('drums_0_120')
            >>> if audio is not None:
            ...     play(audio)
        """

        if key in self.cache:
            # Update LRU order
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)

            self.hits += 1
            return self.cache[key]
        else:
            self.misses += 1
            return None

    def has(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Does NOT update LRU order (use get() for that).

        Args:
            key: Cache key

        Returns:
            True if key is in cache

        Example:
            >>> if cache.has('drums_0_120'):
            ...     audio = cache.get('drums_0_120')
        """

        return key in self.cache

    def clear(self):
        """
        Clear entire cache.

        Resets all statistics.

        Example:
            >>> cache.clear()
            >>> cache.get_stats()['item_count']
            0
        """

        self.cache.clear()
        self.access_order.clear()
        self.current_size_bytes = 0

        logger.info("Cache cleared")

    def remove(self, key: str) -> bool:
        """
        Remove specific item from cache.

        Args:
            key: Cache key to remove

        Returns:
            True if item was removed, False if not found

        Example:
            >>> cache.remove('drums_0_120')
            True
        """

        if key in self.cache:
            audio = self.cache.pop(key)
            if key in self.access_order:
                self.access_order.remove(key)

            removed_size = self._estimate_size(audio)
            self.current_size_bytes -= removed_size

            logger.debug(f"Removed: {key} ({removed_size / (1024**2):.2f} MB)")
            return True

        return False

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dict with statistics:
            - size_mb: Current cache size in MB
            - max_size_mb: Maximum cache size in MB
            - usage_percent: Percentage of max size used
            - item_count: Number of cached items
            - hits: Number of cache hits
            - misses: Number of cache misses
            - hit_rate: Hit rate (0.0 to 1.0)
            - evictions: Number of items evicted

        Example:
            >>> stats = cache.get_stats()
            >>> print(f"Cache: {stats['size_mb']:.1f} MB / {stats['max_size_mb']} MB")
            >>> print(f"Hit rate: {stats['hit_rate']:.1%}")
            Cache: 123.4 MB / 500 MB
            Hit rate: 85.3%
        """

        total_accesses = self.hits + self.misses
        hit_rate = self.hits / total_accesses if total_accesses > 0 else 0.0

        size_mb = self.current_size_bytes / (1024 * 1024)
        max_size_mb = self.max_size_bytes / (1024 * 1024)
        usage_percent = (size_mb / max_size_mb * 100) if max_size_mb > 0 else 0.0

        return {
            'size_mb': size_mb,
            'max_size_mb': max_size_mb,
            'usage_percent': usage_percent,
            'item_count': len(self.cache),
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': hit_rate,
            'evictions': self.evictions
        }

    def get_keys(self) -> List[str]:
        """
        Get list of all cached keys.

        Returns:
            List of cache keys

        Example:
            >>> cache.get_keys()
            ['drums_0_120', 'drums_1_120', 'vocals_0_120', ...]
        """

        return list(self.cache.keys())

    def get_lru_order(self) -> List[str]:
        """
        Get LRU order (oldest to newest).

        Returns:
            List of keys in LRU order (index 0 = oldest, -1 = newest)

        Example:
            >>> cache.get_lru_order()
            ['vocals_2_120', 'drums_0_120', 'drums_3_120']
            # 'vocals_2_120' will be evicted first if cache is full
        """

        return self.access_order.copy()


# ============================================================================
# Cache Factory & Configuration
# ============================================================================

# Recommended cache sizes based on use case
CACHE_SIZE_LARGE = 500  # MB - for professional users, long sessions
CACHE_SIZE_STANDARD = 300  # MB - for typical use
CACHE_SIZE_SMALL = 200  # MB - for systems with limited RAM


def create_cache(size_preset: str = 'standard') -> StretchCache:
    """
    Create cache with preset size.

    Args:
        size_preset: 'small', 'standard', or 'large'

    Returns:
        StretchCache instance

    Example:
        >>> cache = create_cache('large')
        >>> cache.get_stats()['max_size_mb']
        500
    """

    size_map = {
        'small': CACHE_SIZE_SMALL,
        'standard': CACHE_SIZE_STANDARD,
        'large': CACHE_SIZE_LARGE
    }

    size_mb = size_map.get(size_preset, CACHE_SIZE_STANDARD)

    return StretchCache(max_size_mb=size_mb)
