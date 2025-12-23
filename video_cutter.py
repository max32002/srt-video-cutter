import argparse
import ffmpeg
import pysrt
import subprocess
import sys
import os
from typing import List, Tuple

# ---------------------------
# 工具函式
# ---------------------------

def get_video_duration(video_path: str) -> float:
    probe = ffmpeg.probe(video_path)
    return float(probe["format"]["duration"])


def parse_srt(srt_path: str) -> List[Tuple[float, float]]:
    subs = pysrt.open(srt_path)
    intervals = []
    for s in subs:
        start = s.start.ordinal / 1000.0
        end = s.end.ordinal / 1000.0
        if end > start:
            intervals.append((start, end))
    return intervals


def merge_short_segments(
    intervals: List[Tuple[float, float]],
    min_duration: float = 0.4,
    max_gap: float = 0.3,
):
    merged = []
    for start, end in intervals:
        if not merged:
            merged.append([start, end])
            continue

        prev_start, prev_end = merged[-1]
        duration = end - start
        gap = start - prev_end

        if duration < min_duration or gap <= max_gap:
            merged[-1][1] = max(prev_end, end)
        else:
            merged.append([start, end])

    return [(s, e) for s, e in merged]


def apply_padding(
    intervals: List[Tuple[float, float]],
    padding: float,
    max_duration: float,
):
    padded = []
    for start, end in intervals:
        s = max(0.0, start - padding)
        e = min(max_duration, end + padding)
        padded.append((s, e))
    return padded


def detect_silence(video_path: str, silence_db: float = -35, min_silence: float = 0.3):
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-af", f"silencedetect=n={silence_db}dB:d={min_silence}",
        "-f", "null",
        "-"
    ]

    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    silences = []
    silence_start = None

    for line in result.stderr.splitlines():
        if "silence_start" in line:
            silence_start = float(line.split("silence_start:")[1])
        elif "silence_end" in line and silence_start is not None:
            end = float(line.split("silence_end:")[1].split()[0])
            silences.append((silence_start, end))
            silence_start = None

    return silences


def is_inside_silence(interval, silences):
    s, e = interval
    for ss, se in silences:
        if s >= ss and e <= se:
            return True
    return False


# ---------------------------
# 主流程
# ---------------------------

def process_video(
    video_in,
    srt_in=None,
    video_out=None,
    min_duration=0.4,
    padding=0.15,
    highpass_freq=80,
    afftdn_nr=12,
    aecho="0.8:0.3:40:0.2",
    speechnorm_e=4,
    speechnorm_p=0.9,
):
    if not os.path.exists(video_in):
        sys.exit(f"找不到影片：{video_in}")

    base, ext = os.path.splitext(video_in)
    srt_in = srt_in or f"{base}.srt"
    video_out = video_out or f"{base}_cut{ext}"

    if not os.path.exists(srt_in):
        sys.exit(f"找不到字幕：{srt_in}")

    print("解析字幕...")
    intervals = parse_srt(srt_in)

    print("合併過短字幕...")
    intervals = merge_short_segments(intervals, min_duration)

    duration = get_video_duration(video_in)

    print("補前後緩衝...")
    intervals = apply_padding(intervals, padding, duration)

    print("進行靜音偵測...")
    silences = detect_silence(video_in)

    final_intervals = [
        i for i in intervals
        if not is_inside_silence(i, silences)
    ]

    if not final_intervals:
        sys.exit("沒有可用剪輯區間")

    print(f"最終剪輯段數：{len(final_intervals)}")

    inp = ffmpeg.input(video_in)
    segments = []

    for start, end in final_intervals:
        v = inp.video.filter("trim", start=start, end=end).filter("setpts", "PTS-STARTPTS")
        a = inp.audio.filter("atrim", start=start, end=end).filter("asetpts", "PTS-STARTPTS")
        segments.extend([v, a])

    # 1. 建立 Concat 節點
    joined = ffmpeg.concat(*segments, v=1, a=1, n=len(segments)//2).node
    
    # 2. 明確指定索引：[0]是視訊, [1]是音訊 (避免 Media type mismatch)
    v_stream = joined[0]
    a_stream = joined[1]

    # 3. 對音訊串流應用濾鏡鏈
    # 目標參數: "highpass=f=80, afftdn=nr=12, aecho=0.8:0.3:40:0.2, speechnorm=e=4:p=0.9"
    a_stream = (
        a_stream
        .filter("highpass", f=80)
        .filter("afftdn", nr=12)
        .filter("aecho", 0.8, 0.3, 40, 0.2)
        .filter("speechnorm", e=4, p=0.9)
    )

    # 4. 輸出
    out = ffmpeg.output(v_stream, a_stream, video_out)

    out.run(overwrite_output=True, quiet=True)
    print(f"完成輸出：{video_out}")


def main():
    p = argparse.ArgumentParser("Subtitle-based smart video cutter")
    p.add_argument("input")
    p.add_argument("-s", "--srt")
    p.add_argument("-o", "--output")
    p.add_argument("--min-duration", type=float, default=0.4)
    p.add_argument("--padding", type=float, default=0.15)

    p.add_argument("--highpass", type=int, default=80, help="Highpass filter freq (0=off)")
    p.add_argument("--afftdn", type=int, default=12, help="FFT denoise level (0=off)")
    p.add_argument("--aecho", default="0.8:0.3:40:0.2", help="aecho in:out:delay:decay")
    p.add_argument("--speechnorm-e", type=int, default=4)
    p.add_argument("--speechnorm-p", type=float, default=0.9)

    args = p.parse_args()

    process_video(
        args.input,
        args.srt,
        args.output,
        args.min_duration,
        args.padding,
        args.highpass,
        args.afftdn,
        args.aecho,
        args.speechnorm_e,
        args.speechnorm_p,
    )


if __name__ == "__main__":
    main()
