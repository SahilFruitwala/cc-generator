# AI Caption Generator (Apple Silicon Edition)

A high-performance tool that automatically creates subtitles for your videos. Optimized specifically for Mac computers with Apple Silicon chips (M1, M2, M3).

> **⚠️ Note:** This application is currently **tested on macOS only**. It leverage Apple Silicon's GPU/Neural Engine via the `mlx` framework.

## 🌟 What does this do?
*   **Drag & Drop** any video or audio file.
*   **Automatic AI Transcription:** Generates captions in seconds.
*   **Privacy First:** Everything runs **100% offline** on your Mac. No data is ever sent to the cloud.
*   **Space Saving:** Automatically cleans up large video files after processing.

---

## 🚀 How to Install (One-Time Setup)

Since this app runs locally on your Mac, you'll need to set it up once.

1.  **Open Terminal** (Command+Space, type "Terminal").

2.  **Download the Code**:
    ```bash
    git clone https://github.com/SahilFruitwala/cc-generator.git
    cd cc-generator
    ```

3.  **Create a Virtual Environment** (Keeps things clean!):
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

4.  **Install Dependencies**:
    ```bash
    python3 -m pip install -r requirements.txt
    ```
    *Wait for it to finish installing the AI tools (MLX Whisper, etc.).*

---

## ▶️ How to Use

1.  **Start the App**:
    In your terminal, run:
    ```bash
    python3 app.py
    ```
    *You should see a message saying:* `Server running at http://0.0.0.0:8000`

2.  **Open in Browser**:
    Open Chrome or Safari and go to:
    **[http://localhost:8000](http://localhost:8000)**

3.  **Generate Captions**:
    *   **Drag & Drop** your video or audio file into the box.
    *   (Optional) Select a model from the list. "Large v3 Turbo" is recommended for best accuracy.
    *   Click **"Generate Captions"**.

4.  **Download**:
    *   Watch the progress bar (it stays in a modal so you can't miss it!).
    *   Once finished, click the **"Download SRT"** button.
    *   *Your original video file is automatically deleted to save space.*

---

## 💡 Tips
*   **First Run might be slow:** The first time you pick a new model, it needs to download (1-3 GB). Future runs will be instant!
*   **"Auto-Download":** Keep this checked to let the app handle model downloads for you.
*   **Deleting Models:** If you need disk space, you can delete old models directly from the list by hovering over them and clicking "Delete".
