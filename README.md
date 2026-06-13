# Mage Battle — Hand Gesture Controlled Game

## Identity
**NAMA** : Bintang Narindra Putra Pratama
**NRP**  : 5024231038

This project was developed to fulfill the requirements of the Computer Vision course taught by Arta Kusuma Hernanda, B.S., M.S.
## Description

Mage Battle is a real-time webcam-based game where the player controls a mage character using hand gestures detected through a webcam. No keyboard or mouse is needed during gameplay. The left hand controls where the player aims, while the right hand selects and casts spells by holding up a number of fingers. Enemies march down the screen in fixed lanes and the player must defeat them before they reach the bottom.

The image processing pipeline is built from scratch using NumPy — no OpenCV pixel-level processing functions (such as `cvtColor`, `dilate`, `erode`, or `inRange`) are used. All color conversion, masking, and morphological operations are implemented manually.

---

## Game Features

- **Dual hand control** — left hand aims the crosshair, right hand selects the spell
- **5 unique spells** mapped to finger count (1–5)
  - 1 Finger — Fireball: medium damage, fast projectile
  - 2 Fingers — Heal: instantly restores player HP, no projectile
  - 3 Fingers — Ice Shard: light damage, very fast projectile
  - 4 Fingers — Thunder: heavy damage projectile
  - 5 Fingers — Void Blast: massive damage, slower projectile
- **4 enemy types** — Goblin, Orc, Wraith, and Dragon, each with different HP, speed, and damage
- **Particle effects** on spell cast, impact, and player hits
- **Floating damage numbers** shown on every hit and heal
- **Spell palette HUD** at the bottom showing all spells, with the active one highlighted
- **HP bar and score** displayed at the top
- **Game Over screen** with final score, restart (R) and quit (Q) options
- **Automatic spell firing** on cooldown while a gesture is held — no button press needed

---

## Tools / Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3 |
| Webcam capture & drawing | OpenCV (`cv2`) |
| Numerical computation | NumPy |
| Contour & defect analysis | OpenCV (`findContours`, `convexityDefects`) |
| HSV conversion | Manual NumPy implementation |
| Morphological ops | Manual NumPy stride-tricks implementation |
| Skin masking | Manual dual-range HSV threshold |
| Position smoothing | Exponential Moving Average (EMA) |
| Finger count smoothing | Majority vote over sliding window |

---

## Program Flow

```
Game.py
  │
  ├─ Reads webcam frame
  ├─ Flips frame horizontally (mirror)
  ├─ Calls detect_hands(frame)  ──────────────────────────────┐
  │                                                           │
  │   Capture.py :: detect_hands()                           │
  │     ├─ Crops left ROI (bottom-left)                      │
  │     ├─ Crops right ROI (bottom-right)                    │
  │     ├─ Calls process_roi_mask() on each ROI              │
  │     │     ├─ Processing.py :: convert_hsv()              │
  │     │     │     └─ Manual BGR → HSV via NumPy            │
  │     │     ├─ Processing.py :: mask_dual()                │
  │     │     │     └─ Two HSV ranges OR-ed for skin tones   │
  │     │     ├─ Processing.py :: median_filter()            │
  │     │     ├─ Processing.py :: dilation() + erosion()     │
  │     │     │     └─ Close (fill holes) + Open (remove     │
  │     │     │        stray blobs) via sliding_window_view  │
  │     │     └─ Returns cleaned binary mask                 │
  │     ├─ get_best_contour() on each mask                   │
  │     │     └─ Finds largest valid hand-shaped blob        │
  │     ├─ LEFT: get_palm_center() → smooth_position() (EMA) │
  │     └─ RIGHT: count_fingers() via convexity defects      │
  │           └─ Majority vote smoothing over 5 frames       │
  │                                                           │
  ├─ Returns: left_pos, num_fingers, debug_info  ────────────┘
  │
  ├─ Maps left_pos → crosshair (cx, cy) on full frame
  ├─ Maps num_fingers → active spell (1–5)
  │
  ├─ Game Logic
  │     ├─ Spawn enemies on interval
  │     ├─ Cast spell toward crosshair (on cooldown)
  │     │     ├─ Spell 2 (Heal): apply HP directly, no projectile
  │     │     └─ Others: create Projectile aimed at crosshair
  │     ├─ Update all enemies (march downward)
  │     ├─ Update all projectiles (move toward target)
  │     ├─ Collision detection: projectile hits enemy
  │     ├─ Enemy reach check: enemy hits player
  │     ├─ Update particles and floating texts
  │     └─ Check game over (HP ≤ 0)
  │
  └─ Draw everything onto frame and display
```

---

## Consequence of Using Manual NumPy Calculation Instead of Built-in OpenCV Functions

The project deliberately avoids OpenCV's pixel-processing functions (`cv2.cvtColor`, `cv2.inRange`, `cv2.dilate`, `cv2.erode`, `cv2.medianBlur`) and reimplements them in pure NumPy. This has several practical consequences:

**Performance**
OpenCV's built-in functions are implemented in optimized C++ with SIMD (vectorized CPU instructions) and multithreading. The NumPy implementations here are slower — particularly the morphological operations, which use `np.lib.stride_tricks.sliding_window_view` to avoid Python loops but still run entirely on the Python/NumPy layer. On a typical CPU this is fast enough for real-time use with small ROIs (300×300), but would struggle with full-resolution processing.

**Accuracy**
The manual HSV conversion matches OpenCV's formula exactly (H scaled to 0–180, S and V scaled to 0–255), so masking results are consistent with what OpenCV would produce. However, floating-point rounding in intermediate steps can cause very minor differences at edge pixels.

**Morphological kernel shape**
OpenCV's `dilate`/`erode` default to a cross-shaped structuring element. The NumPy implementation here uses a full square kernel (all ones). This makes dilation slightly more aggressive — useful for filling finger gaps in the mask, but means thresholds tuned here would not transfer directly to OpenCV's defaults.

**Portability and maintainability**
Because the processing has no hidden OpenCV defaults, every parameter is explicit and visible in the code. This makes the pipeline easier to understand and modify, at the cost of more code to maintain.

---

## How to Run

**Requirements**

```
Python 3.8+
opencv-python
numpy
```

Install dependencies:

```bash
pip install opencv-python numpy
```

**File structure**

All four files must be in the same folder:

```
project/
├── Game.py
├── Capture.py
├── Processing.py
└── README.md
```

**Run the game**

```bash
python Game.py
```

**Controls**

| Input | Action |
|---|---|
| Left hand in left ROI box | Moves the crosshair |
| Right hand — 1 finger | Select & cast Fireball |
| Right hand — 2 fingers | Select & cast Heal |
| Right hand — 3 fingers | Select & cast Ice Shard |
| Right hand — 4 fingers | Select & cast Thunder |
| Right hand — 5 fingers | Select & cast Void Blast |
| Q key | Quit |
| R key | Restart (also works on Game Over screen) |

**Tips for best detection**
- Use in a well-lit environment with a plain background behind your hands
- Keep your hands inside the green (left) and red (right) ROI boxes shown on screen
- Hold gestures steady for at least half a second for the smoothing to stabilize
- If skin detection is poor, adjust the HSV thresholds in `process_roi_mask()` inside `Capture.py`

---

## Documentation
