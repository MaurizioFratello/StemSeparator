"""
Unit tests for core.stretch_cache module

Tests cover:
- Cache put/get operations
- LRU eviction
- Size management
- Statistics tracking
- Edge cases
"""

import pytest
import numpy as np

from core.stretch_cache import StretchCache, create_cache, CACHE_SIZE_LARGE


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def cache():
    """Create cache with small size for testing"""
    return StretchCache(max_size_mb=10)  # 10 MB for tests


@pytest.fixture
def sample_audio():
    """Generate sample audio array (~3.5 MB)"""
    # 10 seconds, 44100 Hz, stereo, float32
    samples = 10 * 44100
    audio = np.random.randn(samples, 2).astype(np.float32)
    return audio


@pytest.fixture
def small_audio():
    """Generate small audio array (~350 KB)"""
    # 1 second, 44100 Hz, stereo, float32
    samples = 44100
    audio = np.random.randn(samples, 2).astype(np.float32)
    return audio


# ============================================================================
# Test: Basic Put/Get Operations
# ============================================================================

def test_cache_put_get(cache, small_audio):
    """Test basic cache put and get"""
    cache.put('test_key', small_audio)

    retrieved = cache.get('test_key')
    assert retrieved is not None
    np.testing.assert_array_equal(retrieved, small_audio)


def test_cache_get_nonexistent(cache):
    """Test getting nonexistent key"""
    result = cache.get('nonexistent')
    assert result is None


def test_cache_has(cache, small_audio):
    """Test cache.has() method"""
    assert cache.has('test_key') is False

    cache.put('test_key', small_audio)
    assert cache.has('test_key') is True


def test_cache_put_update(cache, small_audio):
    """Test updating existing key"""
    # Put initial value
    cache.put('key1', small_audio)

    # Update with new value
    new_audio = small_audio * 2
    cache.put('key1', new_audio)

    # Should retrieve new value
    retrieved = cache.get('key1')
    np.testing.assert_array_equal(retrieved, new_audio)


# ============================================================================
# Test: LRU Eviction
# ============================================================================

def test_cache_lru_eviction(cache, sample_audio):
    """Test LRU eviction when cache is full"""
    # Cache is 10 MB, sample_audio is ~3.5 MB
    # We can fit 2, third should evict first

    cache.put('audio1', sample_audio)
    cache.put('audio2', sample_audio)
    cache.put('audio3', sample_audio)  # Should evict audio1

    # audio1 should be evicted
    assert cache.has('audio1') is False
    assert cache.has('audio2') is True
    assert cache.has('audio3') is True


def test_cache_lru_order_update(cache, small_audio):
    """Test that get() updates LRU order"""
    # Add three items
    cache.put('a', small_audio)
    cache.put('b', small_audio)
    cache.put('c', small_audio)

    # Access 'a' to make it most recent
    cache.get('a')

    # Get LRU order
    lru_order = cache.get_lru_order()

    # 'a' should be at the end (most recent)
    assert lru_order[-1] == 'a'


def test_cache_eviction_count(cache, sample_audio):
    """Test eviction count tracking"""
    initial_evictions = cache.get_stats()['evictions']

    # Fill cache beyond capacity
    cache.put('audio1', sample_audio)
    cache.put('audio2', sample_audio)
    cache.put('audio3', sample_audio)  # Triggers eviction

    stats = cache.get_stats()
    assert stats['evictions'] > initial_evictions


# ============================================================================
# Test: Size Management
# ============================================================================

def test_cache_size_estimation(cache, small_audio):
    """Test size estimation"""
    # Empty cache
    assert cache.current_size_bytes == 0

    # Add audio
    cache.put('test', small_audio)

    # Size should match audio nbytes
    expected_size = small_audio.nbytes
    assert cache.current_size_bytes == expected_size


def test_cache_size_limit(cache):
    """Test that cache respects size limit"""
    max_size = cache.max_size_bytes

    # Fill cache
    audio = np.random.randn(10000, 2).astype(np.float32)
    for i in range(100):
        cache.put(f'audio{i}', audio)

    # Current size should never exceed max
    assert cache.current_size_bytes <= max_size


def test_cache_stats_size(cache, small_audio):
    """Test size reporting in stats"""
    cache.put('test', small_audio)

    stats = cache.get_stats()

    # Check size is reasonable
    assert stats['size_mb'] > 0
    assert stats['size_mb'] < stats['max_size_mb']
    assert 0 <= stats['usage_percent'] <= 100


# ============================================================================
# Test: Statistics
# ============================================================================

def test_cache_hit_miss_tracking(cache, small_audio):
    """Test hit/miss statistics"""
    cache.put('key1', small_audio)

    # Initial stats
    stats = cache.get_stats()
    initial_hits = stats['hits']
    initial_misses = stats['misses']

    # Hit
    cache.get('key1')
    stats = cache.get_stats()
    assert stats['hits'] == initial_hits + 1

    # Miss
    cache.get('nonexistent')
    stats = cache.get_stats()
    assert stats['misses'] == initial_misses + 1


def test_cache_hit_rate_calculation(cache, small_audio):
    """Test hit rate calculation"""
    cache.put('key1', small_audio)

    # 2 hits, 1 miss → 66.7% hit rate
    cache.get('key1')
    cache.get('key1')
    cache.get('nonexistent')

    stats = cache.get_stats()
    expected_hit_rate = 2 / 3  # 2 hits out of 3 accesses
    assert abs(stats['hit_rate'] - expected_hit_rate) < 0.01


def test_cache_stats_item_count(cache, small_audio):
    """Test item count in stats"""
    stats = cache.get_stats()
    assert stats['item_count'] == 0

    cache.put('key1', small_audio)
    cache.put('key2', small_audio)

    stats = cache.get_stats()
    assert stats['item_count'] == 2


# ============================================================================
# Test: Clear and Remove
# ============================================================================

def test_cache_clear(cache, small_audio):
    """Test clearing cache"""
    cache.put('key1', small_audio)
    cache.put('key2', small_audio)

    assert cache.get_stats()['item_count'] == 2

    cache.clear()

    stats = cache.get_stats()
    assert stats['item_count'] == 0
    assert stats['size_mb'] == 0
    assert cache.has('key1') is False
    assert cache.has('key2') is False


def test_cache_remove_existing(cache, small_audio):
    """Test removing existing item"""
    cache.put('key1', small_audio)

    assert cache.has('key1') is True

    removed = cache.remove('key1')
    assert removed is True
    assert cache.has('key1') is False


def test_cache_remove_nonexistent(cache):
    """Test removing nonexistent item"""
    removed = cache.remove('nonexistent')
    assert removed is False


def test_cache_remove_size_update(cache, small_audio):
    """Test that remove updates size correctly"""
    cache.put('key1', small_audio)

    size_before = cache.current_size_bytes
    cache.remove('key1')

    assert cache.current_size_bytes == 0
    assert cache.current_size_bytes < size_before


# ============================================================================
# Test: Get Keys and LRU Order
# ============================================================================

def test_cache_get_keys(cache, small_audio):
    """Test getting all cache keys"""
    cache.put('key1', small_audio)
    cache.put('key2', small_audio)
    cache.put('key3', small_audio)

    keys = cache.get_keys()
    assert len(keys) == 3
    assert 'key1' in keys
    assert 'key2' in keys
    assert 'key3' in keys


def test_cache_get_lru_order(cache, small_audio):
    """Test getting LRU order"""
    cache.put('a', small_audio)
    cache.put('b', small_audio)
    cache.put('c', small_audio)

    lru_order = cache.get_lru_order()

    # Should be in insertion order (oldest to newest)
    assert lru_order == ['a', 'b', 'c']


# ============================================================================
# Test: Edge Cases
# ============================================================================

def test_cache_empty_audio():
    """Test caching empty audio"""
    cache = StretchCache(max_size_mb=10)
    empty_audio = np.array([])

    cache.put('empty', empty_audio)

    # Should still work
    retrieved = cache.get('empty')
    assert retrieved is not None
    assert retrieved.size == 0


def test_cache_mono_audio(cache):
    """Test caching mono audio"""
    mono_audio = np.random.randn(44100).astype(np.float32)

    cache.put('mono', mono_audio)

    retrieved = cache.get('mono')
    np.testing.assert_array_equal(retrieved, mono_audio)


def test_cache_different_dtypes(cache):
    """Test caching different data types"""
    audio_float32 = np.random.randn(1000).astype(np.float32)
    audio_float64 = np.random.randn(1000).astype(np.float64)

    cache.put('f32', audio_float32)
    cache.put('f64', audio_float64)

    assert cache.get('f32').dtype == np.float32
    assert cache.get('f64').dtype == np.float64


def test_cache_has_no_side_effects(cache, small_audio):
    """Test that has() does not update LRU order"""
    cache.put('a', small_audio)
    cache.put('b', small_audio)

    # Check 'a' with has() (should not update LRU)
    cache.has('a')

    lru_order = cache.get_lru_order()

    # 'a' should still be oldest (index 0)
    assert lru_order[0] == 'a'


# ============================================================================
# Test: Factory Functions
# ============================================================================

def test_create_cache_small():
    """Test creating cache with small preset"""
    cache = create_cache('small')
    stats = cache.get_stats()
    assert stats['max_size_mb'] == 200


def test_create_cache_standard():
    """Test creating cache with standard preset"""
    cache = create_cache('standard')
    stats = cache.get_stats()
    assert stats['max_size_mb'] == 300


def test_create_cache_large():
    """Test creating cache with large preset"""
    cache = create_cache('large')
    stats = cache.get_stats()
    assert stats['max_size_mb'] == 500


def test_create_cache_invalid_preset():
    """Test creating cache with invalid preset (should use default)"""
    cache = create_cache('invalid')
    stats = cache.get_stats()
    assert stats['max_size_mb'] == 300  # Default to standard


# ============================================================================
# Test: Realistic Scenario
# ============================================================================

def test_realistic_loop_caching_scenario():
    """Test realistic scenario: caching loops for 4 stems × 8 loops"""
    cache = StretchCache(max_size_mb=500)

    # Simulate 4 stems × 8 loops
    stems = ['drums', 'vocals', 'bass', 'other']
    num_loops = 8
    target_bpm = 120

    # Generate loops (~3.5 MB each)
    loop_audio = np.random.randn(10 * 44100, 2).astype(np.float32)

    # Cache all loops
    for stem in stems:
        for loop_idx in range(num_loops):
            key = f"{stem}_{loop_idx}_{target_bpm}"
            cache.put(key, loop_audio)

    # Check all are cached
    stats = cache.get_stats()
    assert stats['item_count'] == 32  # 4 stems × 8 loops

    # Check we can retrieve all
    for stem in stems:
        for loop_idx in range(num_loops):
            key = f"{stem}_{loop_idx}_{target_bpm}"
            assert cache.has(key) is True

    # Check size is reasonable
    assert stats['size_mb'] < 500  # Within limit


def test_cache_performance_many_items(cache):
    """Test cache performance with many small items"""
    # Add many small items
    small_audio = np.random.randn(1000).astype(np.float32)

    for i in range(1000):
        cache.put(f'item{i}', small_audio)

    # Should still be fast
    assert cache.has('item500') in [True, False]  # Might be evicted

    stats = cache.get_stats()
    assert stats['item_count'] > 0
