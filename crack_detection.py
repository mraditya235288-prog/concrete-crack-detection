import cv2
import math
import numpy as np
import scipy.ndimage


def non_max_suppression(data, win):
    data_max = scipy.ndimage.maximum_filter(
        data,
        footprint=win,
        mode="constant"
    )
    return data * (data == data_max)


def orientated_non_max_suppression(mag, ang):
    ang_quant = np.round(ang / (np.pi / 4)) % 4

    winE = np.array([[0, 0, 0], [1, 1, 1], [0, 0, 0]])
    winSE = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    winS = np.array([[0, 1, 0], [0, 1, 0], [0, 1, 0]])
    winSW = np.array([[0, 0, 1], [0, 1, 0], [1, 0, 0]])

    magE = non_max_suppression(mag, winE)
    magSE = non_max_suppression(mag, winSE)
    magS = non_max_suppression(mag, winS)
    magSW = non_max_suppression(mag, winSW)

    mag[ang_quant == 0] = magE[ang_quant == 0]
    mag[ang_quant == 1] = magSE[ang_quant == 1]
    mag[ang_quant == 2] = magS[ang_quant == 2]
    mag[ang_quant == 3] = magSW[ang_quant == 3]
    return mag


def _detect_on_tile(tile_bgr, pixels_per_cm=100.0, mode="structural"):
    """Run the supplied image-processing pipeline on one image tile."""
    original = tile_bgr.copy()
    original_copy = tile_bgr.copy()

    gray_image = cv2.cvtColor(tile_bgr, cv2.COLOR_BGR2GRAY)
    gray_image = gray_image.astype(np.float32) / 255.0

    sigma = 21
    kernel_size = 2 * math.ceil(2 * sigma) + 1

    blur = cv2.GaussianBlur(
        gray_image,
        (kernel_size, kernel_size),
        sigma
    )

    # Preserve supplied background-subtraction logic.
    gray_image = cv2.subtract(gray_image, blur)

    sobelx = cv2.Sobel(gray_image, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(gray_image, cv2.CV_64F, 0, 1, ksize=3)

    mag = np.hypot(sobelx, sobely)
    ang = np.arctan2(sobely, sobelx)

    threshold = 4 * 1.3 * np.mean(mag)
    mag[mag < threshold] = 0

    mag = orientated_non_max_suppression(mag, ang)
    mag[mag > 0] = 255
    mag = mag.astype(np.uint8)

    morph_kernel = np.ones((5, 5), np.uint8)
    result = cv2.morphologyEx(
        mag,
        cv2.MORPH_CLOSE,
        morph_kernel
    )

    contours, _ = cv2.findContours(
        result,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    h, w = tile_bgr.shape[:2]
    image_area = h * w

    # Structural mode is intentionally stricter about tiny isolated blobs.
    if mode == "sensitive":
        min_area = max(5, int(image_area * 0.000003))
        min_length = max(5, int(min(h, w) * 0.004))
    elif mode == "structural":
        min_area = max(18, int(image_area * 0.000012))
        min_length = max(12, int(min(h, w) * 0.008))
    else:  # standard
        min_area = max(10, int(image_area * 0.000007))
        min_length = max(8, int(min(h, w) * 0.006))

    largest_length = 0
    largest_width = 0
    total_area = 0
    accepted = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        x, y, bw, bh = cv2.boundingRect(cnt)

        length = max(bw, bh)
        width = min(bw, bh)
        aspect_ratio = length / max(width, 1)

        if area < min_area:
            continue

        if length < min_length:
            continue

        # Remove small, compact dot-like noise while preserving elongated cracks.
        if aspect_ratio < 2.0 and length < min_length * 2.5:
            continue

        accepted.append((cnt, x, y, bw, bh, area, length, width))
        total_area += area
        largest_length = max(largest_length, length)
        largest_width = max(largest_width, width)

        # Blue bounding rectangle.
        cv2.rectangle(
            original,
            (x, y),
            (x + bw, y + bh),
            (255, 0, 0),
            2
        )

    # Red crack highlighting only for accepted crack candidates.
    clean_mask = np.zeros_like(result)
    for item in accepted:
        cnt = item[0]
        cv2.drawContours(clean_mask, [cnt], -1, 255, thickness=cv2.FILLED)

    original[clean_mask == 255] = (0, 0, 255)

    px = float(pixels_per_cm)
    length_cm = largest_length / px
    width_cm = largest_width / px
    area_cm2 = total_area / (px ** 2)

    return {
        "original": original_copy,
        "detected": original,
        "length_cm": length_cm,
        "width_cm": width_cm,
        "area_cm2": area_cm2,
        "accepted_count": len(accepted),
        "mask": clean_mask,
    }


def _iter_tiles(image, tile_size=640, overlap=80):
    """Yield overlapping tiles with their top-left coordinates."""
    h, w = image.shape[:2]

    if tile_size <= 0:
        raise ValueError("tile_size must be positive.")

    stride = max(1, tile_size - overlap)

    ys = list(range(0, max(1, h - tile_size + 1), stride))
    xs = list(range(0, max(1, w - tile_size + 1), stride))

    if not ys or ys[-1] + tile_size < h:
        ys.append(max(0, h - tile_size))
    if not xs or xs[-1] + tile_size < w:
        xs.append(max(0, w - tile_size))

    seen = set()
    for y in ys:
        for x in xs:
            key = (x, y)
            if key in seen:
                continue
            seen.add(key)

            tile = image[y:min(y + tile_size, h), x:min(x + tile_size, w)]
            yield x, y, tile


def detect_crack(
    image_path,
    pixels_per_cm=100.0,
    mode="structural",
    tile_size=640,
    overlap=80,
    use_tiling=True,
):
    """
    Large-structure crack detection.

    The supplied OpenCV pipeline remains the core detector. For large images,
    overlapping tiles are processed independently and merged into one output.

    mode:
      sensitive  - keeps more candidates
      standard   - balanced
      structural - removes more tiny isolated/dot-like noise
    """
    original = cv2.imread(image_path)
    if original is None:
        raise ValueError("Image not found or OpenCV could not decode it.")

    if original.shape[0] < 10 or original.shape[1] < 10:
        raise ValueError("Image is too small for processing.")

    px = float(pixels_per_cm)
    if px <= 0:
        raise ValueError("Pixels per centimeter must be greater than zero.")

    h, w = original.shape[:2]

    # For normal/small images, process the whole image exactly once.
    should_tile = use_tiling and (max(h, w) > tile_size * 1.15)

    if not should_tile:
        result = _detect_on_tile(
            original,
            pixels_per_cm=px,
            mode=mode
        )
        detected = result["detected"]
        length_cm = result["length_cm"]
        width_cm = result["width_cm"]
        area_cm2 = result["area_cm2"]
        crack_count = result["accepted_count"]
    else:
        detected = original.copy()

        # Accumulate a global mask so red highlighting is applied cleanly once.
        global_mask = np.zeros((h, w), dtype=np.uint8)

        # Store global boxes and measurements.
        boxes = []
        total_area_px = 0.0
        largest_length_px = 0
        largest_width_px = 0

        for x0, y0, tile in _iter_tiles(
            original,
            tile_size=tile_size,
            overlap=overlap
        ):
            tile_result = _detect_on_tile(
                tile,
                pixels_per_cm=px,
                mode=mode
            )

            tile_mask = tile_result["mask"]
            th, tw = tile_mask.shape[:2]

            # Merge mask back into the full-resolution image.
            region = global_mask[y0:y0 + th, x0:x0 + tw]
            np.maximum(region, tile_mask, out=region)

            contours, _ = cv2.findContours(
                tile_mask,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area <= 0:
                    continue

                tx, ty, bw, bh = cv2.boundingRect(cnt)
                length = max(bw, bh)
                width = min(bw, bh)

                boxes.append((x0 + tx, y0 + ty, bw, bh))
                total_area_px += area
                largest_length_px = max(largest_length_px, length)
                largest_width_px = max(largest_width_px, width)

        # Draw boxes after all tiles are processed.
        for x, y, bw, bh in boxes:
            cv2.rectangle(
                detected,
                (x, y),
                (x + bw, y + bh),
                (255, 0, 0),
                2
            )

        detected[global_mask == 255] = (0, 0, 255)

        length_cm = largest_length_px / px
        width_cm = largest_width_px / px
        area_cm2 = total_area_px / (px ** 2)
        crack_count = len(boxes)

    if crack_count == 0:
        severity = "NO SIGNIFICANT CRACK"
        severity_message = (
            "No significant crack candidate was detected after structural "
            "noise filtering."
        )
    elif width_cm < 0.30:
        severity = "MINOR"
        severity_message = "Small crack detected. Continue monitoring."
    elif width_cm < 1.00:
        severity = "MODERATE"
        severity_message = (
            "Moderate crack detected. Structural inspection is recommended."
        )
    else:
        severity = "SEVERE"
        severity_message = (
            "Significant crack detected. Professional structural assessment "
            "is recommended."
        )

    return {
        "original": original,
        "detected": detected,
        "length_cm": round(float(length_cm), 2),
        "width_cm": round(float(width_cm), 2),
        "area_cm2": round(float(area_cm2), 2),
        "severity": severity,
        "severity_message": severity_message,
        "crack_count": int(crack_count),
        "mode": mode,
        "tiled": bool(should_tile),
        "tile_size": tile_size,
        "overlap": overlap,
    }


def save_image(image, output_path):
    if not cv2.imwrite(output_path, image):
        raise ValueError("Could not save processed image.")
