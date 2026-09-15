#!/usr/bin/env python3
"""Run YOLO + ByteTrack, YOLO + BoT-SORT-ReID, and all evaluations."""
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import run_tracker
import ultralytics
import torch
import importlib.metadata as metadata

CLIP = ROOT / "data" / "clips" / "clip_01"
MY_LABELS = ROOT / "annotations" / "clip_01" / "gt.txt"
GOLD = ROOT / "gold" / "clip_01" / "gt.txt"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

DEVICE = "0" if torch.cuda.is_available() else "cpu"
MODEL = "yolo26n.pt"  # or yolo11n.pt fallback if yolo26n doesn't exist
CONF = 0.25
IOU = 0.70
IMGSZ = 960
CLASSES = [2, 5, 7]

RUNS = {
    "bytetrack": {
        "label": "ByteTrack control",
        "tracker": "bytetrack.yaml",
        "out": OUT / "model_bytetrack_clip_01.txt",
    },
    "reid": {
        "label": "BoT-SORT + ReID treatment",
        "tracker": str(ROOT / "configs" / "trackers" / "botsort-reid.yaml"),
        "out": OUT / "model_reid_clip_01.txt",
    },
}

run_config = {
    "python": platform.python_version(),
    "ultralytics": ultralytics.__version__,
    "torch": torch.__version__,
    "lap": metadata.version("lap"),
    "weights": MODEL,
    "runs": {name: {"label": run["label"], "tracker": run["tracker"]}
             for name, run in RUNS.items()},
    "conf": CONF,
    "iou": IOU,
    "imgsz": IMGSZ,
    "classes": CLASSES,
    "device": DEVICE,
    "persist": True,
    "clip_frames": 190,
}

MODEL_CONFIG = OUT / "model_run_config.json"
MODEL_CONFIG.write_text(json.dumps(run_config, indent=2) + "\n", encoding="utf-8")
print("Saved model_run_config.json")

# Run trackers
for run_name, run in RUNS.items():
    print(f"\n=== Running {run['label']} ===")
    rows = run_tracker.track_clip(
        clip=CLIP, model_name=MODEL, tracker=run["tracker"],
        conf=CONF, iou=IOU, imgsz=IMGSZ, classes=CLASSES, device=DEVICE,
    )
    run_tracker.write_mot(rows, run["out"])
    tracks = {r[1] for r in rows}
    print(f"{run['label']}: {len(rows)} bboxes, {len(tracks)} tracks -> {run['out']}")

def evaluate(pred, gt, mode, out_json, pred_label, gt_label):
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "evaluate_tracking.py"),
         "--pred", str(pred), "--gt", str(gt),
         "--seqinfo", str(CLIP / "seqinfo.ini"),
         "--mode", mode, "--output", str(out_json),
         "--pred-label", pred_label, "--gt-label", gt_label],
        check=True
    )
    return json.loads(Path(out_json).read_text())

print("\n=== Evaluating ===")
res_mine = evaluate(MY_LABELS, GOLD, "annotation", OUT / "eval_vs_gold.json", "nhan cua ban", "gold clip_01")
res_byte = evaluate(RUNS["bytetrack"]["out"], GOLD, "model", OUT / "eval_bytetrack_vs_gold.json", "ByteTrack control", "gold clip_01")
res_reid = evaluate(RUNS["reid"]["out"], GOLD, "model", OUT / "eval_reid_vs_gold.json", "BoT-SORT + ReID", "gold clip_01")
res_reid_me = evaluate(RUNS["reid"]["out"], MY_LABELS, "peer", OUT / "eval_reid_vs_me.json", "BoT-SORT + ReID", "nhan cua ban")

print("\n=== SUMMARY TABLE ===")
ORDER = ["HOTA", "DetA", "AssA", "LocA", "IDF1", "MOTA", "MOTP", "FP", "FN", "IDSW"]
results = {
    "ban vs gold": res_mine,
    "ByteTrack control vs gold": res_byte,
    "BoT-SORT + ReID vs gold": res_reid,
    "ReID vs ban": res_reid_me,
}

header = "{:<26}".format("So sanh") + "".join("{:>8}".format(k) for k in ORDER)
print(header)
print("-" * len(header))
for name, res in results.items():
    m = res["metrics"]
    row = "{:<26}".format(name)
    for k in ORDER:
        v = m[k]
        row += "{:>8.3f}".format(v) if isinstance(v, float) else "{:>8d}".format(v)
    print(row)
