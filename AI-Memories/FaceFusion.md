# FaceFusion Project Reference

**Date Created:** 2026-08-08  
**Last Updated:** 2026-08-08  
**Status:** Active Project  

---


## 📁 Project Location

| Item | Path |
|------|------|
| **Primary** | `D:/MyWorld-Sync/011-AI/FaceFusion` |
| **Original** | `D:/Softwares/FaceFusion` (moved) |

---


## 🐍 Virtual Environment

- **Working venv:** `./venv_311/` — Python 3.11.9, 147 packages installed
- **Python Path:** `D:/MyWorld-Sync/011-AI/FaceFusion/venv_311/Scripts/python.exe`
- ⚠️ **CRITICAL:** Always use FaceFusion's venv (venv_311), NOT Hermes agent's venv. The Hermes venv lacks OpenCV and other dependencies required by FaceFusion.
- ❌ `./venv/` (Python 3.14) was deleted — it was empty with zero packages installed, just dead weight (~766 MB).

---


## 🧠 Models Location

- **External path:** `D:\AI-Models\FaceFusionModels\models\`
- **Symlink:** `.assets/models/` → points to external models folder
- ⚠️ Symlink excluded from Mega sync via `.megaignore` rule (`-dpg:011-AI/FaceFusion/.assets/models`)
- Model format: `.dfm` (deep swapper) and `.onnx` files with corresponding `.hash` files

---


## 🎬 Main Entry Point

- **File:** `facefusion.py`
- **Mode:** Headless-run (CLI automation, no GUI)
- **Configuration:** Via `state_manager` and CLI arguments

---


## 🧠 Available Processors

| Processor | Description |
|-----------|-------------|
| `deep_swapper` | AI deep face swapping |
| `face_swapper` | Standard face swap |
| `face_editor` | Face editing tools |
| `age_modifier` | Age up/down faces |
| `expression_restorer` | Restore facial expressions |
| `face_enhancer` | Enhance face quality |
| `frame_colorizer` | Colorize black & white frames |
| `lip_syncer` | Sync lip movements to audio |
| `background_remover` | Remove backgrounds |
| `face_debugger` | Debugging tools |

---


## 📦 Model Storage

**Base Path:** `.assets/models/` (symlinked from external drive)

### Available Model Categories:
- `iperov/` — Deep swap models
- Root-level `.onnx` files — face detector, landmarker, classifier, masker, enhancer, swapper models

### File Format:
- `.dfm` files (deep swapper model data)
- `.onnx` files (face detection, enhancement, swapping models)
- Corresponding `.hash` files (integrity verification)

---


## 🛠️ Batch Scripts (Root Directory)

| Script | Purpose |
|--------|---------|
| `run_prep_source.bat` | Prepare source images |
| `run_swap.bat` | Run face swap operations |
| `run_identity.bat` | Identity-based processing |

These scripts properly activate the venv before running Python.

---


## 📋 Job Naming Convention

When FaceFusion processes jobs, it creates folders named:

```
[source_folder_name] - [job_title] - [full_name]
```

**Example:** `پهپاد - امیر دریادار - دانا`

### Multi-Target Processing:
When given **ONE source + MULTIPLE targets**, each target is processed separately with sequential numbered subfolders:
- `sweep-01/`
- `sweep-02/`
- etc.

---


## ⚙️ Configuration

- Uses `state_manager` for settings persistence
- CLI arguments override config values
- Jobs system available for batch processing
- Config file: `facefusion.ini` (empty defaults — all set via CLI args)

---


## 🖥️ Hardware Notes

- **GPU:** RTX 4060 (16GB VRAM)
- **RAM:** 16GB
- **Location:** Iran (HuggingFace throttled, uses hf-mirror/X or IDM for large downloads >250MB)

---


## 📝 Usage Notes

1. Always activate FaceFusion's venv_311 before running any Python scripts
2. Large models (>250MB) like `elon_musk_224.onnx` (685MB) need manual download via IDM
3. Headless mode is used for all automation — no GUI interaction needed
4. Jobs can be batched using the jobs system
5. Models are stored externally at `D:\AI-Models\FaceFusionModels\models\`, symlinked into `.assets/models/`

---


## 🔗 Related Sessions

- **Source & Target Image Workflow:** @session:default/20260808_012113_42a8c7
