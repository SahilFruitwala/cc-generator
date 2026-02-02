# CC Generator

A web-based tool to generate .srt captions for video files using Whisper.

## Features
- Upload video/audio files
- Automatic transcription using Whisper
- Download generated .srt files
- Local processing (privacy-focused)

## Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd cc-generator
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   (Note: Add a requirements.txt if not already present)
   ```bash
   pip install flask transformers torch torchaudio
   ```

4. **Download Models**
   ```bash
   python3 download_models.py
   ```

5. **Run the application**
   ```bash
   python3 app.py
   ```

## Technologies
- **Backend**: Python (Flask)
- **Frontend**: Vanilla HTML/CSS/JS
- **Transcription**: Whisper (HuggingFace Transformers)
