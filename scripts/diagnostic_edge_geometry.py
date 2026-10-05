"""Diagnostic-only distributed edges; excluded pixels cannot supply gradients."""

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class EdgeGeometry:
    descriptor: np.ndarray
    valid_pixel_count: int
    occupied_cell_count: int
    gradient_magnitude_sum: float


def masked_spatial_hog(
    image: np.ndarray,
    mask: np.ndarray,
    *,
    grid: tuple[int, int] = (8, 8),
    bins: int = 8,
) -> EdgeGeometry:
    """Measure current pixels whose entire 3x3 derivative footprint is valid.

    Scores are descriptive, not acceptance probabilities or production identity.
    No black fill is differentiated: masking after derivative-footprint erosion
    excludes artificial mask borders and influence from dynamic/excluded pixels.
    """
    if image.dtype != np.uint8 or image.ndim not in (2, 3):
        raise ValueError("expected uint8 grayscale or BGR image")
    if image.ndim == 3 and image.shape[2] != 3:
        raise ValueError("expected three BGR channels")
    height, width = image.shape[:2]
    if mask.shape != (height, width) or mask.dtype != np.bool_:
        raise ValueError("mask must be bool with image dimensions")
    rows, cols = grid
    if not (1 <= rows <= height and 1 <= cols <= width and 1 <= bins <= 180):
        raise ValueError("invalid descriptor geometry")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    valid = cv2.erode(
        mask.astype(np.uint8),
        np.ones((3, 3), np.uint8),
        borderType=cv2.BORDER_CONSTANT,
        borderValue=0,
    ).astype(bool)
    dx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    dy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    magnitude, angle = cv2.cartToPolar(dx, dy, angleInDegrees=True)
    orientation = (np.mod(angle, 180.0) * bins / 180.0).astype(np.int32).clip(0, bins - 1)
    magnitude = np.where(valid, magnitude, 0.0)
    cells = []
    for row in range(rows):
        for col in range(cols):
            ys = slice(row * height // rows, (row + 1) * height // rows)
            xs = slice(col * width // cols, (col + 1) * width // cols)
            cells.append(
                np.bincount(
                    orientation[ys, xs].ravel(),
                    weights=magnitude[ys, xs].ravel(),
                    minlength=bins,
                )
            )
    vector = np.asarray(cells, dtype=np.float64)
    occupied = int(np.count_nonzero(vector.sum(axis=1)))
    flat = vector.ravel()
    norm = float(np.linalg.norm(flat))
    return EdgeGeometry(
        flat / norm if norm else flat,
        int(valid.sum()),
        occupied,
        float(magnitude.sum(dtype=np.float64)),
    )
