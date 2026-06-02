import cv2 as cv
import numpy as np
from collections import deque
import Processing as proc

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SMOOTH_WINDOW  = 5
POSITION_ALPHA = 0.35

# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------
_right_history   = deque(maxlen=SMOOTH_WINDOW)
_left_pos_smooth = None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def smooth_count(history, new_value):
    history.append(new_value)
    return max(set(history), key=history.count)

def get_palm_center(bounding_box):
    x, y, w, h = bounding_box
    return (x + w / 2.0, y + h / 2.0)

def smooth_position(new_pos):
    global _left_pos_smooth
    if _left_pos_smooth is None:
        _left_pos_smooth = new_pos
    else:
        ax = POSITION_ALPHA * new_pos[0] + (1 - POSITION_ALPHA) * _left_pos_smooth[0]
        ay = POSITION_ALPHA * new_pos[1] + (1 - POSITION_ALPHA) * _left_pos_smooth[1]
        _left_pos_smooth = (ax, ay)
    return _left_pos_smooth

# ---------------------------------------------------------------------------
# Contour selection
# ---------------------------------------------------------------------------
def get_best_contour(img, roi_offset_x, roi_offset_y):
    contours, _ = cv.findContours(img, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    for cnt in sorted(contours, key=cv.contourArea, reverse=True):
        area = cv.contourArea(cnt)
        if area < 2000:
            continue
        x, y, w, h = cv.boundingRect(cnt)
        if float(w) / h > 2.5 or float(h) / w > 4.0:
            continue
        hull         = cv.convexHull(cnt)
        hull_area    = cv.contourArea(hull)
        hull_indices = cv.convexHull(cnt, returnPoints=False)
        if hull_area > 0 and float(area) / hull_area < 0.35:
            continue
        return {
            "contours":     cnt + np.array([roi_offset_x, roi_offset_y]),
            "bounding_box": (x + roi_offset_x, y + roi_offset_y, w, h),
            "hull":         hull + np.array([roi_offset_x, roi_offset_y]),
            "hull_indices": hull_indices,
        }
    return None

# ---------------------------------------------------------------------------
# Finger counting
# ---------------------------------------------------------------------------
def count_fingers(contour, hull_indices):
    if hull_indices is None or len(hull_indices) < 3:
        return 0
    defects = cv.convexityDefects(contour, hull_indices)
    if defects is None:
        return 0
    count = 0
    for i in range(defects.shape[0]):
        s, e, f, d = defects[i, 0]
        start = tuple(contour[s][0])
        end   = tuple(contour[e][0])
        far   = tuple(contour[f][0])
        a = np.sqrt((end[0]-start[0])**2 + (end[1]-start[1])**2)
        b = np.sqrt((far[0]-start[0])**2  + (far[1]-start[1])**2)
        c = np.sqrt((far[0]-end[0])**2    + (far[1]-end[1])**2)
        denom = 2 * b * c
        if denom == 0:
            continue
        cos_val = np.clip((b**2 + c**2 - a**2) / denom, -1.0, 1.0)
        angle   = np.degrees(np.arccos(cos_val))
        if angle <= 85 and d / 256.0 > 20:
            count += 1
    return count + 1 if count > 0 else 0

# ---------------------------------------------------------------------------
# Skin mask
# ---------------------------------------------------------------------------
def process_roi_mask(roi_frame):
    hsv_roi  = proc.convert_hsv(roi_frame)
    lower1   = np.array([0,  30,  60]);  upper1 = np.array([8,  160, 255])
    lower2   = np.array([8,  25,  50]);  upper2 = np.array([20, 160, 255])
    raw_mask = proc.mask_dual(hsv_roi, lower1, upper1, lower2, upper2)
    filtered = proc.median_filter(raw_mask, size=5)
    closed   = proc.erosion(proc.dilation(filtered, 9), 9)
    opened   = proc.dilation(proc.erosion(closed, 3), 3)
    return raw_mask, opened

# ---------------------------------------------------------------------------
# Public API  –  called once per frame from Game.py
# ---------------------------------------------------------------------------
def detect_hands(frame):
    """
    Process one BGR frame and return:
        left_pos    : (cx, cy) floats in frame coords, or None
        num_fingers : int 0-5, or None
        debug_info  : dict with bounding boxes / hulls for optional HUD drawing
    """
    global _left_pos_smooth

    f_h, f_w = frame.shape[:2]
    roi_w, roi_h = 240, 240

    left_roi_x  = 20;            left_roi_y  = f_h - roi_h - 40
    right_roi_x = f_w - roi_w - 20; right_roi_y = f_h - roi_h - 40

    left_roi  = frame[left_roi_y  : left_roi_y  + roi_h,
                      left_roi_x  : left_roi_x  + roi_w]
    right_roi = frame[right_roi_y : right_roi_y + roi_h,
                      right_roi_x : right_roi_x + roi_w]

    _, left_opened  = process_roi_mask(left_roi)
    _, right_opened = process_roi_mask(right_roi)

    left_hand  = get_best_contour(left_opened,  left_roi_x,  left_roi_y)
    right_hand = get_best_contour(right_opened, right_roi_x, right_roi_y)

    left_pos = None
    if left_hand:
        raw_pos  = get_palm_center(left_hand["bounding_box"])
        left_pos = smooth_position(raw_pos)
    else:
        _left_pos_smooth = None

    num_fingers = None
    if right_hand:
        cnt_local   = right_hand["contours"] - np.array([right_roi_x, right_roi_y])
        raw_count   = count_fingers(cnt_local, right_hand["hull_indices"])
        num_fingers = smooth_count(_right_history, raw_count)
    else:
        _right_history.clear()

    debug_info = {
        "left_hand":   left_hand,
        "right_hand":  right_hand,
        "left_opened": left_opened,
        "right_opened":right_opened,
        "roi": {
            "left":  (left_roi_x,  left_roi_y,  roi_w, roi_h),
            "right": (right_roi_x, right_roi_y, roi_w, roi_h),
        }
    }

    return left_pos, num_fingers, debug_info