import os
import argparse
from pathlib import Path
from huggingface_hub import snapshot_download

def download_model(model_id: str):
    models_dir = Path("models").absolute()
    models_dir.mkdir(exist_ok=True)
    
    model_folder_name = model_id.split("/")[-1]
    local_model_path = models_dir / model_folder_name
    
    print(f"--- Downloading {model_id} to {local_model_path} ---")
    try:
        snapshot_download(
            repo_id=model_id, 
            local_dir=local_model_path,
            local_dir_use_symlinks=False
        )
        print(f"\nSUCCESS: Model downloaded to {local_model_path}")
    except Exception as e:
        print(f"\nERROR downloading model: {e}")

if __name__ == "__main__":
    MODELS = {
        "tiny": "mlx-community/whisper-tiny",
        "base": "mlx-community/whisper-base",
        "small": "mlx-community/whisper-small",
        "distil-large-v3": "mlx-community/distil-whisper-large-v3",
        "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
        "large-v3-turbo-4bit": "mlx-community/whisper-large-v3-turbo-4bit"
    }
    
    parser = argparse.ArgumentParser(description="Download Whisper models locally for CC Generator")
    parser.add_argument(
        "model", 
        choices=list(MODELS.keys()) + ["all"], 
        default="large-v3-turbo", 
        nargs="?",
        help="The model size to download (default: large-v3-turbo)"
    )
    
    args = parser.parse_args()
    
    if args.model == "all":
        for mid in MODELS.values():
            download_model(mid)
    else:
        download_model(MODELS[args.model])
