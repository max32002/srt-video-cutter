import os
import shutil
import shlex
import subprocess
import math
import re

import uvicorn
from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from typing import List

from faster_whisper import WhisperModel
from contextlib import ExitStack

app = FastAPI()

if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

if not os.path.exists("templates"):
    os.makedirs("templates")

# --- 輔助函式：將秒數轉為 SRT 時間格式 (00:00:00,000) ---
def format_timestamp(seconds: float):
    x = seconds
    hours = int(x // 3600)
    x %= 3600
    minutes = int(x // 60)
    x %= 60
    seconds = int(x)
    milliseconds = int((x - seconds) * 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def split_sentences(text: str):
    pattern = r'(?<=[。！？!?；;])'
    parts = re.split(pattern, text)
    return [p.strip() for p in parts if p.strip()]

def split_by_length(text: str, max_len: int):
    lines = []
    buf = ""
    for ch in text:
        buf += ch
        if len(buf) >= max_len:
            lines.append(buf)
            buf = ""
    if buf:
        lines.append(buf)
    return lines

def build_subtitle_blocks(text: str, max_line_len=22, max_lines=2):
    sentences = split_sentences(text)
    blocks = []

    for sent in sentences:
        lines = split_by_length(sent, max_line_len)

        for i in range(0, len(lines), max_lines):
            block = lines[i:i + max_lines]
            blocks.append("\n".join(block))

    return blocks


def run_faster_whisper_task(
    input_file: str, 
    language: str, 
    model_size: str, 
    device: str, 
    output_formats: List[str],
    max_line_len: int = 22
):
    try:
        print(f"--- 開始處理: {input_file} (Device: {device}, Model: {model_size}) ---")
        
        compute_type = "float16" if device == "cuda" else "int8"
        model = WhisperModel(model_size, device=device, compute_type=compute_type)

        # 加入優化參數解決長延遲問題
        segments, info = model.transcribe(
            input_file, 
            language=language, 
            vad_filter=True,
            # 關閉前文關聯，防止模型為了連貫性把句子硬湊在一起
            condition_on_previous_text=False,
            # 縮短靜音判定，強制切分
            vad_parameters=dict(
                min_silence_duration_ms=300,  # 只要停頓 0.3 秒就切斷
                max_speech_duration_s=3,     # 強制每一段話最長不能超過 4 秒
                speech_pad_ms=200             # 減少片段前后的緩衝音
            ),
            # beam_size 設小一點有助於減少模型過度延伸的幻覺
            beam_size=5,
            # 提高對無聲的判定標準，避免抓到底噪
            no_speech_threshold=0.6,
        )

        base_name = os.path.splitext(input_file)[0]
        print(f"偵測到語言: {info.language} (信心度: {info.language_probability})")
        
        with ExitStack() as stack:
            f_srt = None
            f_txt = None

            if "srt" in output_formats or "all" in output_formats:
                f_srt = stack.enter_context(
                    open(f"{base_name}.srt", "w", encoding="utf-8")
                )

            if "txt" in output_formats or "all" in output_formats:
                f_txt = stack.enter_context(
                    open(f"{base_name}.txt", "w", encoding="utf-8")
                )

            srt_index = 1

            for segment in segments:
                start = segment.start
                end = segment.end
                text = segment.text.strip()

                if not text:
                    continue

                blocks = build_subtitle_blocks(
                    text,
                    max_line_len=max_line_len,
                    max_lines=2
                )

                duration = end - start
                per_block = duration / len(blocks)

                for i, block in enumerate(blocks):
                    s = start + i * per_block
                    e = s + per_block

                    if f_srt:
                        f_srt.write(f"{srt_index}\n")
                        f_srt.write(
                            f"{format_timestamp(s)} --> {format_timestamp(e)}\n"
                        )
                        f_srt.write(f"{block}\n\n")

                    if f_txt:
                        f_txt.write(block.replace("\n", " ") + "\n")

                    print(f"[{format_timestamp(s)} -> {format_timestamp(e)}]")
                    print(block)

                    srt_index += 1

        print(f"--- 處理完成 ({info.language}, {info.language_probability:.2f}) ---")

    except Exception as e:
        print(f"Faster-Whisper 錯誤: {e}")

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/run")
async def run_cutter(
    input_file: str = Form(...),
    srt_file: str = Form(None),
    output_file: str = Form(None),
    highpass: int = Form(80),
    lowpass: int = Form(8000),
    afftdn: int = Form(12),
    aecho: str = Form("0.8:0.3:40:0.2"),
    speechnorm_e: float = Form(4),
    speechnorm_p: float = Form(0.9)
):
    """
    執行 Video Cutter 的邏輯 (原本的功能)
    """
    # 構建指令
    cmd = ["python", "video_cutter.py", input_file]
    
    if srt_file:
        cmd.extend(["--srt", srt_file])
    
    if output_file:
        cmd.extend(["--output", output_file])
        
    # 音效參數
    if highpass > 0:
        cmd.extend(["--highpass", str(highpass)])
    else:
        cmd.extend(["--highpass", "0"]) # Explicitly turn off

    if lowpass > 0:
        cmd.extend(["--lowpass", str(lowpass)])
    else:
        cmd.extend(["--lowpass", "0"]) # Explicitly turn off
        
    if afftdn > 0:
        cmd.extend(["--afftdn", str(afftdn)])
        
    if aecho and aecho.lower() != "none" and aecho != "0":
        cmd.extend(["--aecho", aecho])
        
    cmd.extend(["--speechnorm-e", str(speechnorm_e)])
    cmd.extend(["--speechnorm-p", str(speechnorm_p)])

    # 為了演示，我們回傳指令字串，實際部署時可使用 subprocess.Popen 執行
    # process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    full_command = " ".join(shlex.quote(arg) for arg in cmd)
    
    # 這裡我們使用 subprocess 來真的執行 (但在背景執行，簡單示範)
    try:
        # 使用 Popen 非阻塞執行，或者用 run 阻塞執行
        # 為了 Web 回應速度，這裡演示用 run 並且不等待太久 (實際專案建議用 BackgroundTasks)
        # 這裡為了簡單，我們回傳指令給前端顯示，前端可以讓使用者手動貼上，
        # 或者在此處使用 subprocess.Popen(cmd) 真實執行。
        # 考慮到這是一個本地工具，我們直接執行它。
        subprocess.Popen(cmd)
        message = "後端已啟動剪輯程序 (PID active)。"
    except Exception as e:
        message = f"啟動失敗: {str(e)}"

    return JSONResponse({
        "status": "success",
        "command": full_command,
        "message": message
    })

@app.post("/extract-audio")
async def extract_audio(input_video: str = Form(...)):
    """
    呼叫 FFmpeg 將影片轉為單聲道、16kHz 的 MP3
    """
    if not os.path.exists(input_video):
        return JSONResponse({"status": "error", "message": "找不到輸入影片檔案"})

    # 自動產生輸出檔名： input.mp4 -> input.mp3
    base_name = os.path.splitext(input_video)[0]
    output_mp3 = base_name + ".mp3"

    # FFmpeg 指令: -ar 16000 -ac 1 -ab 16k
    # -y 表示覆蓋輸出檔
    cmd = [
        "ffmpeg", "-y", "-i", input_video,
        "-ar", "16000",
        "-ac", "1",
        "-ab", "16k",
        "-af", "highpass=f=180,lowpass=f=4000,speechnorm=e=4:p=0.9",
        output_mp3
    ]
    
    full_command = " ".join(shlex.quote(arg) for arg in cmd)

    try:
        # 使用 subprocess.run 等待執行完成
        subprocess.run(cmd, check=True)
        return JSONResponse({
            "status": "success",
            "output_path": output_mp3,
            "command": full_command,
            "message": f"轉檔成功！已輸出至: {output_mp3}"
        })
    except subprocess.CalledProcessError as e:
        return JSONResponse({"status": "error", "message": f"FFmpeg 執行錯誤: {e}"})
    except Exception as e:
        return JSONResponse({"status": "error", "message": f"未知錯誤: {e}"})

@app.post("/run-whisper")
async def run_whisper(
    background_tasks: BackgroundTasks,  # 注入 BackgroundTasks
    input_mp3: str = Form(...),
    language: str = Form("zh"),
    model: str = Form("base"),
    device: str = Form("cpu"),
    output_formats: str = Form(...) 
):
    """
    呼叫 Faster-Whisper 進行高效能辨識
    """
    if not os.path.exists(input_mp3):
        return JSONResponse({"status": "error", "message": "找不到輸入音訊檔案"})

    # 處理格式字串 "srt,txt" -> ["srt", "txt"]
    formats_list = output_formats.split(',')

    # 將耗時任務加入 BackgroundTasks
    # 這樣 API 會立刻回傳 success，而轉檔會在後台繼續跑
    background_tasks.add_task(
        run_faster_whisper_task, 
        input_mp3, 
        language, 
        model, 
        device, 
        formats_list
    )

    return JSONResponse({
        "status": "success",
        "message": f"Faster-Whisper 已在背景啟動。\n檔案: {input_mp3}\n模型: {model}\n裝置: {device}\n(請查看後端 Console 監控進度)"
    })


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)