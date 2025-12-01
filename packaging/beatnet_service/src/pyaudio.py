"""
PyAudio Mock Module

PURPOSE: Satisfy BeatNet's pyaudio import without actual audio I/O
CONTEXT: BeatNet imports pyaudio for real-time mode, but we only use offline mode.
"""

# Mock constants
paInt16 = 8
paInt32 = 2
paFloat32 = 1

class PyAudio:
    """Mock PyAudio class - not functional."""
    
    def __init__(self):
        pass
    
    def open(self, *args, **kwargs):
        raise RuntimeError("PyAudio mock: Real-time audio not supported")
    
    def terminate(self):
        pass
    
    def get_device_count(self):
        return 0
