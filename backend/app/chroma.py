from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import cv2
import numpy as np


@dataclass
class ChromaOptions:
    key_color: Tuple[int, int, int] = (0, 255, 0)
    tolerance: float = 45.0
    softness: float = 18.0
    despill: float = 0.75
    denoise: int = 1
    fill_holes: int = 1


def parse_hex_color(value: str | None, default: str = "#00ff00") -> Tuple[int, int, int]:
    value = (value or default).strip()
    if value.startswith("#"):
        value = value[1:]
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        value = default[1:]
    try:
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    except ValueError:
        return parse_hex_color(default)


def _smoothstep(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
    if edge1 <= edge0:
        return (x >= edge0).astype(np.float32)
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _weighted_color_distance(rgb: np.ndarray, key_rgb: np.ndarray) -> np.ndarray:
    """Return a robust distance map combining RGB and HSV distance.

    RGB distance alone is fast, but HSV hue distance is more stable for green/blue screen.
    The function returns approximately 0-255 scale so UI tolerance values remain intuitive.
    """
    rgb_u8 = np.clip(rgb, 0, 255).astype(np.uint8)
    key_u8 = np.array([[key_rgb.astype(np.uint8)]], dtype=np.uint8)

    hsv = cv2.cvtColor(rgb_u8, cv2.COLOR_RGB2HSV).astype(np.float32)
    key_hsv = cv2.cvtColor(key_u8, cv2.COLOR_RGB2HSV).astype(np.float32)[0, 0]

    rgb_dist = np.linalg.norm(rgb.astype(np.float32) - key_rgb.astype(np.float32), axis=2) / np.sqrt(3.0)

    hue_diff = np.abs(hsv[:, :, 0] - key_hsv[0])
    hue_diff = np.minimum(hue_diff, 180.0 - hue_diff) * (255.0 / 90.0)
    sat_diff = np.abs(hsv[:, :, 1] - key_hsv[1])
    val_diff = np.abs(hsv[:, :, 2] - key_hsv[2])
    hsv_dist = 0.55 * hue_diff + 0.25 * sat_diff + 0.20 * val_diff

    return 0.55 * rgb_dist + 0.45 * hsv_dist


def _postprocess_alpha(alpha: np.ndarray, denoise: int, fill_holes: int) -> np.ndarray:
    if denoise <= 0 and fill_holes <= 0:
        return alpha

    # Operate on the hard mask only, then merge with soft edge alpha.
    hard = (alpha > 0.5).astype(np.uint8) * 255

    if denoise > 0:
        k = max(1, int(denoise) * 2 + 1)
        kernel = np.ones((k, k), dtype=np.uint8)
        hard = cv2.morphologyEx(hard, cv2.MORPH_OPEN, kernel)

    if fill_holes > 0:
        k = max(1, int(fill_holes) * 2 + 1)
        kernel = np.ones((k, k), dtype=np.uint8)
        hard = cv2.morphologyEx(hard, cv2.MORPH_CLOSE, kernel)

    # Preserve feathered edges by only removing obvious background speckles.
    return np.where(hard > 0, alpha, 0.0).astype(np.float32)


def _despill_rgb(rgb: np.ndarray, alpha: np.ndarray, key_rgb: np.ndarray, amount: float) -> np.ndarray:
    amount = float(np.clip(amount, 0.0, 1.0))
    if amount <= 0:
        return rgb

    out = rgb.astype(np.float32).copy()
    spill_strength = (1.0 - alpha) * amount
    dominant = int(np.argmax(key_rgb))

    if dominant == 1:  # green screen
        excess = np.maximum(0.0, out[:, :, 1] - np.maximum(out[:, :, 0], out[:, :, 2]))
        out[:, :, 1] -= excess * spill_strength
    elif dominant == 2:  # blue screen
        excess = np.maximum(0.0, out[:, :, 2] - np.maximum(out[:, :, 0], out[:, :, 1]))
        out[:, :, 2] -= excess * spill_strength
    elif dominant == 0:  # red screen, less common
        excess = np.maximum(0.0, out[:, :, 0] - np.maximum(out[:, :, 1], out[:, :, 2]))
        out[:, :, 0] -= excess * spill_strength
    else:
        # For white/gray backgrounds, reduce edge brightness slightly.
        brightness = out.mean(axis=2)
        edge = np.clip(1.0 - alpha, 0, 1) * amount
        out -= (brightness[:, :, None] - out) * 0.05 * edge[:, :, None]

    return np.clip(out, 0, 255).astype(np.uint8)


def apply_chroma_key(frame_rgb: np.ndarray, options: ChromaOptions) -> np.ndarray:
    """Convert an RGB frame to RGBA using chroma key removal."""
    if frame_rgb.ndim != 3 or frame_rgb.shape[2] != 3:
        raise ValueError("frame_rgb must be an HxWx3 RGB image")

    key = np.array(options.key_color, dtype=np.float32)
    tolerance = float(np.clip(options.tolerance, 0, 255))
    softness = float(np.clip(options.softness, 0, 255))

    dist = _weighted_color_distance(frame_rgb.astype(np.float32), key)
    alpha = _smoothstep(tolerance, tolerance + max(softness, 1.0), dist)
    alpha = _postprocess_alpha(alpha, options.denoise, options.fill_holes)

    out_rgb = _despill_rgb(frame_rgb, alpha, key, options.despill)
    out_alpha = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
    rgba = np.dstack([out_rgb, out_alpha])
    return rgba
