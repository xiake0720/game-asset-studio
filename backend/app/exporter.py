from __future__ import annotations

import json
import math
import zipfile
from pathlib import Path
from typing import Iterable, List, Sequence

import imageio.v2 as imageio
from PIL import Image


def zip_directory(source_dir: Path, output_zip: Path, arc_prefix: str = "") -> None:
    source_dir = Path(source_dir)
    output_zip = Path(output_zip)
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                rel = path.relative_to(source_dir).as_posix()
                if arc_prefix:
                    rel = f"{arc_prefix.rstrip('/')}/{rel}"
                zf.write(path, rel)


def create_sprite_sheet(frame_paths: Sequence[Path], output_path: Path, columns: int = 6, gap: int = 0) -> dict:
    if not frame_paths:
        raise ValueError("No frames to create sprite sheet")
    columns = max(1, int(columns))
    gap = max(0, int(gap))
    with Image.open(frame_paths[0]) as first:
        frame_w, frame_h = first.size
        mode = "RGBA" if first.mode == "RGBA" else "RGB"

    rows = math.ceil(len(frame_paths) / columns)
    sheet_w = frame_w * columns + gap * max(0, columns - 1)
    sheet_h = frame_h * rows + gap * max(0, rows - 1)
    sheet = Image.new(mode, (sheet_w, sheet_h), (0, 0, 0, 0) if mode == "RGBA" else (255, 255, 255))

    for i, frame_path in enumerate(frame_paths):
        with Image.open(frame_path) as im:
            if im.mode != mode:
                im = im.convert(mode)
            x = (i % columns) * (frame_w + gap)
            y = (i // columns) * (frame_h + gap)
            sheet.paste(im, (x, y), im if mode == "RGBA" else None)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)
    return {
        "path": output_path.name,
        "columns": columns,
        "rows": rows,
        "gap": gap,
        "frame_width": frame_w,
        "frame_height": frame_h,
        "frame_count": len(frame_paths),
        "sheet_width": sheet_w,
        "sheet_height": sheet_h,
    }


def create_gif(frame_paths: Sequence[Path], output_path: Path, fps: float) -> dict:
    if not frame_paths:
        raise ValueError("No frames to create gif")
    duration = 1.0 / max(float(fps), 1.0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # imageio writes incrementally and avoids keeping the whole GIF source in memory.
    with imageio.get_writer(output_path, mode="I", duration=duration, loop=0) as writer:
        for frame_path in frame_paths:
            frame = imageio.imread(frame_path)
            writer.append_data(frame)
    return {"path": output_path.name, "fps": fps, "frame_count": len(frame_paths)}


def create_spine_package(frame_paths: Sequence[Path], output_zip: Path, fps: float, animation_name: str = "idle") -> dict:
    if not frame_paths:
        raise ValueError("No frames to create Spine package")

    with Image.open(frame_paths[0]) as first:
        width, height = first.size

    skeleton = {
        "skeleton": {
            "hash": "motion-sprite-studio",
            "spine": "4.1.00",
            "x": 0,
            "y": 0,
            "width": width,
            "height": height,
            "images": "./images/",
            "audio": "./audio/",
        },
        "bones": [{"name": "root"}],
        "slots": [{"name": "sprite", "bone": "root", "attachment": "frame_0000"}],
        "skins": [{
            "name": "default",
            "attachments": {
                "sprite": {
                    f"frame_{i:04d}": {
                        "name": f"frame_{i:04d}.png",
                        "width": width,
                        "height": height,
                    }
                    for i in range(len(frame_paths))
                }
            },
        }],
        "animations": {
            animation_name: {
                "slots": {
                    "sprite": {
                        "attachment": [
                            {"time": round(i / max(fps, 1.0), 6), "name": f"frame_{i:04d}"}
                            for i in range(len(frame_paths))
                        ]
                    }
                }
            }
        },
    }

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("skeleton.json", json.dumps(skeleton, ensure_ascii=False, indent=2))
        readme = (
            "Motion Sprite Studio Spine package\n"
            "This package uses one root bone, one sprite slot and attachment timeline animation.\n"
            "It is intended as a starter package for further editing in Spine.\n"
        )
        zf.writestr("README.txt", readme)
        for i, frame_path in enumerate(frame_paths):
            zf.write(frame_path, f"images/frame_{i:04d}.png")

    return {"path": output_zip.name, "frame_count": len(frame_paths), "fps": fps, "width": width, "height": height}
