#!/usr/bin/env python3
"""Propagate existing CVAT track keyframes using a DeepSORT-style Kalman filter.

Reads sparse keyframes from CVAT task 'clip01' (task_id=6), applies a constant-
velocity Kalman filter in the (cx, cy, aspect_ratio, height) state space (same
as DeepSORT), and writes the predicted bounding boxes as additional TrackedShape
keyframes back into the CVAT database.

Usage (run OUTSIDE docker, talks to CVAT via docker exec):

    python3 tools/kalman_propagate.py --task-id 6 --predict-frames 20

Options:
    --task-id       CVAT task ID (default: 6 = clip01)
    --predict-frames  How many frames to predict forward beyond last keyframe
                      per track (default: 20)
    --dry-run       Print predictions without writing to CVAT
    --track-ids     Comma-separated list of CVAT track IDs to process
                    (default: all tracks in the task)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field

import numpy as np


# ---------------------------------------------------------------------------
# DeepSORT-style Kalman Filter
# State vector: [cx, cy, a, h, vx, vy, va, vh]
#   cx, cy = bounding box centre
#   a      = aspect ratio (w / h)
#   h      = height
#   vx … vh = velocities
# ---------------------------------------------------------------------------

class KalmanBoxTracker:
    """A single-object Kalman tracker using the DeepSORT state space."""

    # Process noise gains (tunable)
    _std_weight_position = 1.0 / 20
    _std_weight_velocity = 1.0 / 160

    def __init__(self, bbox: np.ndarray):
        """Initialise with first measurement [xtl, ytl, xbr, ybr]."""
        self.dt = 1  # 1 frame

        # State transition model  (constant velocity)
        self.F = np.eye(8)
        self.F[:4, 4:] = self.dt * np.eye(4)

        # Observation model  (we observe [cx, cy, a, h])
        self.H = np.eye(4, 8)

        # Initial state from first bbox
        z = self._bbox_to_z(bbox)
        self.x = np.zeros(8)
        self.x[:4] = z
        # Initial velocities = 0

        # Covariance
        std = [
            2 * self._std_weight_position * z[3],   # cx
            2 * self._std_weight_position * z[3],   # cy
            1e-2,                                    # a
            2 * self._std_weight_position * z[3],   # h
            10 * self._std_weight_velocity * z[3],  # vx
            10 * self._std_weight_velocity * z[3],  # vy
            1e-5,                                    # va
            10 * self._std_weight_velocity * z[3],  # vh
        ]
        self.P = np.diag(np.square(std))

    @staticmethod
    def _bbox_to_z(bbox: np.ndarray) -> np.ndarray:
        """[xtl, ytl, xbr, ybr] -> [cx, cy, a, h]."""
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        cx = bbox[0] + w / 2
        cy = bbox[1] + h / 2
        a = w / max(h, 1e-6)
        return np.array([cx, cy, a, h])

    @staticmethod
    def _z_to_bbox(z: np.ndarray) -> np.ndarray:
        """[cx, cy, a, h] -> [xtl, ytl, xbr, ybr]."""
        w = z[2] * z[3]
        return np.array([
            z[0] - w / 2,
            z[1] - z[3] / 2,
            z[0] + w / 2,
            z[1] + z[3] / 2,
        ])

    def _process_noise(self) -> np.ndarray:
        h = self.x[3]
        std = [
            self._std_weight_position * h,
            self._std_weight_position * h,
            1e-2,
            self._std_weight_position * h,
            self._std_weight_velocity * h,
            self._std_weight_velocity * h,
            1e-5,
            self._std_weight_velocity * h,
        ]
        return np.diag(np.square(std))

    def _measurement_noise(self) -> np.ndarray:
        h = self.x[3]
        std = [
            self._std_weight_position * h,
            self._std_weight_position * h,
            1e-1,
            self._std_weight_position * h,
        ]
        return np.diag(np.square(std))

    def predict(self) -> np.ndarray:
        """Predict next state. Returns bbox [xtl, ytl, xbr, ybr]."""
        Q = self._process_noise()
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + Q
        # Clamp aspect ratio and height to be positive
        self.x[2] = max(self.x[2], 1e-4)
        self.x[3] = max(self.x[3], 1e-4)
        return self._z_to_bbox(self.x[:4])

    def update(self, bbox: np.ndarray) -> np.ndarray:
        """Update with a measurement. Returns corrected bbox."""
        z = self._bbox_to_z(bbox)
        R = self._measurement_noise()

        y = z - self.H @ self.x  # innovation
        S = self.H @ self.P @ self.H.T + R
        K = self.P @ self.H.T @ np.linalg.inv(S)

        self.x = self.x + K @ y
        I_KH = np.eye(8) - K @ self.H
        self.P = I_KH @ self.P

        self.x[2] = max(self.x[2], 1e-4)
        self.x[3] = max(self.x[3], 1e-4)
        return self._z_to_bbox(self.x[:4])


# ---------------------------------------------------------------------------
# CVAT data extraction (runs inside docker via subprocess)
# ---------------------------------------------------------------------------

def cvat_extract_tracks(task_id: int) -> dict:
    """Extract all track shapes from CVAT via docker exec."""
    script = f"""
import django, os, json
os.environ['DJANGO_SETTINGS_MODULE'] = 'cvat.settings.production'
django.setup()
from cvat.apps.engine.models import Task, LabeledTrack, TrackedShape

task = Task.objects.get(id={task_id})
data = {{
    'task_name': task.name,
    'frame_count': task.data.size,
    'im_width': task.data.image_quality,
}}

# Get job id
from cvat.apps.engine.models import Job
job = Job.objects.filter(segment__task=task).first()
data['job_id'] = job.id

tracks = LabeledTrack.objects.filter(job__segment__task=task).select_related('label')
data['tracks'] = {{}}
for track in tracks:
    shapes = TrackedShape.objects.filter(track=track).order_by('frame')
    data['tracks'][track.id] = {{
        'id': track.id,
        'label': track.label.name,
        'label_id': track.label.id,
        'shapes': [{{
            'frame': s.frame,
            'outside': s.outside,
            'occluded': s.occluded,
            'points': list(s.points) if s.points else [],
            'type': s.type,
        }} for s in shapes],
    }}

print(json.dumps(data))
"""
    result = subprocess.run(
        ["docker", "exec", "cvat_server", "python3", "-c", script],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        print(f"CVAT extract error:\n{result.stderr}", file=sys.stderr)
        raise SystemExit(1)
    return json.loads(result.stdout)


def cvat_write_shapes(task_id: int, track_id: int, new_shapes: list[dict]) -> None:
    """Write new TrackedShape keyframes into CVAT via docker exec."""
    shapes_json = json.dumps(new_shapes)
    script = f"""
import django, os, json
os.environ['DJANGO_SETTINGS_MODULE'] = 'cvat.settings.production'
django.setup()
from cvat.apps.engine.models import LabeledTrack, TrackedShape

track = LabeledTrack.objects.get(id={track_id})
shapes = json.loads('''{shapes_json}''')

existing_frames = set(
    TrackedShape.objects.filter(track=track).values_list('frame', flat=True)
)

created = 0
for s in shapes:
    if s['frame'] in existing_frames:
        continue
    TrackedShape.objects.create(
        track=track,
        frame=s['frame'],
        outside=s['outside'],
        occluded=s.get('occluded', False),
        points=s['points'],
        type='rectangle',
    )
    created += 1

print(f'Track {{track.id}}: created {{created}} new shapes')
"""
    result = subprocess.run(
        ["docker", "exec", "cvat_server", "python3", "-c", script],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        print(f"CVAT write error:\n{result.stderr}", file=sys.stderr)
        raise SystemExit(1)
    print(result.stdout.strip())


# ---------------------------------------------------------------------------
# Main propagation logic
# ---------------------------------------------------------------------------

@dataclass
class TrackPropagation:
    track_id: int
    label: str
    existing_keyframes: list[dict] = field(default_factory=list)
    predicted_shapes: list[dict] = field(default_factory=list)
    velocity_history: list[tuple[float, float]] = field(default_factory=list)


def propagate_track(
    track_data: dict,
    predict_frames: int,
    frame_count: int,
    im_width: int = 960,
    im_height: int = 540,
) -> TrackPropagation:
    """Run Kalman filter on one track, return predicted shapes."""
    prop = TrackPropagation(
        track_id=track_data["id"],
        label=track_data["label"],
        existing_keyframes=track_data["shapes"],
    )

    shapes = sorted(track_data["shapes"], key=lambda s: s["frame"])
    if len(shapes) < 2:
        print(f"  Track {prop.track_id}: too few keyframes ({len(shapes)}), skipping")
        return prop

    # Find last non-outside frame
    last_visible_idx = -1
    for i, s in enumerate(shapes):
        if not s["outside"]:
            last_visible_idx = i

    if last_visible_idx < 1:
        print(f"  Track {prop.track_id}: no visible frames to propagate from")
        return prop

    # Initialize Kalman filter with first keyframe
    first_bbox = np.array(shapes[0]["points"][:4])
    kf = KalmanBoxTracker(first_bbox)

    # Feed all existing keyframes as measurements
    prev_frame = shapes[0]["frame"]
    for shape in shapes[1:last_visible_idx + 1]:
        curr_frame = shape["frame"]
        gap = curr_frame - prev_frame

        # Predict through the gap
        for _ in range(gap - 1):
            kf.predict()

        # Predict + update at the keyframe
        kf.predict()
        bbox_meas = np.array(shape["points"][:4])
        corrected = kf.update(bbox_meas)
        prev_frame = curr_frame

    # Record velocity after absorbing all keyframes
    vx, vy = kf.x[4], kf.x[5]
    prop.velocity_history.append((vx, vy))
    print(f"  Track {prop.track_id} ({prop.label}): "
          f"learned velocity = ({vx:.1f}, {vy:.1f}) px/frame, "
          f"last keyframe at frame {prev_frame}")

    # Now predict forward
    last_frame = shapes[last_visible_idx]["frame"]
    end_frame = min(last_frame + predict_frames, frame_count - 1)

    for frame_idx in range(last_frame + 1, end_frame + 1):
        predicted_bbox = kf.predict()

        # Clamp to image bounds
        xtl = float(np.clip(predicted_bbox[0], 0, im_width))
        ytl = float(np.clip(predicted_bbox[1], 0, im_height))
        xbr = float(np.clip(predicted_bbox[2], 0, im_width))
        ybr = float(np.clip(predicted_bbox[3], 0, im_height))

        # Stop if box has left the frame entirely
        if xbr - xtl < 2 or ybr - ytl < 2:
            # Mark outside
            prop.predicted_shapes.append({
                "frame": frame_idx,
                "outside": True,
                "occluded": False,
                "points": [xtl, ytl, xbr, ybr],
            })
            break

        prop.predicted_shapes.append({
            "frame": frame_idx,
            "outside": False,
            "occluded": False,
            "points": [xtl, ytl, xbr, ybr],
        })

    print(f"  Track {prop.track_id}: predicted {len(prop.predicted_shapes)} new frames "
          f"({last_frame + 1}..{last_frame + len(prop.predicted_shapes)})")

    return prop


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--task-id", type=int, default=6, help="CVAT task ID")
    parser.add_argument("--predict-frames", type=int, default=20,
                        help="Number of frames to predict forward per track")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print predictions without writing to CVAT")
    parser.add_argument("--track-ids", default=None,
                        help="Comma-separated CVAT track IDs to process (default: all)")
    parser.add_argument("--mot-out", default=None,
                        help="Also write combined predictions to MOT format file")
    args = parser.parse_args()

    print(f"Extracting tracks from CVAT task {args.task_id}...")
    data = cvat_extract_tracks(args.task_id)
    print(f"Task: {data['task_name']}, frames: {data['frame_count']}")
    print(f"Tracks found: {list(data['tracks'].keys())}")

    track_filter = None
    if args.track_ids:
        track_filter = {int(x) for x in args.track_ids.split(",")}

    results: list[TrackPropagation] = []
    for tid_str, tdata in data["tracks"].items():
        tid = int(tid_str)
        if track_filter and tid not in track_filter:
            continue
        prop = propagate_track(
            tdata,
            predict_frames=args.predict_frames,
            frame_count=data["frame_count"],
        )
        results.append(prop)

    # Summary
    print("\n--- Kalman Propagation Summary ---")
    total_new = 0
    for r in results:
        n = len(r.predicted_shapes)
        total_new += n
        if n > 0:
            frames = [s["frame"] for s in r.predicted_shapes if not s["outside"]]
            vel = r.velocity_history[-1] if r.velocity_history else (0, 0)
            print(f"  Track {r.track_id} ({r.label}): "
                  f"{n} predicted, velocity=({vel[0]:.1f},{vel[1]:.1f}), "
                  f"frames {min(frames) if frames else '?'}..{max(frames) if frames else '?'}")
    print(f"Total new shapes: {total_new}")

    if args.dry_run:
        print("\n[DRY RUN] Not writing to CVAT. Predictions:")
        for r in results:
            for s in r.predicted_shapes:
                p = s["points"]
                print(f"  track={r.track_id} frame={s['frame']} "
                      f"outside={s['outside']} "
                      f"bbox=[{p[0]:.1f}, {p[1]:.1f}, {p[2]:.1f}, {p[3]:.1f}]")
        return 0

    # Write to CVAT
    print("\nWriting to CVAT...")
    for r in results:
        if r.predicted_shapes:
            cvat_write_shapes(args.task_id, r.track_id, r.predicted_shapes)

    # Optionally write MOT format
    if args.mot_out:
        from pathlib import Path
        rows = []
        for r in results:
            # Include existing + predicted
            for s in r.existing_keyframes + r.predicted_shapes:
                if s["outside"]:
                    continue
                p = s["points"]
                # MOT: frame(1-indexed), id, x, y, w, h, conf, -1, -1, -1
                rows.append((
                    s["frame"] + 1,  # CVAT is 0-indexed, MOT is 1-indexed
                    r.track_id,
                    p[0], p[1],
                    p[2] - p[0], p[3] - p[1],
                    1.0,
                ))
        out_path = Path(args.mot_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            "\n".join(
                f"{f},{t},{x:.2f},{y:.2f},{w:.2f},{h:.2f},{c:.4f},-1,-1,-1"
                for f, t, x, y, w, h, c in sorted(rows)
            ) + "\n",
            encoding="utf-8",
        )
        print(f"MOT output written to {out_path}")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
