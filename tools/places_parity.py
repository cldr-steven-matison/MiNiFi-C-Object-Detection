#!/usr/bin/env python3
"""Tract parity check for ClassifyImage. For every JSON sidecar of a cut, rebuild the exact frame
ExtractVideoFrames sent (by `video.frame`, the source index: 1280 resize, pdr mask, JPEG 85), run Places365
under onnxruntime with ClassifyImage's preprocessing (RGB, stretch to 224, /255, ImageNet mean/std, CHW,
softmax), and compare with the sidecar's `scene` (Tract). The 224 resize is done twice: cv2 INTER_LINEAR
(no antialias) and PIL BILINEAR (antialiased, the torchvision/Places365 training path).
    python3 -I places_parity.py <model.onnx> <labels.txt> <meta_dir> <clip.mp4> [<clip.mp4> ...]
Run with models/.venv plus opencv-python-headless and pillow. Key on video.frame, not
the sample number: OpenCV 4.8 (the agent) and 5.0 report a different src fps, so the step differs."""
import glob
import json
import os
import sys
import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image

PDR = [(0.03, 0.02, 0.19, 0.22), (0.83, 0.02, 0.96, 0.22), (0.0, 0.76, 1.0, 1.0)]
MAX_W, Q = 1280, 85
MEAN, STD = np.array([0.485, 0.456, 0.406], np.float32), np.array([0.229, 0.224, 0.225], np.float32)

model, labels_path, meta = sys.argv[1:4]
with open(labels_path) as fh:
    labels = fh.read().splitlines()
sess = ort.InferenceSession(model, providers=["CPUExecutionProvider"])

def frame_at(path, wanted):
    cap, i, out = cv2.VideoCapture(path), -1, {}
    while cap.grab():
        i += 1
        if i > max(wanted):
            break
        if i not in wanted:
            continue
        _, f = cap.retrieve()
        if f.shape[1] > MAX_W:
            s = MAX_W / f.shape[1]
            f = cv2.resize(f, (MAX_W, int(f.shape[0] * s)), interpolation=cv2.INTER_AREA)
        h, w = f.shape[:2]
        for x0, y0, x1, y1 in PDR:
            f[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)] = 0
        jpeg = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, Q])[1]
        out[i] = cv2.cvtColor(cv2.imdecode(jpeg, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    return out

def classify(rgb224):
    x = ((rgb224.astype(np.float32) / 255.0 - MEAN) / STD).transpose(2, 0, 1)[None]
    z = sess.run(None, {sess.get_inputs()[0].name: x})[0][0]
    p = np.exp(z - z.max())
    p /= p.sum()
    k = int(p.argmax())
    return labels[k], float(p[k])

agree = {"cv2": 0, "pil": 0}
total = 0
for clip in sys.argv[4:]:
    stem = os.path.splitext(os.path.basename(clip))[0]
    sides = {}
    for f in sorted(glob.glob(os.path.join(meta, f"{stem}__*.json"))):
        with open(f) as fh:
            d = json.load(fh)
        s = d["scene"]
        s = json.loads(s) if isinstance(s, str) else s
        sides[int(d["video.frame"])] = (os.path.basename(f), s[0]["class_name"], s[0]["confidence"])
    if not sides:
        print(f"{stem}: no sidecars in {meta}")
        continue
    frames = frame_at(clip, set(sides))
    for idx in sorted(sides):
        name, tl, tc = sides[idx]
        a = classify(cv2.resize(frames[idx], (224, 224), interpolation=cv2.INTER_LINEAR))
        b = classify(np.asarray(Image.fromarray(frames[idx]).resize((224, 224), Image.BILINEAR)))
        total += 1
        agree["cv2"] += a[0] == tl
        agree["pil"] += b[0] == tl
        print(f"{name:24s} frame {idx:4d}  tract {tl} {tc:.3f} | ort+cv2 {a[0]} {a[1]:.3f} | ort+pil {b[0]} {b[1]:.3f}")
print(f"top-1 agreement with Tract: ort+cv2 {agree['cv2']}/{total}, ort+pil {agree['pil']}/{total}")
