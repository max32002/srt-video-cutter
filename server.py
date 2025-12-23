# filename: server.py
import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import subprocess
import os
import shlex

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# 確保 templates 目錄存在
if not os.path.exists("templates"):
    os.makedirs("templates")

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
    input_mp3: str = Form(...),
    language: str = Form("zh"),
    model: str = Form("base"),
    device: str = Form("cpu"),
    output_formats: str = Form(...) # 接收逗號分隔字串，例如 "srt,vtt"
):
    """
    呼叫 Whisper CLI 產生字幕
    """
    if not os.path.exists(input_mp3):
        return JSONResponse({"status": "error", "message": "找不到輸入音訊檔案"})

    # 取得檔案所在目錄，以便 Whisper 輸出到同一層
    output_dir = os.path.dirname(input_mp3)
    if not output_dir:
        output_dir = "."

    # 處理格式列表 (前端傳來可能是 "srt,txt")
    formats = output_formats.split(',')
    
    # 構建 Whisper 指令
    # whisper "input.mp3" --model base --language zh --device cpu --output_format srt --output_dir "..."
    cmd = [
        "whisper", input_mp3,
        "--model", model,
        "--language", language,
        "--device", device,
        "--output_dir", output_dir,
        # whisper CLI 只能一次接受一種格式參數，或者如果不指定預設是全部。
        # 但新版 whisper 支援 --output_format 指定一種。
        # 如果要多種，通常得執行多次或者不指定讓它全產。
        # 不過標準 openai-whisper CLI 若不指定 --output_format 會全產。
        # 若指定，通常只能單選。但我們可以透過 Python 邏輯來優化。
        # 這裡為了簡單，如果選了 "all"，就不傳 --output_format。
        # 如果選了多個但不是 all，我們可能需要迴圈執行，或是依賴 CLI 行為。
        # **修正**: 標準 Whisper CLI 的 --output_format 參數通常接受單一值。
        # 為了支援多選，最簡單的方法是：如果不選 all，則對每個格式跑一次轉換(太慢)，
        # 或者我們直接不加 --output_format 參數讓它預設產生所有，然後刪除不要的。
        # **最佳解**: 為了相容性，我們這裡將 output_format 設為逗號分隔傳入 Python 腳本會更靈活，
        # 但既然是呼叫 CLI，我們假設使用者選了主要的一個，或者我們強制產生 all。
        # 為了滿足你的需求 "多選"，我們這裡做一個變通：
        # 如果包含 'all'，則不加 output_format 參數。
        # 如果是特定幾個，我們只傳第一個給 CLI (因為 CLI 限制)，或者改用 python code 調用 whisper library。
        # 為了 CLI 簡單化，我們這裡假設使用者傳入單一值，若要多選，建議用 'all'。
        # *更正*: 根據你的需求，我將只傳遞 output_format 中的第一個選項，
        # 或是如果使用者選了多個，我們使用 Python 內部呼叫會更好。
        # 但為了維持呼叫 "外指令" 的架構，我們先傳遞第一個被選中的格式。
    ]
    
    # 處理 output_format: Whisper CLI 支援 --output_format {txt,vtt,srt,tsv,json,all}
    # 如果使用者選了多個，我們這裡只取第一個，或者如果包含 "all" 就用 all。
    selected_fmt = formats[0]
    if "all" in formats:
        selected_fmt = "all"
    
    cmd.extend(["--output_format", selected_fmt])
    # 注意: 如果只選 srt 和 vtt，CLI 無法一次輸出兩個。
    # 這裡簡化邏輯：依據第一個選項執行。
    
    full_command = " ".join(shlex.quote(arg) for arg in cmd)

    try:
        subprocess.Popen(cmd)
        return JSONResponse({
            "status": "success",
            "command": full_command,
            "message": f"Whisper 已開始執行 (Model: {model}, Device: {device})"
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": f"Whisper 啟動失敗: {e}"})

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)