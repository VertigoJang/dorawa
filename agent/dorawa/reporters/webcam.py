"""웹캠 사진 1장. 기본 비활성 — config에서 켜야만 호출된다."""
import glob
import os
import subprocess


def capture(out_path):
    """사진 1장. 성공 시 촬영한 장치 경로(str), 실패 시 None."""
    for dev in sorted(glob.glob("/dev/video*")):
        try:
            subprocess.run(
                ["ffmpeg", "-loglevel", "error", "-f", "v4l2",
                 "-i", dev, "-frames:v", "1", "-y", out_path],
                timeout=15, stderr=subprocess.DEVNULL)
        except Exception:
            continue
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return dev
    return None


def record(out_path, seconds=10):
    """영상 녹화. 성공 시 촬영한 장치 경로(str), 실패 시 None."""
    for dev in sorted(glob.glob("/dev/video*")):
        try:
            subprocess.run(
                ["ffmpeg", "-loglevel", "error", "-f", "v4l2",
                 "-i", dev, "-t", str(seconds),
                 "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                 "-y", out_path],
                timeout=seconds + 30, stderr=subprocess.DEVNULL)
        except Exception:
            continue
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return dev
    return None
