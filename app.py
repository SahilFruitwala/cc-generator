import os
import shutil
import asyncio
import time
from typing import Dict, List
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from huggingface_hub import snapshot_download
import mlx_whisper

app = FastAPI()

# In-memory status storage: maps task_id to a list of log messages
transcription_logs: Dict[str, List[str]] = {}
transcription_progress: Dict[str, float] = {} # 0 to 100
transcription_results: Dict[str, List[Dict]] = {} # Maps task_id to segment list

MODELS_METADATA = {
    "tiny": {
        "id": "mlx-community/whisper-tiny",
        "name": "Whisper Tiny",
        "description": "Fastest model, low accuracy. Best for quick tests.",
        "min_ram": "1GB",
        "speed": "Ultra",
        "accuracy": "Low"
    },
    "base": {
        "id": "mlx-community/whisper-base",
        "name": "Whisper Base",
        "description": "Balanced speed and accuracy for simple audio.",
        "min_ram": "1.5GB",
        "speed": "Very Fast",
        "accuracy": "Fair"
    },
    "small": {
        "id": "mlx-community/whisper-small",
        "name": "Whisper Small",
        "description": "Great balance for most everyday content.",
        "min_ram": "3GB",
        "speed": "Fast",
        "accuracy": "Good"
    },
    "distil-large-v3": {
        "id": "mlx-community/distil-whisper-large-v3",
        "name": "Distil-Large-v3",
        "description": "Compressed large model. High quality with extreme speed.",
        "min_ram": "6GB",
        "speed": "Very Fast",
        "accuracy": "High"
    },
    "large-v3-turbo": {
        "id": "mlx-community/whisper-large-v3-turbo",
        "name": "Whisper Large-v3-Turbo",
        "description": "Optimized version of Large-v3. Recommended for M2 Air.",
        "min_ram": "6GB",
        "speed": "Fast",
        "accuracy": "High"
    },
    "large-v3-turbo-4bit": {
        "id": "mlx-community/whisper-large-v3-turbo-4bit",
        "name": "Whisper Large-v3-Turbo (4-bit)",
        "description": "Memory efficient version. Best for heavy loads on M2 Air.",
        "min_ram": "4GB",
        "speed": "Fast",
        "accuracy": "High"
    }
}

def format_timestamp(seconds):
    """Converts seconds to HH:MM:SS,mmm format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def write_srt(segments, output_path):
    """Writes transcription segments to an SRT file using smart chunking."""
    
    # Constants for smart chunking
    MAX_CHARS = 42
    MAX_WORDS = 8
    PAUSE_THRESHOLD = 0.5  # seconds

    # Flatten all words from all segments into a single stream for continuous processing
    all_words = []
    for segment in segments:
        if "words" in segment:
            all_words.extend(segment["words"])
    
    with open(output_path, "w", encoding="utf-8") as f:
        caption_counter = 1
        
        # Fallback to segment-based if no word timestamps found
        if not all_words:
            for i, segment in enumerate(segments, start=1):
                start = format_timestamp(segment["start"])
                end = format_timestamp(segment["end"])
                text = segment["text"].strip()
                f.write(f"{i}\n{start} --> {end}\n{text}\n\n")
            return

        current_chunk = []
        
        for i, word_info in enumerate(all_words):
            current_chunk.append(word_info)
            should_break = False
            
            # 1. Check for natural pause (look ahead to next word)
            if i < len(all_words) - 1:
                next_word = all_words[i+1]
                if next_word["start"] - word_info["end"] > PAUSE_THRESHOLD:
                    should_break = True
            
            # 2. Check for punctuation
            word_text = word_info["word"].strip()
            if word_text and word_text[-1] in ".?!":
                should_break = True
                
            # 3. Check for max length (character count)
            current_text = "".join([w["word"] for w in current_chunk]).strip()
            if len(current_text) > MAX_CHARS:
                should_break = True
                
            # 4. Check for max words
            if len(current_chunk) >= MAX_WORDS:
                should_break = True
            
            if should_break and current_chunk:
                start_time = current_chunk[0]["start"]
                end_time = current_chunk[-1]["end"]
                text = "".join([w["word"] for w in current_chunk]).strip()
                
                f.write(f"{caption_counter}\n")
                f.write(f"{format_timestamp(start_time)} --> {format_timestamp(end_time)}\n")
                f.write(f"{text}\n\n")
                caption_counter += 1
                current_chunk = []
        
        # Flush remaining words in buffer
        if current_chunk:
            start_time = current_chunk[0]["start"]
            end_time = current_chunk[-1]["end"]
            text = "".join([w["word"] for w in current_chunk]).strip()
            f.write(f"{caption_counter}\n")
            f.write(f"{format_timestamp(start_time)} --> {format_timestamp(end_time)}\n")
            f.write(f"{text}\n\n")

def add_log(task_id: str, message: str):
    timestamp = time.strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    if task_id not in transcription_logs:
        transcription_logs[task_id] = []
    transcription_logs[task_id].append(log_entry)
    print(f"TASK {task_id}: {message}")

def run_transcription_task(file_path: str, model_id: str, task_id: str):
    try:
        add_log(task_id, f"Initializing transcription with model: {model_id}")
        transcription_progress[task_id] = 5
        
        # Local model directory storage logic
        models_dir = Path("models").absolute()
        models_dir.mkdir(exist_ok=True)
        
        # Extract model folder name
        model_folder_name = model_id.split("/")[-1]
        local_model_path = models_dir / model_folder_name
        
        if not local_model_path.exists() or not any(local_model_path.iterdir()):
            add_log(task_id, f"Model not found in {local_model_path}. Starting download from Hugging Face...")
            add_log(task_id, "This may take a while depending on your internet speed (Large models are ~1.6GB).")
            transcription_progress[task_id] = 10
            
            try:
                # Download to local directory
                snapshot_download(
                    repo_id=model_id, 
                    local_dir=local_model_path,
                    local_dir_use_symlinks=False
                )
                add_log(task_id, "Download complete!")
            except Exception as download_error:
                add_log(task_id, f"Download failed: {str(download_error)}. Attempting to use default cache...")
                # If download fails, we let it try the default behavior
        else:
            add_log(task_id, f"Using local model found at: {local_model_path}")

        transcription_progress[task_id] = 20
        add_log(task_id, "Loading model into memory... (M2 Optimized)")
        add_log(task_id, "TIP: Initial load may be slow. Subsequent calls will be faster.")
        
        output_path = os.path.splitext(file_path)[0] + ".srt"
        transcription_progress[task_id] = 30
        
        add_log(task_id, "Model loaded. Starting inference on Apple Silicon GPU...")
        # Point mlx_whisper to the local model folder, enable word timestamps for granular sync
        result = mlx_whisper.transcribe(
            file_path, 
            path_or_hf_repo=str(local_model_path),
            word_timestamps=True
        )
        transcription_progress[task_id] = 80
        
        add_log(task_id, "Inference complete. Formatting SRT file...")
        write_srt(result["segments"], output_path)
        transcription_progress[task_id] = 100
        
        add_log(task_id, f"SUCCESS: Generated {os.path.basename(output_path)}")
        transcription_results[task_id] = result["segments"]
        
        # Auto-cleanup: Delete the original uploaded file
        time.sleep(1) # Wait for file handles to release
        try:
            print(f"DEBUG: Attempting to delete {file_path}")
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"DEBUG: Successfully deleted {file_path}")
                add_log(task_id, f"Cleaned up source file: {os.path.basename(file_path)}")
            else:
                print(f"DEBUG: File not found for deletion: {file_path}")
        except Exception as cleanup_error:
            print(f"DEBUG: Deletion error: {cleanup_error}")
            add_log(task_id, f"WARNING: Failed to delete source file: {str(cleanup_error)}")

        add_log(task_id, "Done!")
        
    except BaseException as e:
        add_log(task_id, f"ERROR: {str(e)}")
        transcription_progress[task_id] = -1 # Indicate error
        # Re-raise if it's a critical system exit/interrupt, though usually we want to log it first
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise e

@app.post("/transcribe")
async def transcribe(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    model: str = Form(...)
):
    upload_dir = os.path.join(os.getcwd(), "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    task_id = f"{file.filename}_{int(time.time())}"
    transcription_logs[task_id] = []
    transcription_progress[task_id] = 0
    
    add_log(task_id, f"Received file: {file.filename}")
    background_tasks.add_task(run_transcription_task, file_path, model, task_id)
    
    return {"task_id": task_id, "message": "Transcription started"}

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    async def event_generator():
        sent_logs_count = 0
        while True:
            logs = transcription_logs.get(task_id, [])
            # Send only new logs
            if len(logs) > sent_logs_count:
                for i in range(sent_logs_count, len(logs)):
                    yield f"event: log\ndata: {logs[i]}\n\n"
                sent_logs_count = len(logs)
            
            progress = transcription_progress.get(task_id, 0)
            yield f"event: progress\ndata: {progress}\n\n"
            
            if "Done!" in (logs[-1] if logs else "") or "ERROR" in (logs[-1] if logs else ""):
                break
                
            await asyncio.sleep(0.5)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

def is_model_downloaded(model_key: str) -> bool:
    model_id = MODELS_METADATA[model_key]["id"]
    model_folder_name = model_id.split("/")[-1]
    local_model_path = Path("models").absolute() / model_folder_name
    return local_model_path.exists() and any(local_model_path.iterdir())

@app.get("/models")
async def list_models():
    models = []
    for key, meta in MODELS_METADATA.items():
        models.append({
            "key": key,
            **meta,
            "downloaded": is_model_downloaded(key)
        })
    return models

@app.post("/models/download/{model_key}")
async def download_model_ui(model_key: str, background_tasks: BackgroundTasks):
    if model_key not in MODELS_METADATA:
        return JSONResponse({"error": "Model not found"}, status_code=404)
    
    task_id = f"download_{model_key}_{int(time.time())}"
    transcription_logs[task_id] = []
    transcription_progress[task_id] = 0
    
    def run_download():
        try:
            model_id = MODELS_METADATA[model_key]["id"]
            models_dir = Path("models").absolute()
            models_dir.mkdir(exist_ok=True)
            model_folder_name = model_id.split("/")[-1]
            local_model_path = models_dir / model_folder_name
            
            add_log(task_id, f"Starting download of {model_id}...")
            transcription_progress[task_id] = 10
            
            snapshot_download(
                repo_id=model_id, 
                local_dir=local_model_path,
                local_dir_use_symlinks=False
            )
            
            transcription_progress[task_id] = 100
            add_log(task_id, f"Successfully downloaded {model_id}")
            add_log(task_id, "Done!")
        except Exception as e:
            add_log(task_id, f"ERROR: {str(e)}")
            transcription_progress[task_id] = -1

    background_tasks.add_task(run_download)
    return {"task_id": task_id, "message": "Download started"}

@app.post("/models/delete/{model_key}")
async def delete_model(model_key: str):
    if model_key not in MODELS_METADATA:
        return JSONResponse({"status": "error", "message": "Model not found"}, status_code=404)
    
    model_id = MODELS_METADATA[model_key]["id"]
    model_folder_name = model_id.split("/")[-1]
    local_model_path = Path("models") / model_folder_name
    
    try:
        if local_model_path.exists():
            shutil.rmtree(local_model_path)
            print(f"Deleted model directory: {local_model_path}")
            return {"status": "success", "message": f"Model {model_key} deleted"}
        else:
            return JSONResponse({"status": "error", "message": "Model files not found locally"}, status_code=404)
    except Exception as e:
        print(f"Error deleting model: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/results/{task_id}")
async def get_results(task_id: str):
    if task_id not in transcription_results:
        return JSONResponse({"error": "Results not found or task still in progress"}, status_code=404)
    return JSONResponse(transcription_results[task_id])

# Serve the static frontend
os.makedirs("static", exist_ok=True)
os.makedirs("uploads", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/uploads/{filename}")
async def download_file(filename: str, background_tasks: BackgroundTasks):
    file_path = os.path.join("uploads", filename)
    if not os.path.exists(file_path):
        return JSONResponse({"error": "File not found"}, status_code=404)
    
    def cleanup():
        try:
            print(f"DEBUG: Auto-deleting SRT file: {filename}")
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"ERROR: Failed to delete SRT: {e}")

    # Use BackgroundTasks to queue the cleanup after the response is sent
    background_tasks.add_task(cleanup)
    
    return FileResponse(file_path, filename=filename, media_type="application/x-subrip")

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
