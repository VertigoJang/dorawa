"""웹캠 사진 1장 / 10초 영상. 기본 비활성 — config에서 켜야만 호출된다."""
import glob
import os
import subprocess

# H.264(웹·앱 재생 호환) 인코더 우선순위. 배포판마다 들어있는 게 달라서
# 순서대로 시도하고, 처음 성공하는 것을 쓴다.
#   - libx264      : 데비안/우분투 기본
#   - libopenh264  : 페도라/RHEL(RPM Fusion) 기본
#   - h264_v4l2m2m : 일부 기기의 하드웨어 H.264 인코더
#   - mpeg4        : 최후의 보루(거의 모든 ffmpeg에 존재). H.264보다 호환성은 낮지만
#                    아무 인코더도 없을 때 영상이 아예 안 남는 것보단 낫다.
# 주의: libopenh264 / 하드웨어 인코더는 비트레이트(-b:v)를 안 주면
# "Unable to create encoder"로 실패한다. 그래서 명시적으로 지정한다.
_VIDEO_ENCODERS = [
    ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"],
    ["-c:v", "libopenh264", "-b:v", "1500k", "-pix_fmt", "yuv420p"],
    ["-c:v", "h264_v4l2m2m", "-b:v", "1500k", "-pix_fmt", "yuv420p"],
    ["-c:v", "mpeg4", "-q:v", "5", "-pix_fmt", "yuv420p"],
]


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
    """영상 녹화. 성공 시 촬영한 장치 경로(str), 실패 시 None.

    배포판마다 사용 가능한 H.264 인코더가 달라서, 장치 x 인코더 조합을
    순서대로 시도한다. 사진은 되는데 영상만 안 되던 문제(libx264 미탑재)는
    이 폴백으로 해결된다.
    """
    for dev in sorted(glob.glob("/dev/video*")):
        for enc in _VIDEO_ENCODERS:
            # 이전 시도의 반쪽짜리 파일이 성공으로 오인되지 않게 먼저 제거
            try:
                if os.path.exists(out_path):
                    os.remove(out_path)
            except Exception:
                pass
            try:
                subprocess.run(
                    ["ffmpeg", "-loglevel", "error", "-f", "v4l2",
                     "-i", dev, "-t", str(seconds)] + enc + ["-y", out_path],
                    timeout=seconds + 30, stderr=subprocess.DEVNULL)
            except Exception:
                continue
            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                return dev
    return None
