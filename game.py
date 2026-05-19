import pygame
import sys
import os
import math
import struct
import random

# ── Constants ─────────────────────────────────────────────────────────────────
SCREEN_W, SCREEN_H = 800, 400
GROUND_Y = 320
HITBOX_SHRINK = 5
GRAVITY = 0.7
JUMP_VY = -14.0
FPS = 60

# Colors
COL_SKY        = (25,  30,  45)
COL_GROUND     = (55,  55,  60)
COL_ROAD_LINE  = (200, 200, 200)
COL_PLAYER     = (0,   255, 220)   # neon cyan
COL_WHITE      = (255, 255, 255)
COL_DANFO      = (255, 200, 0)
COL_FOOD_STAND = (225, 110, 30)
COL_PEDESTRIAN = (240, 200, 150)
COL_BUILDING   = (35,  40,  55)
COL_WIN_LIT    = (255, 230, 150)
COL_WIN_UNLIT  = (40,  50,  70)

# States
MENU      = "MENU"
PLAYING   = "PLAYING"
GAME_OVER = "GAME_OVER"

# Obstacle type tags
T_DANFO = "danfo"
T_FOOD  = "food"
T_PED   = "ped"


# ── Sound Engine ──────────────────────────────────────────────────────────────
class SoundEngine:
    def __init__(self):
        self._jump  = None
        self._crash = None
        try:
            self._jump  = self._tone(520, 100, 0.30)
            self._crash = self._tone(140, 320, 0.40)
        except Exception:
            pass

    def _tone(self, freq, ms, vol):
        rate = 44100
        n = int(rate * ms / 1000)
        buf = bytearray(n * 4)  # stereo 16-bit PCM = 4 bytes/frame
        for i in range(n):
            env = 1.0 - i / n   # linear fade-out eliminates click
            v = int(math.sin(2 * math.pi * freq * i / rate) * 32767 * vol * env)
            v = max(-32768, min(32767, v))
            struct.pack_into('<hh', buf, i * 4, v, v)
        return pygame.mixer.Sound(buffer=bytes(buf))

    def play_jump(self):
        if self._jump:
            try:
                self._jump.play()
            except Exception:
                pass

    def play_crash(self):
        if self._crash:
            try:
                self._crash.play()
            except Exception:
                pass


# ── Score Tracker ─────────────────────────────────────────────────────────────
class ScoreTracker:
    _SAVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "highscore.txt")

    def __init__(self):
        self.score = 0
        self.best  = self._load()

    def _load(self):
        try:
            with open(self._SAVE) as f:
                return int(f.read().strip())
        except Exception:
            return 0

    def _save(self):
        try:
            with open(self._SAVE, "w") as f:
                f.write(str(self.best))
        except Exception:
            pass

    def tick(self):
        self.score += 1
        if self.score > self.best:
            self.best = self.score
            self._save()

    def reset(self):
        self.score = 0


# ── Player ────────────────────────────────────────────────────────────────────
class Player:
    W       = 32
    H_STAND = 32
    H_DUCK  = 16
    X       = 100

    def __init__(self):
        self.ducking   = False
        self.vy        = 0.0
        self.on_ground = True
        self._y        = float(GROUND_Y - self.H_STAND)
        self.rect      = pygame.Rect(self.X, int(self._y), self.W, self.H_STAND)

    def jump(self):
        if self.on_ground and not self.ducking:
            self.vy        = JUMP_VY
            self.on_ground = False

    def set_duck(self, want):
        if not self.on_ground:
            return          # no mid-air crouch
        if want == self.ducking:
            return
        self.ducking   = want
        h              = self.H_DUCK if want else self.H_STAND
        self._y        = float(GROUND_Y - h)
        self.rect.height = h
        self.rect.y    = int(self._y)

    def update(self):
        if not self.on_ground:
            self.vy  += GRAVITY
            self._y  += self.vy
            land_y    = float(GROUND_Y - self.H_STAND)
            if self._y >= land_y:
                self._y        = land_y
                self.vy        = 0.0
                self.on_ground = True
        self.rect.height = self.H_DUCK if self.ducking else self.H_STAND
        self.rect.y      = int(self._y)

    def hitbox(self):
        return self.rect.inflate(-HITBOX_SHRINK * 2, -HITBOX_SHRINK * 2)

    def draw(self, surf):
        r = self.rect
        pygame.draw.rect(surf, COL_PLAYER, r)
        pygame.draw.rect(surf, COL_WHITE,  r, 2)
        # small "eye"
        pygame.draw.rect(surf, COL_WHITE, (r.right - 7, r.top + 4, 3, 3))


# ── Obstacle ──────────────────────────────────────────────────────────────────
class Obstacle:
    def __init__(self, kind):
        self.kind = kind
        if kind == T_DANFO:
            w, h = random.randint(80, 100), random.randint(65, 80)
            self.rect  = pygame.Rect(SCREEN_W, GROUND_Y - h, w, h)
            self.color = COL_DANFO
        elif kind == T_FOOD:
            w, h = random.randint(60, 80), random.randint(50, 58)
            self.rect  = pygame.Rect(SCREEN_W, GROUND_Y - 20 - h, w, h)
            self.color = COL_FOOD_STAND
        else:                                      # pedestrian
            w, h = random.randint(20, 26), random.randint(42, 55)
            self.rect  = pygame.Rect(SCREEN_W, GROUND_Y - h, w, h)
            self.color = COL_PEDESTRIAN
        self._fx = float(self.rect.x)

    def hitbox(self):
        return self.rect.inflate(-HITBOX_SHRINK * 2, -HITBOX_SHRINK * 2)

    def update(self, speed):
        self._fx    -= speed
        self.rect.x  = int(self._fx)

    def off_screen(self):
        return self.rect.right < 0

    def draw(self, surf):
        r = self.rect
        pygame.draw.rect(surf, self.color, r)

        if self.kind == T_DANFO:
            stripe_h = max(8, r.height // 6)
            pygame.draw.rect(surf, (200, 30, 30),
                             (r.x, r.bottom - stripe_h, r.width, stripe_h))
            win_h = max(10, r.height // 3)
            for wx in range(r.x + 6, r.right - 14, 16):
                pygame.draw.rect(surf, (60, 80, 100),
                                 (wx, r.top + 6, 10, win_h))

        elif self.kind == T_FOOD:
            # table legs from rect bottom down to GROUND_Y
            leg_h = GROUND_Y - r.bottom
            if leg_h > 0:
                pygame.draw.rect(surf, (180, 80, 20),
                                 (r.x + 6,          r.bottom, 5, leg_h))
                pygame.draw.rect(surf, (180, 80, 20),
                                 (r.right - 11,     r.bottom, 5, leg_h))
            # food items above the table surface
            for fx in range(r.x + 8, r.right - 6, 12):
                pygame.draw.circle(surf, (255, 180, 80), (fx, r.top - 5), 4)

        else:  # pedestrian
            head_r = r.width // 2
            pygame.draw.circle(surf, self.color,
                               (r.centerx, r.top - head_r), head_r)
            shirt_y = r.top + r.height // 3
            pygame.draw.rect(surf, (50, 80, 200),
                             (r.x, shirt_y, r.width, r.height // 4))


# ── Background ────────────────────────────────────────────────────────────────
class Background:
    _DASH_W   = 40
    _DASH_GAP = 30

    def __init__(self):
        self._sky    = self._bake_sky()
        self._offset = 0.0
        self._period = self._DASH_W + self._DASH_GAP

    def _bake_sky(self):
        surf = pygame.Surface((SCREEN_W, GROUND_Y))
        surf.fill(COL_SKY)
        rng = random.Random(42)          # fixed seed → deterministic cityscape
        x = 0
        while x < SCREEN_W + 30:
            bw = rng.randint(40, 90)
            bh = rng.randint(60, GROUND_Y - 20)
            by = GROUND_Y - bh
            pygame.draw.rect(surf, COL_BUILDING, (x, by, bw - 2, bh))
            for wy in range(by + 8, GROUND_Y - 10, 14):
                for wx in range(x + 5, x + bw - 10, 12):
                    col = COL_WIN_LIT if rng.random() > 0.4 else COL_WIN_UNLIT
                    pygame.draw.rect(surf, col, (wx, wy, 7, 8))
            x += bw + rng.randint(0, 10)
        return surf

    def update(self, speed):
        self._offset = (self._offset + speed) % self._period

    def draw(self, surf):
        surf.blit(self._sky, (0, 0))
        pygame.draw.rect(surf, COL_GROUND,
                         (0, GROUND_Y, SCREEN_W, SCREEN_H - GROUND_Y))
        # scrolling centre-line dashes
        dash_y = GROUND_Y + (SCREEN_H - GROUND_Y) // 2 - 1
        x = -self._offset
        while x < SCREEN_W:
            if x + self._DASH_W > 0:
                pygame.draw.rect(surf, COL_ROAD_LINE,
                                 (int(x), dash_y, self._DASH_W, 3))
            x += self._period


# ── Game ──────────────────────────────────────────────────────────────────────
class Game:
    def __init__(self):
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        self._screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Olé!")
        self._clock  = pygame.time.Clock()
        self._font_lg = pygame.font.SysFont("monospace", 48, bold=True)
        self._font_md = pygame.font.SysFont("monospace", 28, bold=True)
        self._font_sm = pygame.font.SysFont("monospace", 20)
        self._sound   = SoundEngine()
        self._scores  = ScoreTracker()
        self._bg      = Background()
        self._state   = MENU
        self._player    = None
        self._obstacles = []
        self._spawn_timer = 0
        self._speed       = 5.0

    # ── helpers ───────────────────────────────────────────────────────────────
    def _start_game(self):
        self._scores.reset()
        self._player    = Player()
        self._obstacles = []
        self._speed     = 5.0
        self._spawn_timer = 60        # 1-second head-start before first obstacle
        self._state     = PLAYING

    def _current_speed(self):
        return min(5.0 + self._scores.score * 0.004, 18.0)

    def _next_spawn(self):
        s  = self._scores.score
        lo = max(20, 45 - s // 50)
        hi = max(lo + 5, 120 - s // 30)
        return random.randint(lo, hi)

    # ── main loop ─────────────────────────────────────────────────────────────
    def run(self):
        while True:
            self._handle_events()
            self._update()
            self._draw()
            self._clock.tick(FPS)

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if self._state == MENU:
                    if event.key == pygame.K_SPACE:
                        self._start_game()
                elif self._state == PLAYING:
                    if event.key == pygame.K_SPACE:
                        self._player.jump()
                        self._sound.play_jump()
                elif self._state == GAME_OVER:
                    if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                        self._start_game()

    def _update(self):
        if self._state != PLAYING:
            return

        keys = pygame.key.get_pressed()
        self._player.set_duck(bool(keys[pygame.K_DOWN]))
        self._player.update()

        self._speed = self._current_speed()
        self._bg.update(self._speed)
        self._scores.tick()

        # spawn
        self._spawn_timer -= 1
        if self._spawn_timer <= 0:
            self._obstacles.append(Obstacle(random.choice([T_DANFO, T_FOOD, T_PED])))
            self._spawn_timer = self._next_spawn()

        # move + collision
        p_hb = self._player.hitbox()
        for obs in self._obstacles:
            obs.update(self._speed)
            if p_hb.colliderect(obs.hitbox()):
                self._sound.play_crash()
                self._state = GAME_OVER
                return

        self._obstacles = [o for o in self._obstacles if not o.off_screen()]

    # ── drawing ───────────────────────────────────────────────────────────────
    def _draw(self):
        self._bg.draw(self._screen)
        if self._player:
            self._player.draw(self._screen)
        for obs in self._obstacles:
            obs.draw(self._screen)
        self._draw_hud()
        if self._state == MENU:
            self._draw_menu()
        elif self._state == GAME_OVER:
            self._draw_gameover()
        pygame.display.flip()

    def _draw_hud(self):
        sc = self._scores
        self._screen.blit(
            self._font_sm.render(f"Score: {sc.score}", True, COL_WHITE),
            (10, 10))
        hi = self._font_sm.render(f"Best: {sc.best}", True, (255, 220, 80))
        self._screen.blit(hi, (SCREEN_W - hi.get_width() - 10, 10))

    def _overlay(self, alpha=150):
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        s.fill((0, 0, 0, alpha))
        self._screen.blit(s, (0, 0))

    def _centred(self, surf, y):
        self._screen.blit(surf, (SCREEN_W // 2 - surf.get_width() // 2, y))

    def _draw_menu(self):
        self._overlay(140)
        self._centred(self._font_lg.render("Olé!", True, (0, 255, 220)), 100)
        self._centred(self._font_md.render("Lagos Street Runner", True, (255, 220, 80)), 162)
        self._centred(
            self._font_sm.render("SPACE = jump   ↓ = duck   ESC = quit", True, COL_WHITE), 230)
        self._centred(
            self._font_sm.render("Press  SPACE  to start", True, (180, 255, 180)), 270)

    def _draw_gameover(self):
        self._overlay(160)
        self._centred(self._font_lg.render("GAME OVER", True, (255, 60, 60)),  95)
        self._centred(
            self._font_md.render(f"Score: {self._scores.score}", True, COL_WHITE), 168)
        self._centred(
            self._font_md.render(f"Best:  {self._scores.best}",  True, (255, 220, 80)), 208)
        self._centred(
            self._font_sm.render("SPACE or ENTER to play again", True, (180, 180, 180)), 268)


if __name__ == "__main__":
    Game().run()
