"""Driver compatibility checks without changing any installed GPU packages."""
import ctypes


def cuda_driver_version():
    """Read the host driver's CUDA API version, e.g. 12040, when available."""
    try:
        cuda = ctypes.CDLL("libcuda.so.1")
        version = ctypes.c_int()
        get_version = cuda.cuDriverGetVersion
        get_version.argtypes = [ctypes.POINTER(ctypes.c_int)]
        get_version.restype = ctypes.c_int
        if get_version(ctypes.byref(version)) == 0 and version.value > 0:
            return version.value
    except (OSError, AttributeError):
        pass
    return None


def check_driver_compatibility(runtime_cuda, driver_api):
    """Reject a known major-family mismatch; actual GPU checks follow.

    CUDA 11+ supports minor version compatibility. In particular, a 12.8
    runtime on a 12.4 driver is not a major mismatch. This check does not
    establish support for every kernel, GPU architecture or PTX feature.
    """
    if not runtime_cuda or driver_api is None:
        return
    runtime_major = int(runtime_cuda.split(".")[0])
    driver_major = driver_api // 1000
    if runtime_major >= 11 and driver_major < runtime_major:
        driver_minor = (driver_api % 1000) // 10
        remedy = (
            "Container Imageを ghcr.io/grawthings-beep/illustrious:cuda12 に変更してください。"
            if runtime_major >= 13 and driver_major == 12 else
            "対応するNVIDIAドライバーのGPUホストを選択してください。"
        )
        raise RuntimeError(
            f"CUDAの互換性エラー: PyTorchはCUDA {runtime_cuda}用ですが、"
            f"PodのドライバーはCUDA API {driver_major}.{driver_minor}です。"
            + remedy + "環境変数やSecretの設定が原因ではありません。"
        )
