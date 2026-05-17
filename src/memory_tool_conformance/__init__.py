"""memory-tool-conformance: conformance suite + filesystem reference implementation for the LLM memory tool 6-op contract."""
from .conformance.contract import MemoryContract, ConformanceResult, ConformanceReport
from .reference.fs_memory import FilesystemMemory

__version__ = "1.0.0"
__all__ = ["MemoryContract", "ConformanceResult", "ConformanceReport", "FilesystemMemory"]
