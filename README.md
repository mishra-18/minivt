# OpenVT

Open-source 2D VTuber renderer built from scratch — no Live2D, no game engine.
Layered PNGs → triangle meshes → face tracking → real-time deformation.

### Web GPU Demo (browser version)
https://github.com/user-attachments/assets/aaca2a62-3cac-41ce-8538-69679d095d69

### CPU Demo
https://github.com/user-attachments/assets/2df3d217-6430-433f-8f9e-6f95fba26d23


https://github.com/user-attachments/assets/aecb9d38-0b5e-4c22-96da-9e355e940fda



## Run

```bash
python serve.py     # browser version → http://localhost:8000/web/
python main.py      # desktop version (pip install -r requirements.txt)
```

Click **enable camera**. No webcam? Cursor mode works: move mouse = head,
left-click = mouth, right-click = blink.

## Controls

`Tab` select param · `↑↓` adjust · `C` calibrate · `M` mirror · `P` physics · `H` panel · `R` reset

## How it works

```
webcam → MediaPipe → parameters → spring physics → mesh deformation → renderer
```

- **Parameters** are the core abstraction. Trackers write named floats (`headX`, `mouthOpen`); nothing downstream knows where they came from.
- **Meshes** — each PNG is subdivided into a triangle grid, transparent cells discarded.
- **Deformation** is data, not code: `transform` bindings move node hierarchies, `morph` bindings blend per-vertex offsets.
- **Physics** — damped springs run on parameters, so hair trails behind head motion.
- **Shaders** are minimal by design (animation stays CPU-side, debuggable): the vertex shader projects pre-deformed positions; the fragment shader samples texture, applies tint/mask, and outputs **premultiplied alpha** — the reason transparency and blend modes composite without edge halos.

## If you wanna use a custom model Custom model

```
models/<name>/model.json + textures/*.png
python main.py --model models/<name>
python tools/import_psd.py character.psd models/<name>   # from a layered PSD
```

## OBS

Browser source → `http://localhost:8000/web/` — transparent, no chroma key needed.

## Stack

WebGL2 / OpenGL 3.3 · MediaPipe Face Landmarker · NumPy · no rendering libraries.
