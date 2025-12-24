import os
import shutil
import shlex
import subprocess
import math
from typing import List

import uvicorn
from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from typing import List

from faster_whisper import WhisperModel

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

# --- 核心邏輯：使用 Faster-Whisper 執行辨識 ---
def run_faster_whisper_task(input_file: str, language: str, model_size: str, device: str, output_formats: List[str]):
    """
    背景執行的核心函數：
    1. 載入模型
    2. 使用 VAD 自動切分並辨識
    3. 即時寫入 SRT/TXT 檔案 (自動合併)
    """
    try:
        print(f"--- 開始處理: {input_file} (Device: {device}, Model: {model_size}) ---")
        
        # 決定計算類型 (GPU 用 float16, CPU 用 int8 以加速)
        compute_type = "float16" if device == "cuda" else "int8"
        
        # 1. 載入模型 (這只需要做一次，比切成實體小檔案反覆載入快得多)
        model = WhisperModel(model_size, device=device, compute_type=compute_type)

        # 2. 開始轉錄
        # vad_filter=True : 這就是「自動切檔」的關鍵，它會忽略靜音片段，只辨識人聲
        segments, info = model.transcribe(input_file, language=language, vad_filter=True)

        # 準備輸出檔名
        base_name = os.path.splitext(input_file)[0]
        srt_path = f"{base_name}.srt"
        txt_path = f"{base_name}.txt"
        
        # 開啟檔案準備寫入 (這裡演示同時輸出 srt 和 txt，如果需要)
        # 透過 with open 保持檔案開啟，逐行寫入，達成「自動合併」的效果
        
        print(f"偵測到語言: {info.language} (信心度: {info.language_probability})")
        
        with open(srt_path, "w", encoding="utf-8") as f_srt, \
             open(txt_path, "w", encoding="utf-8") as f_txt:
            
            for i, segment in enumerate(segments, start=1):
                # 處理時間戳
                start_time = format_timestamp(segment.start)
                end_time = format_timestamp(segment.end)
                text = segment.text.strip()
                
                # 寫入 SRT 格式
                if "srt" in output_formats or "all" in output_formats:
                    f_srt.write(f"{i}\n")
                    f_srt.write(f"{start_time} --> {end_time}\n")
                    f_srt.write(f"{text}\n\n")
                    # 強制刷新緩衝區，讓使用者能看到檔案變大
                    f_srt.flush() 

                # 寫入 TXT 格式
                if "txt" in output_formats or "all" in output_formats:
                    f_txt.write(f"{text}\n")
                    f_txt.flush()
                
                # 在 Console 顯示進度
                print(f"[{start_time} -> {end_time}] {text}")

        print(f"--- 處理完成: {srt_path} ---")

    except Exception as e:
        print(f"Faster-Whisper 執行錯誤: {e}")

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/run")
async def run_cutter(
    input_file: str = Form(...),
    srt_file: str = Form(None),
    output_file: str = Form(None),
    highpass: float = Form(80),
    afftdn: float = Form(12),
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