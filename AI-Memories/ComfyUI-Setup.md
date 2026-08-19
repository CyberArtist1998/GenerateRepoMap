# ComfyUI Setup Guide

## Environment Details
- **GPU:** NVIDIA GeForce RTX 4060 Ti (8GB VRAM)
- **Python Version:** 3.12.13 (required for CUDA compatibility)
- **PyTorch:** 2.6.0+cu124 (CUDA-enabled)
- **ComfyUI Version:** 0.28.0

## Installation Steps

### 1. Create Python 3.12 Virtual Environment
```bash
# Use uv to create venv with Python 3.12 (CUDA wheels only available for cp312)
uv venv .venv --python C:\Users\RedRain2077\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe
```

### 2. Install CUDA-Compatible PyTorch Wheels (Manual Download via IDM)
Download from https://pytorch.org/get-started/locally/ and install:
```bash
pip install torch-2.6.0+cu124-cp312-cp312-win_amd64.whl
pip install torchvision-0.21.0+cu124-cp312-cp312-win_amd64.whl
pip install torchaudio-2.6.0+cu124-cp312-cp312-win_amd64.whl
```

### 3. Install ComfyUI Dependencies
```bash
cd D:\MyWorld-Sync\011-AI\ComfyUIDirectory\Main\ComfyUI\ComfyUI
pip install -r requirements.txt
```

**Key dependencies installed:**
- Core: numpy, scipy, Pillow, PyYAML, typing_extensions
- ML: transformers, tokenizers, sentencepiece, safetensors
- ComfyUI: comfyui-frontend-package, workflow-templates, aimdo, kitchen
- Custom nodes: opencv-python, scikit-image, ultralytics, matplotlib

### 4. Configure Model Paths
Edit `extra_model_paths.yaml` to point to model directory:
```yaml
# Set base_path to: D:\AI-Models\ComfyUIModels\models\
```

## Launch Command (IMPORTANT)

```bash
cd "D:\MyWorld-Sync\011-AI\ComfyUIDirectory\Main\ComfyUI\ComfyUI"
PYTHONPATH="" "./.venv/Scripts/python.exe" main.py --listen 127.0.0.1 --port 8188
```

**CRITICAL:** Always use `PYTHONPATH=""` to prevent environment contamination from Hermes Agent's venv!

## Known Issues & Workarounds

### Issue 1: Python 3.14 Incompatibility
- **Problem:** PyTorch CUDA wheels not available for Python 3.14
- **Solution:** Use Python 3.12 exclusively for ComfyUI

### Issue 2: Environment Contamination
- **Problem:** Hermes Agent's site-packages interfere with ComfyUI dependencies
- **Solution:** Always set `PYTHONPATH=""` before launching

### Issue 3: Network Connectivity (ComfyRegistry)
- **Problem:** Cannot connect to comfyregistry during startup
- **Symptom:** Server crashes with `InvalidChannel` error
- **Workaround:** Custom nodes disabled; core ComfyUI works fine without them

### Issue 4: Triton Module Missing
- **Problem:** No Windows wheel for Python 3.12
- **Impact:** Optional optimization module only - not required for operation

## Backup Location
Previous environment backed up at: `D:\MyWorld-Sync\011-AI\ComfyUIDirectory\Main\ComfyUI\ComfyUI_backup_20260808`

## Model Directory Structure
```
D:\AI-Models\ComfyUIModels\models\
├── checkpoints/
├── clip_vision/
├── diffusion_models/
├── loras/
├── vae/
└── ... (other subdirectories)
```

## Verification Commands

Check CUDA availability:
```python
import torch
print(torch.cuda.is_available())  # Should return True
print(torch.cuda.get_device_name(0))  # Should show RTX 4060 Ti
```
