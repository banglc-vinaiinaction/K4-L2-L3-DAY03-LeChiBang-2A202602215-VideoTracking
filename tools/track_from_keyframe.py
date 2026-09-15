#!/usr/bin/env python3
"""Track vehicles from a single CVAT keyframe using OpenCV optical flow.

For each target track (with only 1 keyframe), this script:
1. Extracts a dense grid of feature points within the bbox
2. Tracks them forward and backward using Lucas-Kanade optical flow
3. Estimates the bbox position in each frame from tracked points
4. Detects occlusion/visibility transitions and marks keyframes there
5. Writes the results back into CVAT

Usage:
    python3 tools/track_from_keyframe.py --task-id 6 --track-ids 22,23 --dry-run
    python3 tools/track_from_keyframe.py --task-id 6 --track-ids 22,23
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# CVAT helpers (same pattern as kalman_propagate.py)
# ---------------------------------------------------------------------------

def cvat_get_track(task_id: int, track_id: int) -> dict:
    script = f"""
import django, os, json
os.environ['DJANGO_SETTINGS_MODULE'] = 'cvat.settings.production'
django.setup()
from cvat.apps.engine.models import Task, LabeledTrack, TrackedShape

task = Task.objects.get(id={task_id})
track = LabeledTrack.objects.get(id={track_id})
shapes = TrackedShape.objects.filter(track=track).order_by('frame')
data = {{
    'task_name': task.name,
    'frame_count': task.data.size,
    'track_id': track.id,
    'label': track.label.name,
    'label_id': track.label.id,
    'shapes': [{{
        'frame': s.frame,
        'outside': s.outside,
        'occluded': s.occluded,
        'points': list(s.points),
        'type': s.type,
    }} for s in shapes],
}}
print(json.dumps(data))
"""
    r = subprocess.run(["docker", "exec", "cvat_server", "python3", "-c", script],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        print(f"Error: {r.stderr}", file=sys.stderr)
        raise SystemExit(1)
    return json.loads(r.stdout)


def cvat_write_shapes(task_id: int, track_id: int, new_shapes: list[dict]) -> None:
    shapes_json = json.dumps(new_shapes).replace("'", "\\'")
    script = f"""
import django, os, json
os.environ['DJANGO_SETTINGS_MODULE'] = 'cvat.settings.production'
django.setup()
from cvat.apps.engine.models import LabeledTrack, TrackedShape

track = LabeledTrack.objects.get(id={track_id})
shapes = json.loads('{shapes_json}')

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
    r = subprocess.run(["docker", "exec", "cvat_server", "python3", "-c", script],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        print(f"Error: {r.stderr}", file=sys.stderr)
        raise SystemExit(1)
    print(r.stdout.strip())


# ---------------------------------------------------------------------------
# Optical flow tracker
# ---------------------------------------------------------------------------

def load_frame(clip_dir: Path, frame_idx: int) -> np.ndarray | None:
    """Load frame image (0-indexed frame_idx -> 1-indexed filename)."""
    path = clip_dir / "img1" / f"{frame_idx + 1:06d}.jpg"
    if not path.exists():
        return None
    return cv2.imread(str(path))


def generate_grid_points(bbox: np.ndarray, step: int = 5) -> np.ndarray:
    """Generate a dense grid of points inside the bbox."""
    xtl, ytl, xbr, ybr = bbox.astype(int)
    xs = np.arange(xtl + step, xbr, step)
    ys = np.arange(ytl + step, ybr, step)
    grid = np.array(np.meshgrid(xs, ys)).T.reshape(-1, 2).astype(np.float32)
    return grid.reshape(-1, 1, 2)


def track_direction(
    clip_dir: Path,
    start_frame: int,
    start_bbox: np.ndarray,
    direction: int,  # +1 forward, -1 backward
    max_frames: int,
    frame_count: int,
    im_width: int = 960,
    im_height: int = 540,
) -> list[dict]:
    """Track a bbox in one direction using Lucas-Kanade optical flow.

    Returns list of {frame, bbox, occluded, outside, confidence} dicts.
    """
    lk_params = dict(
        winSize=(21, 21),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )

    results = []
    prev_img = load_frame(clip_dir, start_frame)
    if prev_img is None:
        return results
    prev_gray = cv2.cvtColor(prev_img, cv2.COLOR_BGR2GRAY)

    # Initial feature points from bbox
    prev_points = generate_grid_points(start_bbox, step=5)
    if len(prev_points) < 4:
        prev_points = generate_grid_points(start_bbox, step=3)
    if len(prev_points) < 2:
        return results

    initial_point_count = len(prev_points)
    current_bbox = start_bbox.copy()

    for step_i in range(1, max_frames + 1):
        frame_idx = start_frame + direction * step_i
        if frame_idx < 0 or frame_idx >= frame_count:
            # Vehicle has gone outside
            results.append({
                "frame": max(0, min(frame_idx, frame_count - 1)),
                "bbox": current_bbox.tolist(),
                "occluded": False,
                "outside": True,
                "confidence": 0.0,
            })
            break

        curr_img = load_frame(clip_dir, frame_idx)
        if curr_img is None:
            break
        curr_gray = cv2.cvtColor(curr_img, cv2.COLOR_BGR2GRAY)

        # Track points
        next_points, status, err = cv2.calcOpticalFlowPyrLK(
            prev_gray, curr_gray, prev_points, None, **lk_params
        )

        if next_points is None or status is None:
            break

        # Filter good points
        good_mask = status.flatten() == 1
        if good_mask.sum() < 2:
            # Lost tracking — likely fully occluded or out of frame
            results.append({
                "frame": frame_idx,
                "bbox": current_bbox.tolist(),
                "occluded": True,
                "outside": False,
                "confidence": 0.0,
            })
            break

        good_new = next_points[good_mask]
        good_old = prev_points[good_mask]

        # Estimate new bbox from tracked points
        # Compute median displacement
        displacements = (good_new - good_old).reshape(-1, 2)
        median_dx = np.median(displacements[:, 0])
        median_dy = np.median(displacements[:, 1])

        # Also estimate scale change from point spread
        old_spread = np.std(good_old.reshape(-1, 2), axis=0)
        new_spread = np.std(good_new.reshape(-1, 2), axis=0)
        scale_x = new_spread[0] / max(old_spread[0], 1e-6)
        scale_y = new_spread[1] / max(old_spread[1], 1e-6)
        # Clamp scale to reasonable range
        scale_x = np.clip(scale_x, 0.98, 1.02)
        scale_y = np.clip(scale_y, 0.98, 1.02)

        # Apply displacement and scale
        cx = (current_bbox[0] + current_bbox[2]) / 2 + median_dx
        cy = (current_bbox[1] + current_bbox[3]) / 2 + median_dy
        w = (current_bbox[2] - current_bbox[0]) * scale_x
        h = (current_bbox[3] - current_bbox[1]) * scale_y

        new_bbox = np.array([cx - w/2, cy - h/2, cx + w/2, cy + h/2])

        # Clamp to image bounds
        new_bbox[0] = max(0, new_bbox[0])
        new_bbox[1] = max(0, new_bbox[1])
        new_bbox[2] = min(im_width, new_bbox[2])
        new_bbox[3] = min(im_height, new_bbox[3])

        # Check if mostly outside
        visible_w = new_bbox[2] - new_bbox[0]
        visible_h = new_bbox[3] - new_bbox[1]
        is_outside = visible_w < 3 or visible_h < 3

        # Confidence based on how many points survived
        confidence = good_mask.sum() / initial_point_count

        # Detect occlusion: significant point loss
        is_occluded = confidence < 0.4

        results.append({
            "frame": frame_idx,
            "bbox": new_bbox.tolist(),
            "occluded": is_occluded,
            "outside": is_outside,
            "confidence": float(confidence),
        })

        if is_outside:
            break

        current_bbox = new_bbox
        prev_gray = curr_gray

        # Re-generate points periodically to avoid drift
        if step_i % 10 == 0:
            prev_points = generate_grid_points(current_bbox, step=5)
            if len(prev_points) < 4:
                prev_points = generate_grid_points(current_bbox, step=3)
            initial_point_count = len(prev_points)
        else:
            prev_points = good_new

    return results


def select_keyframes(
    tracked: list[dict],
    start_bbox: list[float],
    start_frame: int,
) -> list[dict]:
    """Select keyframes at occlusion/visibility transitions and periodic intervals.

    Picks: first visible, last visible, occlusion in/out edges, outside edges,
    and every 10th frame for smooth CVAT interpolation.
    """
    if not tracked:
        return []

    keyframes = []
    prev_occluded = False
    prev_outside = False

    for i, t in enumerate(tracked):
        pick = False
        reason = ""

        # First and last frame always
        if i == 0:
            pick, reason = True, "first"
        elif i == len(tracked) - 1:
            pick, reason = True, "last"

        # Occlusion transition edge (entering or exiting)
        if t["occluded"] != prev_occluded:
            pick = True
            reason = "occluded" if t["occluded"] else "de-occluded"
            # Also add the frame just before the transition
            if i > 0 and not keyframes or keyframes[-1]["frame"] != tracked[i-1]["frame"]:
                p_prev = tracked[i-1]["bbox"]
                keyframes.append({
                    "frame": tracked[i-1]["frame"],
                    "outside": tracked[i-1]["outside"],
                    "occluded": tracked[i-1]["occluded"],
                    "points": [float(p_prev[0]), float(p_prev[1]),
                               float(p_prev[2]), float(p_prev[3])],
                    "reason": "pre_" + reason,
                    "confidence": tracked[i-1]["confidence"],
                })

        # Outside transition edge
        if t["outside"] != prev_outside:
            pick = True
            reason = "outside" if t["outside"] else "re-entered"

        # Periodic every 10 frames (for smooth interpolation)
        if not pick and i > 0 and i % 10 == 0 and not t["outside"]:
            pick, reason = True, "periodic"

        if pick:
            p = t["bbox"]
            keyframes.append({
                "frame": t["frame"],
                "outside": t["outside"],
                "occluded": t["occluded"],
                "points": [float(p[0]), float(p[1]), float(p[2]), float(p[3])],
                "reason": reason,
                "confidence": t["confidence"],
            })

        prev_occluded = t["occluded"]
        prev_outside = t["outside"]

    return keyframes


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--task-id", type=int, default=6)
    parser.add_argument("--track-ids", required=True,
                        help="Comma-separated CVAT track IDs")
    parser.add_argument("--clip", type=Path,
                        default=Path("data/clips/clip_01"))
    parser.add_argument("--max-frames", type=int, default=40,
                        help="Max frames to track in each direction")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    track_ids = [int(x) for x in args.track_ids.split(",")]

    for tid in track_ids:
        print(f"\n{'='*60}")
        print(f"Processing track {tid}")
        print(f"{'='*60}")

        data = cvat_get_track(args.task_id, tid)
        shapes = data["shapes"]
        frame_count = data["frame_count"]

        if not shapes:
            print(f"  No shapes found, skipping")
            continue

        # Use the first (and likely only) keyframe as anchor
        anchor = shapes[0]
        anchor_frame = anchor["frame"]
        anchor_bbox = np.array(anchor["points"][:4])

        print(f"  Anchor: frame={anchor_frame} "
              f"bbox=[{anchor_bbox[0]:.0f},{anchor_bbox[1]:.0f},"
              f"{anchor_bbox[2]:.0f},{anchor_bbox[3]:.0f}]")

        # Track forward
        print(f"  Tracking forward from frame {anchor_frame}...")
        fwd = track_direction(
            args.clip, anchor_frame, anchor_bbox,
            direction=+1, max_frames=args.max_frames,
            frame_count=frame_count,
        )
        print(f"  Forward: {len(fwd)} frames tracked")
        if fwd:
            last = fwd[-1]
            print(f"    Last: frame={last['frame']} "
                  f"occluded={last['occluded']} outside={last['outside']} "
                  f"conf={last['confidence']:.2f}")

        # Track backward
        print(f"  Tracking backward from frame {anchor_frame}...")
        bwd = track_direction(
            args.clip, anchor_frame, anchor_bbox,
            direction=-1, max_frames=args.max_frames,
            frame_count=frame_count,
        )
        print(f"  Backward: {len(bwd)} frames tracked")
        if bwd:
            first = bwd[-1]
            print(f"    First: frame={first['frame']} "
                  f"occluded={first['occluded']} outside={first['outside']} "
                  f"conf={first['confidence']:.2f}")

        # Combine: backward (reversed) + forward
        all_tracked = list(reversed(bwd)) + fwd

        # Select keyframes at transitions
        keyframes = select_keyframes(all_tracked, anchor_bbox.tolist(), anchor_frame)

        print(f"\n  Selected {len(keyframes)} keyframes:")
        for kf in keyframes:
            p = kf["points"]
            print(f"    frame={kf['frame']:3d} "
                  f"outside={kf['outside']!s:5s} "
                  f"occluded={kf['occluded']!s:5s} "
                  f"conf={kf['confidence']:.2f} "
                  f"reason={kf.get('reason','')} "
                  f"bbox=[{p[0]:.0f},{p[1]:.0f},{p[2]:.0f},{p[3]:.0f}]")

        if args.dry_run:
            print(f"  [DRY RUN] Not writing to CVAT")
        else:
            # Remove 'reason' and 'confidence' before writing
            cvat_shapes = [{
                "frame": int(kf["frame"]),
                "outside": bool(kf["outside"]),
                "occluded": bool(kf["occluded"]),
                "points": [float(x) for x in kf["points"]],
            } for kf in keyframes]
            cvat_write_shapes(args.task_id, tid, cvat_shapes)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
