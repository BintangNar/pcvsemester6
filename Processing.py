import numpy as np

def convert_hsv(bgr_array):
    img = bgr_array.astype(np.float32) / 255.0
    b, g, r = img[:,:,0], img[:,:,1], img[:,:,2]

    v = np.max(img, axis=2)
    m = np.min(img, axis=2)
    delta = v - m

    # Saturation
    s = np.zeros_like(v)
    s[v != 0] = delta[v != 0] / v[v != 0]

    # Hue
    h = np.zeros_like(v)
    idx = (delta != 0)

    mask_r = idx & (v == r)
    h[mask_r] = 60 * ((g[mask_r] - b[mask_r]) / delta[mask_r])

    mask_g = idx & (v == g)
    h[mask_g] = 60 * (2 + (b[mask_g] - r[mask_g]) / delta[mask_g])

    mask_b = idx & (v == b)
    h[mask_b] = 60 * (4 + (r[mask_b] - g[mask_b]) / delta[mask_b])

    h[h < 0] += 360

    h_final = (h / 2).astype(np.uint8)
    s_final = (s * 255).astype(np.uint8)
    v_final = (v * 255).astype(np.uint8)

    return np.stack([h_final, s_final, v_final], axis=2)


def mask(image, low, high):
    result = (
        (image[:,:,0] >= low[0]) & (image[:,:,0] <= high[0]) &
        (image[:,:,1] >= low[1]) & (image[:,:,1] <= high[1]) &
        (image[:,:,2] >= low[2]) & (image[:,:,2] <= high[2])
    )
    return (result * 255).astype(np.uint8)


def mask_dual(image, low1, high1, low2, high2):
    m1 = (
        (image[:,:,0] >= low1[0]) & (image[:,:,0] <= high1[0]) &
        (image[:,:,1] >= low1[1]) & (image[:,:,1] <= high1[1]) &
        (image[:,:,2] >= low1[2]) & (image[:,:,2] <= high1[2])
    )
    m2 = (
        (image[:,:,0] >= low2[0]) & (image[:,:,0] <= high2[0]) &
        (image[:,:,1] >= low2[1]) & (image[:,:,1] <= high2[1]) &
        (image[:,:,2] >= low2[2]) & (image[:,:,2] <= high2[2])
    )
    return ((m1 | m2) * 255).astype(np.uint8)


def _sliding_window_op(image, size, op):
    img_h, img_w = image.shape[:2]
    pad = size // 2

    if image.ndim == 3:
        padded = np.pad(image, ((pad, pad), (pad, pad), (0, 0)), mode='edge')
    else:
        padded = np.pad(image, ((pad, pad), (pad, pad)), mode='edge')

    # sliding_window_view: shape (img_h, img_w, size, size)
    windows = np.lib.stride_tricks.sliding_window_view(padded, (size, size))
    # windows shape is (img_h, img_w, size, size) for 2-D input
    flat = windows.reshape(img_h, img_w, -1)
    return op(flat, axis=2).astype(np.uint8)


def median_filter(image, size=3):
    return _sliding_window_op(image, size, np.median)


def dilation(image, size=3):
    return _sliding_window_op(image, size, np.max)


def erosion(image, size=3):
    return _sliding_window_op(image, size, np.min)

erotion = erosion