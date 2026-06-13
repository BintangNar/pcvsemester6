import cv2 as cv
import numpy as np
import random
import time
import Capture as cap_module

SPELLS = {
    1: {"name": "Fireball",      "color": (0,  100, 255), "damage": 35, "speed": 14, "radius": 12},
    2: {"name": "Heal",          "color": (0,  255, 120), "damage": -30,"speed": 0,  "radius": 0},
    3: {"name": "Ice Shard",     "color": (255,200,  50), "damage": 25, "speed": 18, "radius": 9},
    4: {"name": "Thunder",       "color": (0,  255, 255), "damage": 50, "speed": 20, "radius": 10},
    5: {"name": "Void Blast",    "color": (180,  0, 255), "damage": 70, "speed": 10, "radius": 16},
}

ENEMY_TYPES = [
    {"name": "Goblin",   "color": (0, 180,  50), "hp": 60,  "speed": 1.2, "damage": 10, "size": 22},
    {"name": "Orc",      "color": (0, 120, 200), "hp": 120, "speed": 0.7, "damage": 20, "size": 30},
    {"name": "Wraith",   "color": (180,  0, 180),"hp": 80,  "speed": 2.0, "damage": 15, "size": 18},
    {"name": "Dragon",   "color": (0,  50, 220), "hp": 200, "speed": 0.5, "damage": 35, "size": 38},
]

PLAYER_MAX_HP     = 100
CAST_COOLDOWN     = 1.00 
SPAWN_INTERVAL    = 4.0   
ENEMY_REACH       = 60     
PROJECTILE_LIMIT  = 20
CROSSHAIR_COLOR   = (0, 255, 180)


class Particle:
    __slots__ = ("x","y","vx","vy","color","life","max_life","radius")
    def __init__(self, x, y, color, count=8, spread=4.0, life=0.5):
        self.x, self.y = float(x), float(y)
        angle = random.uniform(0, 2*np.pi)
        spd   = random.uniform(1.0, spread)
        self.vx, self.vy = np.cos(angle)*spd, np.sin(angle)*spd
        self.color    = color
        self.life     = life
        self.max_life = life
        self.radius   = random.randint(2, 5)

    def update(self, dt):
        self.x   += self.vx
        self.y   += self.vy
        self.vy  += 0.15          
        self.life -= dt
        return self.life > 0

    def draw(self, frame):
        alpha  = max(0.0, self.life / self.max_life)
        col    = tuple(int(c * alpha) for c in self.color)
        r      = max(1, int(self.radius * alpha))
        cv.circle(frame, (int(self.x), int(self.y)), r, col, -1)

#  PROJECTILE
class Projectile:
    def __init__(self, x, y, tx, ty, spell_id):
        sp             = SPELLS[spell_id]
        self.x, self.y = float(x), float(y)
        self.spell_id  = spell_id
        self.color     = sp["color"]
        self.damage    = sp["damage"]
        self.radius    = sp["radius"]
        self.alive     = True
        # Direction toward crosshair
        dx, dy = tx - x, ty - y
        dist   = np.sqrt(dx*dx + dy*dy) or 1
        self.vx = dx/dist * sp["speed"]
        self.vy = dy/dist * sp["speed"]

    def update(self):
        self.x += self.vx
        self.y += self.vy

    def draw(self, frame):
        cv.circle(frame, (int(self.x), int(self.y)), self.radius, self.color, -1)
        # Glow ring
        cv.circle(frame, (int(self.x), int(self.y)), self.radius+3, self.color, 1)


#  ENEMY
class Enemy:
    _id = 0
    def __init__(self, frame_w, frame_h):
        Enemy._id  += 1
        self.id     = Enemy._id
        etype       = random.choice(ENEMY_TYPES)
        self.name   = etype["name"]
        self.color  = etype["color"]
        self.max_hp = etype["hp"]
        self.hp     = float(self.max_hp)
        self.speed  = etype["speed"]
        self.damage = etype["damage"]
        self.size   = etype["size"]
        # Spawn: random x across lane, top of screen
        num_lanes   = 5
        lane        = random.randint(0, num_lanes - 1)
        lane_w      = frame_w // num_lanes
        self.x      = float(lane * lane_w + lane_w // 2 + random.randint(-20, 20))
        self.y      = float(-self.size)
        self.alive  = True

    def update(self):
        self.y += self.speed

    def hit(self, damage):
        self.hp -= damage
        if self.hp <= 0:
            self.alive = False
            return True  
        return False

    def draw(self, frame):
        ix, iy = int(self.x), int(self.y)
        # Body
        cv.circle(frame, (ix, iy), self.size, self.color, -1)
        cv.circle(frame, (ix, iy), self.size, (255,255,255), 1)
        # Name
        cv.putText(frame, self.name, (ix - 25, iy - self.size - 6),
                   cv.FONT_HERSHEY_SIMPLEX, 0.38, (255,255,255), 1)
        # HP bar
        bar_w = self.size * 2
        filled = int(bar_w * max(0, self.hp / self.max_hp))
        cv.rectangle(frame, (ix - self.size, iy + self.size + 4),
                             (ix - self.size + bar_w, iy + self.size + 10), (60,60,60), -1)
        cv.rectangle(frame, (ix - self.size, iy + self.size + 4),
                             (ix - self.size + filled, iy + self.size + 10), (0,220,80), -1)

#  FLOATING TEXT
class FloatText:
    def __init__(self, x, y, text, color):
        self.x, self.y = float(x), float(y)
        self.text  = text
        self.color = color
        self.life  = 1.0

    def update(self, dt):
        self.y   -= 1.2
        self.life -= dt * 1.5
        return self.life > 0

    def draw(self, frame):
        alpha = max(0, self.life)
        col   = tuple(int(c * alpha) for c in self.color)
        cv.putText(frame, self.text, (int(self.x), int(self.y)),
                   cv.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)

#  HUD DRAWING HELPERS
def draw_hud(frame, player_hp, score, spell_id, num_fingers, frame_w, frame_h):
    #HP bar
    bar_x, bar_y, bar_w, bar_h = 20, 20, 220, 22
    hp_ratio = max(0.0, player_hp / PLAYER_MAX_HP)
    hp_color = (0,220,80) if hp_ratio > 0.5 else (0,180,255) if hp_ratio > 0.25 else (0,60,220)
    cv.rectangle(frame, (bar_x, bar_y), (bar_x+bar_w, bar_y+bar_h), (40,40,40), -1)
    cv.rectangle(frame, (bar_x, bar_y), (bar_x+int(bar_w*hp_ratio), bar_y+bar_h), hp_color, -1)
    cv.rectangle(frame, (bar_x, bar_y), (bar_x+bar_w, bar_y+bar_h), (200,200,200), 1)
    cv.putText(frame, f"HP {int(player_hp)}/{PLAYER_MAX_HP}",
               (bar_x+4, bar_y+16), cv.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)

    #Score
    cv.putText(frame, f"Score: {score}", (bar_x, bar_y + 45),
               cv.FONT_HERSHEY_SIMPLEX, 0.65, (255,240,100), 2)

    #Spell palette (bottom centre)
    palette_y = frame_h - 55
    total_w   = len(SPELLS) * 90
    start_x   = (frame_w - total_w) // 2

    for sid, sp in SPELLS.items():
        bx = start_x + (sid-1) * 90
        # Highlight active spell
        active = (sid == spell_id)
        bg_col = sp["color"] if active else (30, 30, 30)
        cv.rectangle(frame, (bx, palette_y), (bx+82, palette_y+44), bg_col, -1)
        cv.rectangle(frame, (bx, palette_y), (bx+82, palette_y+44),
                     (255,255,255) if active else (100,100,100), 2 if active else 1)
        cv.putText(frame, f"{sid}: {sp['name']}", (bx+4, palette_y+16),
                   cv.FONT_HERSHEY_SIMPLEX, 0.38, (255,255,255), 1)
        finger_dots = "o" * sid
        cv.putText(frame, finger_dots, (bx+4, palette_y+34),
                   cv.FONT_HERSHEY_SIMPLEX, 0.38, (200,200,200), 1)

    # Right-hand gesture hint
    hint = f"Fingers: {num_fingers if num_fingers is not None else '?'}"
    cv.putText(frame, hint, (frame_w - 160, 35),
               cv.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,255), 2)

def draw_crosshair(frame, cx, cy):
    size = 18
    gap  = 5
    col  = CROSSHAIR_COLOR
    t    = 2
    cv.line(frame, (cx-size, cy), (cx-gap, cy), col, t)
    cv.line(frame, (cx+gap,  cy), (cx+size, cy), col, t)
    cv.line(frame, (cx, cy-size), (cx, cy-gap),  col, t)
    cv.line(frame, (cx, cy+gap),  (cx, cy+size), col, t)
    cv.circle(frame, (cx, cy), 3, col, -1)

def draw_hand_debug(frame, debug_info, f_w, f_h):
    lx, ly, lw, lh = debug_info["roi"]["left"]
    rx, ry, rw, rh = debug_info["roi"]["right"]
    cv.rectangle(frame, (lx,ly), (lx+lw, ly+lh), (0,180,0), 1)
    cv.rectangle(frame, (rx,ry), (rx+rw, ry+rh), (180,0,0), 1)

def draw_game_over(frame, score, f_w, f_h):
    overlay = frame.copy()
    cv.rectangle(overlay, (0,0), (f_w, f_h), (0,0,0), -1)
    cv.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
    cv.putText(frame, "GAME OVER", (f_w//2 - 140, f_h//2 - 30),
               cv.FONT_HERSHEY_DUPLEX, 2.0, (0,60,220), 4)
    cv.putText(frame, f"Final Score: {score}", (f_w//2 - 110, f_h//2 + 30),
               cv.FONT_HERSHEY_SIMPLEX, 1.0, (255,240,100), 2)
    cv.putText(frame, "Press R to restart or Q to quit",
               (f_w//2 - 180, f_h//2 + 80),
               cv.FONT_HERSHEY_SIMPLEX, 0.65, (200,200,200), 1)

#  GAME STATE
class GameState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.player_hp    = float(PLAYER_MAX_HP)
        self.score        = 0
        self.enemies      = []
        self.projectiles  = []
        self.particles    = []
        self.float_texts  = []
        self.last_cast    = 0.0
        self.last_spawn   = 0.0
        self.game_over    = False

#  MAIN
def main():
    cap = cv.VideoCapture(0)
    if not cap.isOpened():
        print("Gagal membuka kamera")
        return

    state       = GameState()
    prev_time   = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame    = np.ascontiguousarray(np.flip(frame, axis=1))
        f_h, f_w = frame.shape[:2]
        now      = time.time()
        dt       = now - prev_time
        prev_time = now

        #Hand detection
        left_pos, num_fingers, debug_info = cap_module.detect_hands(frame)
        combined_mask = np.hstack((debug_info["left_opened"], debug_info["right_opened"]))
        cv.imshow("Masks (Left | Right)", combined_mask)
        # Draw contours on a small debug view
        debug_frame = frame.copy()
        if debug_info["left_hand"]:
            cv.drawContours(debug_frame, [debug_info["left_hand"]["hull"]], -1, (0,255,255), 2)
        if debug_info["right_hand"]:
            cv.drawContours(debug_frame, [debug_info["right_hand"]["hull"]], -1, (0,255,255), 2)
        cv.imshow("Contours", debug_frame)
        combined_mask = np.hstack((debug_info["left_opened"], debug_info["right_opened"]))
        cv.imshow("Masks (Left | Right)", combined_mask)

        # Map left hand position to full frame crosshair
        if left_pos is not None:
            roi_lx, roi_ly, roi_lw, roi_lh = debug_info["roi"]["left"]
            # Remap from ROI coords to full frame
            norm_x = (left_pos[0] - roi_lx) / roi_lw   
            norm_y = (left_pos[1] - roi_ly) / roi_lh
            cx = int(np.clip(norm_x * f_w, 0, f_w - 1))
            cy = int(np.clip(norm_y * f_h, 0, f_h - 1))
            crosshair = (cx, cy)
        else:
            crosshair = (f_w // 2, f_h // 2)   # default centre

        # Spell selected = num_fingers (1-5), fallback to last valid
        spell_id = num_fingers if (num_fingers and 1 <= num_fingers <= 5) else 1

        # GAME OVER screen 
        if state.game_over:
            draw_game_over(frame, state.score, f_w, f_h)
            cv.imshow("Mage Battle", frame)
            key = cv.waitKey(1) & 0xFF
            if key == ord('r'):
                state.reset()
            elif key == ord('q'):
                break
            continue

        # Darken frame slightly so game elements pop 
        frame = (frame * 0.55).astype(np.uint8)

        #Spawn enemies 
        if now - state.last_spawn > SPAWN_INTERVAL:
            state.enemies.append(Enemy(f_w, f_h))
            state.last_spawn = now

        # Cast spell: gesture held = fire each CAST_COOLDOWN
        if (num_fingers and 1 <= num_fingers <= 5
                and now - state.last_cast > CAST_COOLDOWN
                and len(state.projectiles) < PROJECTILE_LIMIT):

            sp = SPELLS[spell_id]
            if spell_id == 2:   # Heal
                heal_amt = abs(sp["damage"])
                state.player_hp = min(PLAYER_MAX_HP, state.player_hp + heal_amt)
                state.float_texts.append(
                    FloatText(f_w//2, f_h//2 - 40, f"+{heal_amt} HP", (0,255,120)))
                # Healing particles around centre
                for _ in range(12):
                    state.particles.append(
                        Particle(f_w//2, f_h//2, (0,255,120), spread=5, life=0.7))
            else:
                # Fire from bottom centre toward crosshair
                px, py = f_w//2, f_h - 80
                state.projectiles.append(
                    Projectile(px, py, crosshair[0], crosshair[1], spell_id))
                # Muzzle particles
                for _ in range(8):
                    state.particles.append(
                        Particle(px, py, sp["color"], spread=3, life=0.4))

            state.last_cast = now

        # Update enemies 
        for en in state.enemies[:]:
            en.update()
            if en.y > f_h - ENEMY_REACH:
                state.player_hp -= en.damage
                state.float_texts.append(
                    FloatText(en.x, f_h - 80, f"-{en.damage}", (0,60,220)))
                state.enemies.remove(en)
                # Hit flash particles
                for _ in range(10):
                    state.particles.append(
                        Particle(f_w//2, f_h - 80, (0,60,220), spread=6, life=0.5))

        # Update projectiles + collision
        for proj in state.projectiles[:]:
            proj.update()
            # Off-screen
            if (proj.x < -20 or proj.x > f_w+20
                    or proj.y < -20 or proj.y > f_h+20):
                state.projectiles.remove(proj)
                continue
            # Check hits
            hit = False
            for en in state.enemies[:]:
                dx = proj.x - en.x
                dy = proj.y - en.y
                if np.sqrt(dx*dx + dy*dy) < (proj.radius + en.size):
                    killed = en.hit(proj.damage)
                    # Impact particles
                    for _ in range(10):
                        state.particles.append(
                            Particle(proj.x, proj.y, proj.color, spread=5, life=0.5))
                    if killed:
                        state.score += 10
                        state.float_texts.append(
                            FloatText(en.x, en.y - 20, "+10", (255,240,100)))
                        state.enemies.remove(en)
                    else:
                        state.float_texts.append(
                            FloatText(en.x, en.y - 20, f"-{proj.damage}", proj.color))
                    hit = True
                    break
            if hit and proj in state.projectiles:
                state.projectiles.remove(proj)

        #Update particles & float texts
        state.particles  = [p for p in state.particles  if p.update(dt)]
        state.float_texts= [t for t in state.float_texts if t.update(dt)]

        #Check game over
        if state.player_hp <= 0:
            state.player_hp = 0
            state.game_over  = True

        #Draw everything
        px_icon = f_w // 2
        py_icon = f_h - 60
        cv.circle(frame, (px_icon, py_icon), 22, (60, 60, 180), -1)
        cv.circle(frame, (px_icon, py_icon), 22, (180,180,255), 2)
        cv.putText(frame, "M", (px_icon-8, py_icon+7),
                   cv.FONT_HERSHEY_DUPLEX, 0.8, (255,255,255), 2)

        for en   in state.enemies:      en.draw(frame)
        for proj in state.projectiles:  proj.draw(frame)
        for p    in state.particles:    p.draw(frame)
        for ft   in state.float_texts:  ft.draw(frame)

        draw_crosshair(frame, crosshair[0], crosshair[1])
        draw_hand_debug(frame, debug_info, f_w, f_h)
        draw_hud(frame, state.player_hp, state.score, spell_id, num_fingers, f_w, f_h)

        #Spell name flash when casting
        if now - state.last_cast < 0.25:
            sp  = SPELLS[spell_id]
            cv.putText(frame, sp["name"],
                       (f_w//2 - 60, f_h - 95),
                       cv.FONT_HERSHEY_SIMPLEX, 0.9, sp["color"], 2)

        cv.imshow("Mage Battle", frame)

        key = cv.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r'):
            state.reset()

    cap.release()
    cv.destroyAllWindows()


if __name__ == "__main__":
    main()