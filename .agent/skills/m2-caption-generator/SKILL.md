---
name: m2-caption-generator
description: Generates .srt captions locally on Apple Silicon (M1/M2/M3) using MLX-Whisper. Use this when the user asks to "transcribe", "subtitle", or "create captions" for video files.
---

# Goal
To generate timestamped `.srt` subtitles for video/audio files locally on Apple Silicon hardware without using cloud APIs or heavy PyTorch dependencies.

# Instructions
When the user requests video transcription or caption generation, follow these steps:

1.  **Environment Check:**
    * Verify the system is Apple Silicon (M1/M2/M3).
    * Ensure `ffmpeg` is available (via `which ffmpeg`).
    * Ensure `mlx-whisper` is installed.

2.  **Code Generation Strategy:**
    * **Import:** Use `import mlx_whisper`.
    * **Threading:** ALWAYS wrap the inference/transcription call in a background thread (using `threading.Thread`) to prevent the GUI from freezing.
    * **Model Selection:** Default to `mlx-community/whisper-large-v3-turbo` for the best balance of speed and accuracy on M2.
    * **Output:** The generated file must be saved as `.srt` with the standard timestamp format `HH:MM:SS,mmm`.

3.  **UI Requirements (tkinter):**
    * Create a "Select File" button (supports .mp4, .mov, .mp3, .wav).
    * Create a "Model" dropdown (Tiny, Base, Small, Large-V3-Turbo).
    * Display a real-time status label ("Loading...", "Processing...", "Done").

# Constraints
* DO NOT use standard `openai-whisper` (too slow/RAM heavy for this use case).
* DO NOT use `torch` or `cuda` libraries.
* DO NOT hardcode paths; use `os.path` for cross-platform compatibility.

# Examples
User: "Make an app to subtitle my videos."
Action: Generate a Python script using `fastapi` and `mlx_whisper.transcribe(video_path)`.