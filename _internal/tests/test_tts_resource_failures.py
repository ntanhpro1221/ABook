"""Specific allocation statuses take the existing bounded memory recovery path."""
import pytest

from abook.tts import is_fatal_tts_error, is_transient_tts_memory_error


@pytest.mark.parametrize("message", [
    "CUDA error: CUBLAS_STATUS_ALLOC_FAILED when calling cublasCreate(handle)",
    "cuDNN error: CUDNN_STATUS_ALLOC_FAILED",
    "CUDA error: cudaErrorMemoryAllocation",
])
def test_explicit_allocation_failure_is_transient(message):
    error = RuntimeError(message)
    assert is_transient_tts_memory_error(error)
    assert not is_fatal_tts_error(error)


@pytest.mark.parametrize("message", [
    "CUBLAS_STATUS_EXECUTION_FAILED", "CUBLAS_STATUS_NOT_INITIALIZED",
    "CUDNN_STATUS_INTERNAL_ERROR", "CUDA driver version is insufficient",
    "cuBLAS error: out of memory",
    "CUDA driver failure: CUBLAS_STATUS_ALLOC_FAILED",
    "CUBLAS_STATUS_ALLOC_FAILED then CUDNN_STATUS_INTERNAL_ERROR",
])
def test_other_driver_and_library_failures_remain_fatal(message):
    error = RuntimeError(message)
    assert is_fatal_tts_error(error)
    assert not is_transient_tts_memory_error(error)
