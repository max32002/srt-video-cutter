# 🎬 SRT Video Cutter

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-Powered-red?logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**SRT Video Cutter** 是一個現代化的影片自動剪輯與後製工具。它解決了創作者最繁瑣的工作流程：根據 SRT 字幕的時間軸自動切分影片，移除無聲片段，並透過 FFmpeg 的濾鏡鏈 (Filter Chain) 自動優化音質（降噪、人聲增強、空間感營造）。

本專案內建了一個具備 **Cyberpunk 風格的 Web UI**，讓你不必記憶複雜的指令，即可透過圖形介面一鍵處理影片。

---

## ✨ 核心功能 (Key Features)

* **✂️ 智慧剪輯 (Smart Cutting)**：
    * 解析 SRT 字幕檔，精準提取有對白的片段。
    * 自動合併間隔過短的片段，避免影片產生破碎感。
    * **靜音偵測**：雙重驗證，確保剪輯出來的片段不會包含長時間的無聲畫面。
* **🎛️ 專業音訊工程 (Audio Engineering)**：
    * **Highpass Filter**：消除低頻轟鳴聲（如冷氣運作聲、風切聲）。
    * **FFT Denoise**：基於頻譜的背景降噪算法。
    * **Auto Echo**：為過乾的錄音室人聲添加微量延遲與殘響，提升聽感自然度。
    * **Speech Normalization**：動態調整人聲音量，確保整體響度一致。
* **🎛️ 整合外部 whisper 指令 **：
    * **轉檔**：來源檔案轉換為單聲道 MP3 (16kHz)。
    * **生成字幕**：圖形化介面設定常用參數。
* **💻 現代化介面 (Web Interface)**：
    * 基於 **FastAPI** 構建的高效後端。
    * 支援 **深色 (Dark)** / **淺色 (Light)** 主題切換。
    * **情境預設 (Presets)**：內建「教學」、「Vlog」、「純降噪」等參數模組。
* **🚀 雙模式執行**：同時支援 Web UI 操作與 CLI (Command Line) 自動化腳本。

---

## 📥 下載與安裝 (Installation)

### 1. 環境需求 (Prerequisites)

在開始之前，請確保您的系統已安裝以下軟體：

* **Python 3.8+**
* **FFmpeg** (⚠️ 重要)
    * **Windows**: 下載編譯好的執行檔，並將 `bin` 資料夾路徑加入系統環境變數 (System PATH)。
    * **Mac**: ```bash brew install ffmpeg```
    * **Linux**: ```bash sudo apt install ffmpeg```
* **Whisper**
    * 請確保你的電腦環境已經安裝了 openai-whisper: ```pip install openai-whisper```

    (注意：Whisper 需要 PyTorch，如果你有 NVIDIA 顯卡並希望使用 GPU 加速，請務必安裝對應 CUDA 版本的 PyTorch)

### 2. 下載專案 (Clone Project)

開啟終端機 (Terminal) 或命令提示字元 (CMD)，執行以下指令：

```bash
# 下載專案代碼
git clone https://github.com/max32002/srt-video-cutter.git

# 進入專案目錄
cd srt-video-cutter
```

### 3. 安裝依賴套件 (Install Dependencies)

建議建立虛擬環境 (Virtual Environment) 以保持系統整潔：

```bash
# [選用] 建立虛擬環境
python -m venv venv

# [選用] 啟動虛擬環境 (Windows)
.\venv\Scripts\activate
# [選用] 啟動虛擬環境 (Mac/Linux)
source venv/bin/activate
```

安裝必要的 Python 套件：

```bash
pip install -r requirements.txt
```

若無 `requirements.txt`，請手動安裝：
```bash
pip install fastapi uvicorn python-multipart jinja2 ffmpeg-python pysrt
```

---

## 📂 專案結構 (Project Structure)

了解檔案結構有助於你進行維護或修改：

```text
ai-video-cutter/
├── clip_cutter.py         # 核心邏輯：負責呼叫 FFmpeg 進行剪輯與音效處理
├── server.py              # 後端服務：FastAPI 伺服器，處理網頁請求
├── requirements.txt       # 套件清單
├── README.md              # 專案說明文件
└── templates/             # 前端頁面資料夾
    └── index.html         # Web UI 介面 (HTML/Tailwind CSS/JS)
└── static/                # 前端頁面靜態資源資料夾
    ├── app.js             # javascript
    └── style.css          # css
```

---

## 🚀 使用方法 (Usage)

### 方法一：圖形化介面 (Web UI) - 推薦 ⭐

這是最直覺的使用方式，適合一般創作者。

1.  **啟動伺服器**：
    在終端機執行：
    ```bash
    python server.py
    ```
    當看到 `Uvicorn running on http://127.0.0.1:8000` 字樣時表示啟動成功。

2.  **開啟瀏覽器**：
    訪問網址：[http://127.0.0.1:8000](http://127.0.0.1:8000)

3.  **操作步驟**：
    * **影片路徑**：輸入電腦中的完整檔案路徑（例如：`C:/Projects/Video/raw.mp4`）。
    * **參數設定**：可以直接調整數值，或點擊右側的 **「⚡ 快速情境」** 按鈕載入預設值。
    * **執行**：點擊 **「🚀 EXECUTE CUTTER」**。
    * **監控**：下方的控制台 (Console) 視窗會顯示執行指令與狀態。

### 方法二：命令列模式 (CLI) - 進階

適合工程師或需要批次處理大量檔案的場景。

```bash
python clip_cutter.py "input_video.mp4" [參數...]
```

**範例指令：**
```bash
python clip_cutter.py "video.mp4" --srt "subs.srt" --highpass 100 --afftdn 15 --aecho "0.8:0.3:40:0.2"
```

---

## 🎛️ 音效情境建議 (Audio Presets)

本工具最強大的功能在於其音訊處理鏈 (Audio Chain)。不確定參數怎麼填？請參考下表：

| 情境模式 (Preset) | 適用場景 | 參數解析與建議 |
| :--- | :--- | :--- |
| **🎤 人聲偏乾 (Dry Vocal)** | 錄音室環境吸音太強，聲音聽起來像貼在耳朵旁，缺乏空間感。 | **重點：增加 Echo**<br>增加 `aecho` 的延遲 (Delay) 與衰減 (Decay)，製造微量的房間殘響，讓聲音聽起來更自然、不壓迫。 |
| **📚 教學影片 (Tutorial)** | YouTube 教學、線上課程。需要聲音極度清晰，去除雜訊。 | **重點：清晰度**<br>`Highpass` 設為 100Hz 濾掉冷氣聲；`Afftdn` 開啟適度降噪；Echo 保持微量以潤飾剪輯點。 |
| **🥁 音樂重低音 (Bass)** | 影片包含背景音樂 (BGM) 或音效，需要保留低頻震撼感。 | **重點：保留低頻**<br>將 `Highpass` 降至 20Hz 或關閉，避免濾掉大鼓或低音貝斯的頻率。 |
| **🔇 只進行降噪 (Denoise Only)** | 已經有很好的錄音環境，只需去除底噪，不需要其他渲染。 | **重點：純淨**<br>關閉 `Highpass`、`Echo` 與 `Norm`，將 `Afftdn` (降噪) 設為 15dB 或更高。 |
| **🚫 關閉 Echo (No Echo)** | 在空曠房間錄音，原始素材已經有很重的回音。 | **重點：去殘響**<br>強制關閉 `aecho`，避免回音疊加導致聲音模糊，但保留降噪與音量標準化。 |
| **🛑 完全關閉 (Raw Cut)** | 只需要利用 SRT 剪輯畫面，音訊已在其他軟體處理過。 | **重點：Bypass**<br>所有音效參數設為 0 或 None，僅進行視訊與音訊的裁切合併。 |

---

## ⚙️ 參數技術詳解 (Technical Details)

如果你想手動微調，這裡解釋各參數對應的 FFmpeg 濾鏡原理：

* **Highpass Freq (Hz)**: 高通濾波器。低於此頻率的聲音會被削減。
    * *建議值*：人聲處理通常設在 `80-100` Hz (濾除風切、電流聲)。
* **FFT Denoise (dB)**: 基於快速傅立葉變換的降噪強度。
    * *建議值*：`5-15` dB。數值過大會導致聲音產生「水下音」失真。
* **Echo (In:Out:Delay:Decay)**: 
    * `In/Out`: 原始聲音與回音的音量比例 (0.0-1.0)。
    * `Delay`: 延遲時間 (毫秒)。
    * `Decay`: 衰減係數。
* **Speech Norm (e/p)**: 
    * `e (expansion)`: 擴展係數，數值越高動態範圍越大。
    * `p (compression)`: 壓縮係數，數值越高聲音越緊實響亮。

---

## ⚠️ 注意事項與常見問題 (FAQ)

1.  **Media type mismatch 錯誤**：
    * 這通常發生在 FFmpeg filter 串接時輸入輸出軌道對不上。本專案已在 `clip_cutter.py` 中透過 `joined[0]` (Video) 與 `joined[1]` (Audio) 明確指定軌道修復此問題。

2.  **找不到影片或路徑錯誤**：
    * 請盡量使用 **絕對路徑** (如 `C:/Users/Name/Video.mp4`)。
    * 路徑中避免包含特殊符號或過長的中文，這可能導致 FFmpeg 解析失敗。

3.  **執行速度慢**：
    * 這是正常的。因為程式不僅是「剪輯」，還進行了「重新編碼 (Re-encoding)」以套用降噪與 EQ 濾鏡。速度取決於您的 CPU 核心數與影片解析度。

4.  **字幕不同步**：
    * 請確保 SRT 字幕的編碼為 `UTF-8`。
    * 若剪輯結果有偏差，可調整 `padding` (緩衝時間) 參數，預設為 `0.15` 秒。

---

## 📄 License

本專案採用 **MIT License** 開源授權。
