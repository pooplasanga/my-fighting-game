import pygame
import sys
import math
import random
import array
import asyncio

pygame.init()

# ---------- Audio setup ----------
AUDIO_ENABLED = True
try:
    pygame.mixer.init(frequency=44100, size=-16, channels=1)
except pygame.error:
    AUDIO_ENABLED = False

# ---------- Constants ----------
WIDTH, HEIGHT = 1000, 600
FPS = 60

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (46, 204, 113)
RED = (231, 76, 60)
YELLOW = (241, 196, 15)
BLUE = (52, 152, 219)
PURPLE = (155, 89, 182)
DARK_BLUE = (30, 39, 46)
LIGHT_GRAY = (150, 150, 150)
CYAN = (0, 255, 255)
ORANGE = (255, 140, 0)

ROUND_TIME = 60
ROUND_START_DELAY = 180
KO_DELAY = 150
WIN_ROUNDS = 2

# ---------- Block balance ----------
BLOCK_CHIP_MULTIPLIER = 0.25      # blocked attacks still deal 25% damage
BLOCK_STAMINA_DRAIN = 0.55        # stamina drained every frame while blocking
BLOCK_GUARD_DRAIN = 0.35          # guard meter drained every frame while blocking
BLOCK_STUN_FRAMES = 10            # short delay after blocking a hit
GUARD_BREAK_STUN_FRAMES = 60      # stun after guard breaks
MAX_GUARD = 100.0


STATE_TITLE = "title"
STATE_SELECT = "select"
STATE_FIGHT = "fight"
STATE_PAUSED = "paused"
STATE_GAME_OVER = "game_over"

main_screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Python Fighting Game: Mobile Combat")
clock = pygame.time.Clock()

font_small = pygame.font.SysFont(None, 24)
font_medium = pygame.font.SysFont(None, 36)
font_large = pygame.font.SysFont(None, 72)
font_huge = pygame.font.SysFont(None, 96)

# ---------- Sound helpers ----------
def make_tone(freq=440, duration_ms=120, volume=0.35):
    if not AUDIO_ENABLED:
        return None

    sample_rate = 44100
    n_samples = int(sample_rate * duration_ms / 1000)
    buf = array.array("h")
    amplitude = int(32767 * volume)

    for s in range(n_samples):
        t = s / sample_rate
        wave = math.sin(2 * math.pi * freq * t)
        fade = 1.0
        edge = max(1, int(n_samples * 0.08))
        if s < edge:
            fade = s / edge
        elif s > n_samples - edge:
            fade = (n_samples - s) / edge
        buf.append(int(amplitude * wave * fade))

    return pygame.mixer.Sound(buffer=buf)

def play_sound(sound):
    if AUDIO_ENABLED and sound is not None:
        try:
            sound.play()
        except pygame.error:
            pass

SND_PUNCH = make_tone(320, 70, 0.28)
SND_KICK = make_tone(180, 110, 0.35)
SND_FIREBALL = make_tone(520, 130, 0.25)
SND_ULTIMATE = make_tone(110, 280, 0.40)
SND_BLOCK = make_tone(700, 60, 0.18)
SND_MENU = make_tone(600, 60, 0.18)
SND_ROUND = make_tone(450, 180, 0.22)
SND_KO = make_tone(95, 400, 0.45)

# ---------- Background ----------
def create_sky_gradient():
    sky = pygame.Surface((WIDTH, HEIGHT))
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(44 * (1 - ratio) + 255 * ratio)
        g = int(44 * (1 - ratio) + 121 * ratio)
        b = int(44 * (1 - ratio) + 63 * ratio)
        pygame.draw.line(sky, (r, g, b), (0, y), (WIDTH, y))

    pygame.draw.circle(sky, (255, 255, 230), (800, 120), 40)
    for r in range(41, 60):
        alpha = int(50 * (1 - (r - 41) / 19))
        glow_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (255, 255, 200, alpha), (r, r), r)
        sky.blit(glow_surf, (800 - r, 120 - r))
    return sky

def generate_layer(total_width, min_h, max_h, color):
    layer = []
    x = -200
    while x < total_width + 200:
        w = random.randint(70, 140)
        h = random.randint(min_h, max_h)
        windows = [random.random() > 0.4 for _ in range(20)]
        layer.append({
            "x": x,
            "w": w,
            "h": h,
            "color": color,
            "windows": windows,
            "timer": random.randint(0, 100),
        })
        x += w + random.randint(-10, 5)
    return layer

sky_surface = create_sky_gradient()
far_skyline = generate_layer(WIDTH * 2, 100, 200, (30, 30, 50))
mid_skyline = generate_layer(WIDTH * 2, 180, 280, (40, 40, 65))
fore_skyline = generate_layer(WIDTH * 2, 250, 380, (50, 50, 80))

def draw_parallax_background(surface, camera_offset=0):
    surface.blit(sky_surface, (0, 0))

    def draw_layer(layer, multiplier):
        for b in layer:
            bx = b["x"] + (camera_offset * multiplier)
            pygame.draw.rect(surface, b["color"], (bx, HEIGHT - 50 - b["h"], b["w"], b["h"]))
            b["timer"] += 1
            if b["timer"] > 120:
                b["timer"] = 0
                b["windows"] = [random.random() > 0.4 for _ in range(20)]

            win_idx = 0
            for wy in range(HEIGHT - 40 - b["h"], HEIGHT - 60, 40):
                for wx in range(int(bx) + 10, int(bx) + b["w"] - 10, 20):
                    if win_idx < len(b["windows"]) and b["windows"][win_idx]:
                        pygame.draw.rect(surface, (241, 196, 15), (wx, wy, 8, 12))
                    win_idx += 1

    draw_layer(far_skyline, 0.05)
    draw_layer(mid_skyline, 0.15)
    draw_layer(fore_skyline, 0.35)
    pygame.draw.rect(surface, (25, 25, 35), (0, HEIGHT - 50, WIDTH, 50))


# ---------- Sprite helpers ----------
def load_sprite_strip(path, frame_count=4, target_height=150):
    try:
        sheet = pygame.image.load(path).convert_alpha()
    except pygame.error:
        return []
    frame_width = sheet.get_width() // frame_count
    frame_height = sheet.get_height()
    frames = []
    for i in range(frame_count):
        frame = sheet.subsurface((i * frame_width, 0, frame_width, frame_height))
        scale = target_height / frame_height
        new_width = max(1, int(frame_width * scale))
        frames.append(pygame.transform.scale(frame, (new_width, target_height)))
    return frames

IDLE_FRAMES = load_sprite_strip("assets/idle.png", 4, 150)

# ---------- Character data ----------
CHARACTERS = [
    {
        "name": "Blaze",
        "color": WHITE,
        "skin": (255, 205, 148),
        "accent": RED,
        "speed": 7.5,
        "punch_damage": 11,
        "kick_damage": 20,
        "fireball_damage": 24,
        "dash_cost": 25,
        "fireball_cost": 35,
        "special": "strong_fireball",
        "ultimate": "fire_blast",
    },
    {
        "name": "Volt",
        "color": RED,
        "skin": (141, 85, 36),
        "accent": BLUE,
        "speed": 8.5,
        "punch_damage": 9,
        "kick_damage": 16,
        "fireball_damage": 18,
        "dash_cost": 20,
        "fireball_cost": 40,
        "special": "fast_dash",
        "ultimate": "dash_strike",
    },
    {
        "name": "Jade",
        "color": GREEN,
        "skin": (220, 180, 140),
        "accent": YELLOW,
        "speed": 7.0,
        "punch_damage": 10,
        "kick_damage": 18,
        "fireball_damage": 20,
        "dash_cost": 25,
        "fireball_cost": 35,
        "special": "stamina_regen",
        "ultimate": "healing_burst",
    },
    {
        "name": "Shadow",
        "color": PURPLE,
        "skin": (120, 90, 70),
        "accent": LIGHT_GRAY,
        "speed": 7.8,
        "punch_damage": 12,
        "kick_damage": 17,
        "fireball_damage": 19,
        "dash_cost": 30,
        "fireball_cost": 40,
        "special": "lifesteal",
        "ultimate": "shadow_orb",
    },
]

ABILITY_NAMES = {
    "strong_fireball": "Big Fireball",
    "fast_dash": "Fast Dash",
    "stamina_regen": "Stamina Regen",
    "lifesteal": "Life Steal",
}

ULTIMATE_NAMES = {
    "fire_blast": "Fire Blast",
    "dash_strike": "Dash Strike",
    "healing_burst": "Healing Burst",
    "shadow_orb": "Shadow Orb",
}

CPU_SETTINGS = {
    "EASY": {
        "block_chance": 0.015,
        "jump_chance": 0.004,
        "ult_chance": 0.03,
        "fireball_chance": 0.09,
        "attack_bias": 0.25,
        "action_min": 26,
        "action_max": 42,
    },
    "NORMAL": {
        "block_chance": 0.03,
        "jump_chance": 0.008,
        "ult_chance": 0.08,
        "fireball_chance": 0.16,
        "attack_bias": 0.35,
        "action_min": 18,
        "action_max": 34,
    },
    "HARD": {
        "block_chance": 0.05,
        "jump_chance": 0.012,
        "ult_chance": 0.14,
        "fireball_chance": 0.24,
        "attack_bias": 0.50,
        "action_min": 12,
        "action_max": 24,
    },
}

# ---------- Fighter ----------
class Fighter:
    def __init__(self, x, y, character_data, is_p1):
        self.initial_x = x
        self.initial_y = y
        self.is_p1 = is_p1
        self.set_character(character_data)
        self.reset()

    def set_character(self, character_data):
        self.character_name = character_data["name"]
        self.color = character_data["color"]
        self.skin_color = character_data["skin"]
        self.accent = character_data["accent"]
        self.base_speed = character_data["speed"]
        self.punch_damage = character_data["punch_damage"]
        self.kick_damage = character_data["kick_damage"]
        self.fireball_damage = character_data["fireball_damage"]
        self.dash_cost = character_data["dash_cost"]
        self.fireball_cost = character_data["fireball_cost"]
        self.special = character_data["special"]
        self.ultimate_type = character_data["ultimate"]

    def reset(self):
        self.rect = pygame.Rect(self.initial_x, self.initial_y, 70, 140)
        self.speed = self.base_speed
        self.vel_y = 0
        self.vel_x = 0
        self.jumping = False
        self.health = 100
        self.stamina = 100.0
        self.ultimate_meter = 0
        self.guard_meter = MAX_GUARD
        self.stun_timer = 0
        self.block_stun_timer = 0

        self.attacking = False
        self.kicking = False
        self.low_attacking = False
        self.dashing = False
        self.blocking = False
        self.crouching = False
        self.using_ultimate = False

        self.attack_timer = 0
        self.kick_timer = 0
        self.low_attack_timer = 0
        self.dash_timer = 0
        self.hit_cooldown = 0
        self.hit_effect_timer = 0
        self.ultimate_timer = 0

        self.facing_right = True if self.is_p1 else False
        self.walk_cycle = 0
        self.anim_time = 0
        self.hit_recoil = 0

        self.combo_count = 0
        self.combo_timer = 0

    def move(self, left, right, up, down, other_fighter):
        self.vel_y += 1.5
        self.rect.y += self.vel_y
        self.rect.x += self.vel_x
        self.vel_x *= 0.8

        if self.rect.bottom >= HEIGHT - 50:
            self.rect.bottom = HEIGHT - 50
            self.vel_y = 0
            self.jumping = False

        stunned = self.stun_timer > 0 or self.block_stun_timer > 0
        move_multiplier = 0.5 if (self.attacking or self.kicking or self.using_ultimate or stunned) else 1.0
        current_speed = self.speed * move_multiplier

        # Directional block: block only happens while holding away from the opponent.
        # It now costs stamina + guard, so players cannot hold it forever.
        moving_back = (left and self.facing_right) or (right and not self.facing_right)
        can_block = (
            moving_back
            and not self.jumping
            and not self.using_ultimate
            and not stunned
            and self.stamina > 5
            and self.guard_meter > 0
        )
        self.blocking = can_block
        self.crouching = down and not self.jumping and not self.using_ultimate and not stunned

        if self.blocking or self.crouching:
            current_speed *= 0.65

        is_moving = False
        if not self.using_ultimate and not stunned:
            if left:
                self.rect.x -= current_speed
                is_moving = True
            if right:
                self.rect.x += current_speed
                is_moving = True

        if is_moving:
            self.walk_cycle += 0.25
        else:
            self.walk_cycle *= 0.8

        if up and not self.jumping and not self.crouching and not self.using_ultimate and not stunned:
            self.vel_y = -23
            self.jumping = True

        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > WIDTH:
            self.rect.right = WIDTH

        if not self.dashing:
            self.facing_right = self.rect.centerx < other_fighter.rect.centerx

    def can_act(self):
        return self.stun_timer <= 0 and self.block_stun_timer <= 0

    def attack(self):
        if self.can_act() and not any([self.attacking, self.kicking, self.low_attacking, self.dashing, self.blocking, self.using_ultimate]):
            self.attacking = True
            self.attack_timer = 15
            play_sound(SND_PUNCH)

    def kick(self):
        if self.can_act() and not any([self.attacking, self.kicking, self.low_attacking, self.dashing, self.blocking, self.using_ultimate]):
            self.kicking = True
            self.kick_timer = 20
            play_sound(SND_KICK)

    def low_attack(self):
        if self.can_act() and self.crouching and not any([self.attacking, self.kicking, self.low_attacking, self.dashing, self.blocking, self.using_ultimate]):
            self.low_attacking = True
            self.low_attack_timer = 18
            play_sound(SND_KICK)

    def dash(self, moving_left, moving_right):
        if self.can_act() and not any([self.attacking, self.kicking, self.low_attacking, self.dashing, self.crouching, self.using_ultimate]) and self.stamina >= self.dash_cost:
            self.stamina -= self.dash_cost
            self.dashing = True
            self.dash_timer = 10

            dash_power = 25
            if self.special == "fast_dash":
                dash_power = 34

            if moving_left:
                self.vel_x = -dash_power
            elif moving_right:
                self.vel_x = dash_power
            else:
                self.vel_x = dash_power if self.facing_right else -dash_power

    def can_use_ultimate(self):
        return self.can_act() and self.ultimate_meter >= 100 and not any([self.attacking, self.kicking, self.low_attacking, self.dashing, self.using_ultimate])

    def use_ultimate(self, projectiles):
        if not self.can_use_ultimate():
            return

        self.ultimate_meter = 0
        play_sound(SND_ULTIMATE)

        if self.ultimate_type == "fire_blast":
            self.using_ultimate = True
            self.ultimate_timer = 25
            projectiles.append({
                "rect": pygame.Rect(self.rect.centerx, self.rect.y + 25, 90, 35),
                "vx": (1 if self.facing_right else -1) * 18,
                "owner": self,
                "damage": 38,
                "kind": "ultimate_fire",
            })

        elif self.ultimate_type == "dash_strike":
            self.using_ultimate = True
            self.ultimate_timer = 12
            self.hit_cooldown = 0
            power = 48
            self.vel_x = power if self.facing_right else -power

        elif self.ultimate_type == "healing_burst":
            self.using_ultimate = True
            self.ultimate_timer = 35
            self.health = min(100, self.health + 30)
            self.stamina = min(100, self.stamina + 40)

        elif self.ultimate_type == "shadow_orb":
            self.using_ultimate = True
            self.ultimate_timer = 25
            projectiles.append({
                "rect": pygame.Rect(self.rect.centerx, self.rect.y + 20, 65, 65),
                "vx": (1 if self.facing_right else -1) * 12,
                "owner": self,
                "damage": 30,
                "kind": "shadow_orb",
            })

    def update(self):
        self.anim_time += 0.12

        if self.stun_timer > 0:
            self.stun_timer -= 1
            self.blocking = False
            self.attacking = False
            self.kicking = False
            self.low_attacking = False

        if self.block_stun_timer > 0:
            self.block_stun_timer -= 1

        # Blocking is strong, but not free: it drains stamina and guard.
        if self.blocking:
            self.stamina = max(0, self.stamina - BLOCK_STAMINA_DRAIN)
            self.guard_meter = max(0, self.guard_meter - BLOCK_GUARD_DRAIN)
            if self.stamina <= 0 or self.guard_meter <= 0:
                self.guard_break()
        else:
            # Guard recovers slowly when not blocking.
            if self.guard_meter < MAX_GUARD and self.stun_timer <= 0:
                self.guard_meter = min(MAX_GUARD, self.guard_meter + 0.45)

        regen = 0.4
        if self.special == "stamina_regen":
            regen = 0.7

        if self.stamina < 100:
            self.stamina = min(100, self.stamina + regen)

        if self.attack_timer > 0:
            self.attack_timer -= 1
            if self.attack_timer == 0:
                self.attacking = False

        if self.kick_timer > 0:
            self.kick_timer -= 1
            if self.kick_timer == 0:
                self.kicking = False

        if self.low_attack_timer > 0:
            self.low_attack_timer -= 1
            if self.low_attack_timer == 0:
                self.low_attacking = False

        if self.dash_timer > 0:
            self.dash_timer -= 1
            if self.dash_timer == 0:
                self.dashing = False

        if self.ultimate_timer > 0:
            self.ultimate_timer -= 1
            if self.ultimate_timer == 0:
                self.using_ultimate = False

        if self.hit_cooldown > 0:
            self.hit_cooldown -= 1

        if self.hit_effect_timer > 0:
            self.hit_effect_timer -= 1
            self.hit_recoil = 5
        else:
            self.hit_recoil *= 0.75

        if self.combo_timer > 0:
            self.combo_timer -= 1
            if self.combo_timer == 0:
                self.combo_count = 0

    def guard_break(self):
        self.blocking = False
        self.stun_timer = GUARD_BREAK_STUN_FRAMES
        self.block_stun_timer = 0
        self.hit_effect_timer = 12
        self.hit_cooldown = 25
        self.stamina = 0
        self.guard_meter = 0
        self.attacking = False
        self.kicking = False
        self.low_attacking = False
        create_hit_spark(self.rect.centerx, self.rect.centery, ORANGE)
        start_screen_shake(12, 8)
        start_hit_pause(5)

    def draw(self, surface):
        if IDLE_FRAMES:
            punch_rect = None
            kick_rect = None
            ultimate_rect = None
            low_attack_rect = None

            if self.attacking:
                reach = 80
                if self.facing_right:
                    punch_rect = pygame.Rect(self.rect.centerx, self.rect.y + 45, reach, 35)
                else:
                    punch_rect = pygame.Rect(self.rect.centerx - reach, self.rect.y + 45, reach, 35)

            if self.kicking:
                reach = 95
                if self.facing_right:
                    kick_rect = pygame.Rect(self.rect.centerx, self.rect.y + 80, reach, 35)
                else:
                    kick_rect = pygame.Rect(self.rect.centerx - reach, self.rect.y + 80, reach, 35)

            if self.low_attacking:
                reach = 85
                if self.facing_right:
                    low_attack_rect = pygame.Rect(self.rect.centerx, self.rect.bottom - 40, reach, 30)
                else:
                    low_attack_rect = pygame.Rect(self.rect.centerx - reach, self.rect.bottom - 40, reach, 30)

            if self.using_ultimate and self.ultimate_type == "dash_strike":
                ultimate_rect = pygame.Rect(self.rect.x - 8, self.rect.y, self.rect.width + 16, self.rect.height)

            frame_index = int(self.anim_time * 8) % len(IDLE_FRAMES)
            img = IDLE_FRAMES[frame_index]
            if not self.facing_right:
                img = pygame.transform.flip(img, True, False)

            draw_x = self.rect.centerx - img.get_width() // 2
            draw_y = self.rect.bottom - img.get_height() + 8

            pygame.draw.ellipse(surface, (0, 0, 0), (self.rect.centerx - 38, self.rect.bottom - 8, 76, 16))

            if self.hit_effect_timer > 0:
                flash = img.copy()
                flash.fill((255, 255, 255, 110), special_flags=pygame.BLEND_RGBA_ADD)
                surface.blit(flash, (draw_x, draw_y))
            else:
                surface.blit(img, (draw_x, draw_y))

            if self.blocking:
                pygame.draw.arc(surface, CYAN, (self.rect.x - 15, self.rect.y + 10, self.rect.width + 30, self.rect.height - 20), 1.2, 5.0, 4)
            if self.stun_timer > 0:
                stun_text = font_small.render("GUARD BREAK!", True, ORANGE)
                surface.blit(stun_text, (self.rect.centerx - stun_text.get_width() // 2, self.rect.y - 20))
            if self.attacking and punch_rect:
                pygame.draw.circle(surface, self.accent, punch_rect.center, 10)
            if self.kicking and kick_rect:
                pygame.draw.circle(surface, self.accent, kick_rect.center, 10)
            if self.low_attacking and low_attack_rect:
                pygame.draw.circle(surface, self.accent, low_attack_rect.center, 8)
            if self.using_ultimate and self.ultimate_type == "healing_burst":
                pygame.draw.circle(surface, GREEN, self.rect.center, 60, 4)
            if self.using_ultimate and self.ultimate_type == "dash_strike":
                pygame.draw.rect(surface, CYAN, self.rect.inflate(30, 30), 4, border_radius=8)

            return punch_rect, kick_rect, ultimate_rect, low_attack_rect

        main_color = WHITE if self.hit_effect_timer > 0 else self.color
        skin = WHITE if self.hit_effect_timer > 0 else self.skin_color
        accent_color = WHITE if self.hit_effect_timer > 0 else self.accent

        dir_factor = 1 if self.facing_right else -1
        cx = self.rect.centerx - int(self.hit_recoil * dir_factor)
        ground_y = self.rect.bottom

        idle_bob = math.sin(self.anim_time * 2.2) * 2
        idle_sway = math.sin(self.anim_time * 1.7) * 3
        walk_wave = math.sin(self.walk_cycle) * 14
        crouch_offset = 18 if self.crouching else 0

        torso_top = self.rect.y + 38 + idle_bob + crouch_offset
        torso_h = 54 - crouch_offset
        head_y = self.rect.y + 18 + idle_bob + crouch_offset
        shoulder_y = torso_top + 12
        waist_y = torso_top + torso_h - 4

        punch_rect = None
        kick_rect = None
        ultimate_rect = None
        low_attack_rect = None

        if self.low_attacking:
            foot_x = cx + (75 * dir_factor)
            foot_y = ground_y - 15
            pygame.draw.line(surface, main_color, (cx, waist_y), (foot_x, foot_y), 14)
            pygame.draw.circle(surface, accent_color, (int(foot_x), int(foot_y)), 9)
            low_attack_rect = pygame.Rect(
                min(cx, int(foot_x)),
                int(foot_y - 12),
                abs(int(foot_x - cx)) + 20,
                24
            )

        if self.kicking:
            pygame.draw.line(surface, main_color, (cx - (10 * dir_factor), waist_y), (cx - (25 * dir_factor), ground_y), 18)
            kick_progress = (20 - self.kick_timer) / 20.0
            reach = 90 * math.sin(kick_progress * math.pi)
            knee_x = cx + (28 * dir_factor)
            knee_y = waist_y - 8
            foot_x = knee_x + (reach * dir_factor)
            foot_y = knee_y - 8

            pygame.draw.line(surface, main_color, (cx + 8 * dir_factor, waist_y), (knee_x, knee_y), 15)
            pygame.draw.line(surface, main_color, (knee_x, knee_y), (foot_x, foot_y), 14)
            pygame.draw.circle(surface, accent_color, (int(foot_x), int(foot_y)), 10)
            kick_rect = pygame.Rect(min(cx, int(foot_x)), int(foot_y - 12), max(abs(int(foot_x - cx)), 1) + 20, 24)
        else:
            if self.jumping:
                left_leg_end = (cx - 14, ground_y - 18)
                right_leg_end = (cx + 18, ground_y - 8)
            elif self.blocking or self.crouching:
                left_leg_end = (cx - 18, ground_y)
                right_leg_end = (cx + 10, ground_y - 6)
            else:
                left_leg_end = (cx - 12 + walk_wave, ground_y)
                right_leg_end = (cx + 12 - walk_wave, ground_y)

            pygame.draw.line(surface, main_color, (cx - 10, waist_y), left_leg_end, 16)
            pygame.draw.line(surface, main_color, (cx + 10, waist_y), right_leg_end, 16)

        torso_w = 46 if self.is_p1 else 42
        pygame.draw.rect(surface, main_color if self.is_p1 else DARK_BLUE,
                         (cx - torso_w // 2, torso_top, torso_w, torso_h), border_radius=8)
        pygame.draw.rect(surface, BLACK, (cx - 24, waist_y - 4, 48, 8), border_radius=3)

        pygame.draw.circle(surface, skin, (cx, int(head_y)), 20 if self.is_p1 else 19)

        if self.character_name == "Blaze":
            pygame.draw.polygon(surface, BLACK, [(cx - 20, head_y - 8), (cx + 20, head_y - 8), (cx, head_y - 25)])
            pygame.draw.rect(surface, RED, (cx - 20, int(head_y - 6), 40, 5))
        elif self.character_name == "Volt":
            pygame.draw.rect(surface, DARK_BLUE, (cx - 20, int(head_y - 2), 40, 18), border_radius=5)
            pygame.draw.circle(surface, BLUE, (cx + (8 * dir_factor), int(head_y - 1)), 4)
        elif self.character_name == "Jade":
            pygame.draw.polygon(surface, GREEN, [(cx - 18, head_y - 10), (cx + 18, head_y - 10), (cx, head_y - 23)])
            pygame.draw.circle(surface, YELLOW, (cx + (9 * dir_factor), int(head_y - 2)), 3)
        elif self.character_name == "Shadow":
            pygame.draw.rect(surface, PURPLE, (cx - 20, int(head_y - 5), 40, 10), border_radius=4)
            pygame.draw.circle(surface, LIGHT_GRAY, (cx + (9 * dir_factor), int(head_y - 1)), 3)

        if self.attacking:
            prog = (15 - self.attack_timer) / 15.0
            reach = 70 * math.sin(prog * math.pi)
            arm_start = (cx + (6 * dir_factor), shoulder_y)
            arm_end = (cx + (reach * dir_factor), shoulder_y - 2)
            pygame.draw.line(surface, skin, arm_start, arm_end, 12)
            pygame.draw.circle(surface, accent_color, (int(arm_end[0]), int(arm_end[1])), 10)

            back_arm = (cx - (18 * dir_factor), shoulder_y + 14)
            pygame.draw.line(surface, skin, (cx - 4 * dir_factor, shoulder_y + 6), back_arm, 10)

            left_x = min(cx, int(cx + reach * dir_factor))
            punch_rect = pygame.Rect(left_x, int(shoulder_y - 10), max(abs(int(reach)), 1), 24)

        elif self.blocking:
            pygame.draw.line(surface, skin, (cx, shoulder_y), (cx + 18 * dir_factor, shoulder_y - 18), 12)
            pygame.draw.line(surface, skin, (cx - 2 * dir_factor, shoulder_y + 8), (cx + 14 * dir_factor, shoulder_y - 2), 12)
            pygame.draw.circle(surface, accent_color, (cx + 18 * dir_factor, int(shoulder_y - 18)), 8)

        elif self.using_ultimate and self.ultimate_type == "dash_strike":
            glow = pygame.Rect(self.rect.x - 10, self.rect.y - 10, self.rect.width + 20, self.rect.height + 20)
            pygame.draw.rect(surface, CYAN, glow, 4, border_radius=8)
            pygame.draw.line(surface, skin, (cx, shoulder_y), (cx + 28 * dir_factor, shoulder_y - 4), 12)
            pygame.draw.line(surface, skin, (cx - 6 * dir_factor, shoulder_y + 10), (cx + 18 * dir_factor, shoulder_y + 8), 12)
            ultimate_rect = pygame.Rect(self.rect.x - 5, self.rect.y, self.rect.width + 10, self.rect.height)

        else:
            front_hand = (cx + (18 * dir_factor) + idle_sway, shoulder_y + 10)
            back_hand = (cx - (12 * dir_factor) - idle_sway, shoulder_y + 18)
            pygame.draw.line(surface, skin, (cx + 3 * dir_factor, shoulder_y + 4), front_hand, 10)
            pygame.draw.line(surface, skin, (cx - 3 * dir_factor, shoulder_y + 7), back_hand, 10)
            pygame.draw.circle(surface, accent_color, (int(front_hand[0]), int(front_hand[1])), 8)

        if self.using_ultimate and self.ultimate_type == "healing_burst":
            pygame.draw.circle(surface, GREEN, self.rect.center, 60, 4)

        return punch_rect, kick_rect, ultimate_rect, low_attack_rect

# ---------- Game state ----------
p1 = Fighter(200, HEIGHT - 180, CHARACTERS[0], True)
p2 = Fighter(700, HEIGHT - 180, CHARACTERS[1], False)

fireballs = []
sparks = []

game_state = STATE_TITLE
winner_text = ""

p1_selection = 0
p2_selection = 1
p1_locked = False
p2_locked = False

p1_rounds = 0
p2_rounds = 0
current_round = 1
round_timer = ROUND_TIME * FPS
round_intro_timer = ROUND_START_DELAY
round_end_timer = 0
round_message = "ROUND 1"
round_over = False

hit_pause_timer = 0
screen_shake_timer = 0
screen_shake_strength = 0
shake_x = 0
shake_y = 0

combo_popup_timer_p1 = 0
combo_popup_timer_p2 = 0

vs_cpu = False
cpu_difficulty = "NORMAL"
cpu_action_timer = 0

# ---------- Utility ----------
def apply_selected_characters():
    global p1, p2
    p1 = Fighter(200, HEIGHT - 180, CHARACTERS[p1_selection], True)
    p2 = Fighter(700, HEIGHT - 180, CHARACTERS[p2_selection], False)

def setup_new_match():
    global p1_rounds, p2_rounds, current_round, winner_text
    p1_rounds = 0
    p2_rounds = 0
    current_round = 1
    winner_text = ""
    apply_selected_characters()
    start_round()

def start_round():
    global fireballs, sparks, round_timer, round_intro_timer, round_end_timer
    global round_message, round_over, hit_pause_timer, screen_shake_timer
    global screen_shake_strength, combo_popup_timer_p1, combo_popup_timer_p2, cpu_action_timer

    p1.reset()
    p2.reset()
    fireballs = []
    sparks = []

    round_timer = ROUND_TIME * FPS
    round_intro_timer = ROUND_START_DELAY
    round_end_timer = 0
    round_over = False
    hit_pause_timer = 0
    screen_shake_timer = 0
    screen_shake_strength = 0
    combo_popup_timer_p1 = 0
    combo_popup_timer_p2 = 0
    cpu_action_timer = 0

    if current_round == 1:
        round_message = "ROUND 1"
    elif current_round == 2:
        round_message = "ROUND 2"
    else:
        round_message = "FINAL ROUND"

    play_sound(SND_ROUND)

def reset_to_character_select():
    global p1_locked, p2_locked, game_state
    p1_locked = False
    p2_locked = False
    game_state = STATE_SELECT

def start_hit_pause(frames):
    global hit_pause_timer
    hit_pause_timer = max(hit_pause_timer, frames)

def start_screen_shake(frames, strength):
    global screen_shake_timer, screen_shake_strength
    screen_shake_timer = max(screen_shake_timer, frames)
    screen_shake_strength = max(screen_shake_strength, strength)

def create_hit_spark(x, y, color):
    for _ in range(8):
        sparks.append({
            "x": x,
            "y": y,
            "vx": random.uniform(-6, 6),
            "vy": random.uniform(-6, 6),
            "life": 12,
            "color": color,
        })

def update_screen_shake():
    global screen_shake_timer, screen_shake_strength, shake_x, shake_y
    if screen_shake_timer > 0:
        shake_x = random.randint(-screen_shake_strength, screen_shake_strength)
        shake_y = random.randint(-screen_shake_strength, screen_shake_strength)
        screen_shake_timer -= 1
        if screen_shake_timer == 0:
            screen_shake_strength = 0
    else:
        shake_x = 0
        shake_y = 0

def gain_ultimate(fighter, amount):
    fighter.ultimate_meter = min(100, fighter.ultimate_meter + amount)

def register_combo(dealer):
    global combo_popup_timer_p1, combo_popup_timer_p2
    dealer.combo_count += 1
    dealer.combo_timer = 90
    if dealer.is_p1:
        combo_popup_timer_p1 = 60
    else:
        combo_popup_timer_p2 = 60

def break_combo(receiver):
    receiver.combo_count = 0
    receiver.combo_timer = 0

def check_hit(dealer, receiver, hitbox, damage, knockback):
    if not hitbox:
        return
    if not hitbox.colliderect(receiver.rect):
        return
    if receiver.hit_cooldown != 0:
        return

    if receiver.blocking:
        chip_damage = damage * BLOCK_CHIP_MULTIPLIER
        receiver.health -= chip_damage
        receiver.stamina = max(0, receiver.stamina - damage * 1.0)
        receiver.guard_meter = max(0, receiver.guard_meter - damage * 2.0)
        receiver.hit_cooldown = 13
        receiver.block_stun_timer = BLOCK_STUN_FRAMES
        receiver.vel_x = (knockback * 0.35) if dealer.rect.centerx < receiver.rect.centerx else -(knockback * 0.35)
        create_hit_spark(receiver.rect.centerx, receiver.rect.centery, PURPLE)

        gain_ultimate(dealer, 7)
        gain_ultimate(receiver, 5)

        start_hit_pause(2)
        start_screen_shake(5, 3)
        play_sound(SND_BLOCK)

        if receiver.stamina <= 0 or receiver.guard_meter <= 0:
            receiver.guard_break()

    else:
        receiver.health -= damage
        receiver.hit_cooldown = 20
        receiver.hit_effect_timer = 5
        receiver.vel_x = knockback if dealer.rect.centerx < receiver.rect.centerx else -knockback
        create_hit_spark(receiver.rect.centerx, receiver.rect.centery, YELLOW if dealer.is_p1 else BLUE)

        gain_ultimate(dealer, 12)
        gain_ultimate(receiver, 10)

        register_combo(dealer)
        break_combo(receiver)

        if damage >= 30:
            start_hit_pause(6)
            start_screen_shake(10, 10)
        elif damage >= 18:
            start_hit_pause(4)
            start_screen_shake(7, 6)
        else:
            start_hit_pause(3)
            start_screen_shake(5, 4)

        if dealer.special == "lifesteal":
            dealer.health = min(100, dealer.health + damage * 0.2)

def award_round():
    global p1_rounds, p2_rounds, current_round, game_state, winner_text, round_end_timer, round_message, round_over

    round_over = True
    round_end_timer = KO_DELAY

    if p1.health > p2.health:
        p1_rounds += 1
        round_message = "PLAYER 1 WINS ROUND"
    elif p2.health > p1.health:
        p2_rounds += 1
        round_message = "PLAYER 2 WINS ROUND"
    else:
        round_message = "DRAW"

    if p1_rounds >= WIN_ROUNDS:
        winner_text = "PLAYER 1 WINS MATCH!"
        game_state = STATE_GAME_OVER
    elif p2_rounds >= WIN_ROUNDS:
        winner_text = "PLAYER 2 WINS MATCH!"
        game_state = STATE_GAME_OVER
    else:
        current_round += 1

    if p1.health <= 0 or p2.health <= 0:
        play_sound(SND_KO)
    else:
        play_sound(SND_ROUND)

def cpu_control(cpu, target):
    global cpu_action_timer, fireballs
    settings = CPU_SETTINGS[cpu_difficulty]

    left = right = up = down = False
    dist = target.rect.centerx - cpu.rect.centerx
    abs_dist = abs(dist)

    if cpu_action_timer > 0:
        cpu_action_timer -= 1

    if abs_dist > 150:
        if dist > 0:
            right = True
        else:
            left = True
    elif abs_dist < 75:
        if dist > 0:
            left = True
        else:
            right = True

    if abs_dist < 120 and random.random() < settings["block_chance"]:
        down = True

    if not cpu.jumping and random.random() < settings["jump_chance"]:
        up = True

    cpu.move(left, right, up, down, target)

    if cpu_action_timer > 0:
        return
    if any([cpu.attacking, cpu.kicking, cpu.low_attacking, cpu.dashing, cpu.using_ultimate]):
        return

    roll = random.random()

    if cpu.can_use_ultimate() and random.random() < settings["ult_chance"]:
        cpu.use_ultimate(fireballs)
        cpu_action_timer = random.randint(settings["action_min"] + 10, settings["action_max"] + 20)
        return

    if abs_dist < 90:
        if roll < settings["attack_bias"]:
            cpu.attack()
        elif roll < settings["attack_bias"] + 0.22:
            cpu.kick()
        elif roll < settings["attack_bias"] + 0.32 and cpu.stamina >= cpu.dash_cost:
            cpu.dash(left, right)
        cpu_action_timer = random.randint(settings["action_min"], settings["action_max"])
        return

    if abs_dist < 280 and random.random() < settings["fireball_chance"] and cpu.stamina >= cpu.fireball_cost:
        cpu.stamina -= cpu.fireball_cost
        fireball_speed = 14
        fireball_w = 40
        fireball_h = 20

        if cpu.special == "strong_fireball":
            fireball_speed = 16
            fireball_w = 55
            fireball_h = 24

        fireballs.append({
            "rect": pygame.Rect(cpu.rect.centerx, cpu.rect.y + 40, fireball_w, fireball_h),
            "vx": (1 if cpu.facing_right else -1) * fireball_speed,
            "owner": cpu,
            "damage": cpu.fireball_damage,
            "kind": "normal",
        })
        play_sound(SND_FIREBALL)
        cpu_action_timer = random.randint(settings["action_min"] + 8, settings["action_max"] + 18)

# ---------- Drawing ----------
def draw_title_screen(surface):
    draw_parallax_background(surface, 0)
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 120))
    surface.blit(overlay, (0, 0))

    title = font_large.render("MOBILE COMBAT", True, WHITE)
    subtitle = font_medium.render("Best 2 out of 3", True, LIGHT_GRAY)
    prompt = font_medium.render("PRESS ENTER TO START", True, YELLOW)

    surface.blit(title, (WIDTH // 2 - title.get_width() // 2, 170))
    surface.blit(subtitle, (WIDTH // 2 - subtitle.get_width() // 2, 255))
    surface.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, 330))

def draw_character_card(surface, x, y, character, selected=False, locked=False, player_text=""):
    card_w, card_h = 180, 255
    border = YELLOW if selected else LIGHT_GRAY
    fill = (35, 35, 45)

    pygame.draw.rect(surface, fill, (x, y, card_w, card_h), border_radius=12)
    pygame.draw.rect(surface, border, (x, y, card_w, card_h), 3, border_radius=12)

    pygame.draw.circle(surface, character["skin"], (x + 90, y + 55), 28)
    pygame.draw.rect(surface, character["color"], (x + 65, y + 90, 50, 80), border_radius=10)
    pygame.draw.circle(surface, character["accent"], (x + 130, y + 105), 10)

    name_text = font_medium.render(character["name"], True, WHITE)
    surface.blit(name_text, (x + card_w // 2 - name_text.get_width() // 2, y + 180))

    if player_text:
        label = font_small.render(player_text, True, YELLOW)
        surface.blit(label, (x + card_w // 2 - label.get_width() // 2, y + 10))

    ability_text = font_small.render(ABILITY_NAMES[character["special"]], True, LIGHT_GRAY)
    ultimate_text = font_small.render("Ult: " + ULTIMATE_NAMES[character["ultimate"]], True, LIGHT_GRAY)
    surface.blit(ability_text, (x + card_w // 2 - ability_text.get_width() // 2, y + 205))
    surface.blit(ultimate_text, (x + card_w // 2 - ultimate_text.get_width() // 2, y + 225))

    if locked:
        lock_text = font_small.render("LOCKED IN", True, GREEN)
        surface.blit(lock_text, (x + card_w // 2 - lock_text.get_width() // 2, y + 238))

def draw_character_select(surface):
    draw_parallax_background(surface, 0)

    title = font_large.render("CHARACTER SELECT", True, WHITE)
    info1 = font_small.render("P1: A / D to choose, F to lock", True, LIGHT_GRAY)
    info2 = font_small.render("P2: LEFT / RIGHT to choose, P to lock", True, LIGHT_GRAY)
    mode_text = font_medium.render(f"MODE: {'VS CPU' if vs_cpu else '2 PLAYER'}   |   M TO CHANGE", True, CYAN)
    diff_text = font_medium.render(f"CPU DIFFICULTY: {cpu_difficulty}   |   N TO CHANGE", True, YELLOW if vs_cpu else LIGHT_GRAY)

    surface.blit(title, (WIDTH // 2 - title.get_width() // 2, 35))
    surface.blit(info1, (WIDTH // 2 - info1.get_width() // 2, 90))
    surface.blit(info2, (WIDTH // 2 - info2.get_width() // 2, 112))
    surface.blit(mode_text, (WIDTH // 2 - mode_text.get_width() // 2, 140))
    surface.blit(diff_text, (WIDTH // 2 - diff_text.get_width() // 2, 170))

    start_x = 90
    gap = 30
    y = 205

    for i, char in enumerate(CHARACTERS):
        x = start_x + i * (180 + gap)
        label = ""
        selected = False
        locked = False

        if i == p1_selection and not p1_locked:
            label = "P1"
            selected = True
        if i == p2_selection and not p2_locked:
            label = "CPU" if vs_cpu else ("P2" if label == "" else "P1 / P2")
            selected = True
        if i == p1_selection and p1_locked:
            label = "P1"
            selected = True
            locked = True
        if i == p2_selection and p2_locked:
            label = "CPU" if vs_cpu else ("P2" if label == "" else "P1 / P2")
            locked = True

        draw_character_card(surface, x, y, char, selected, locked, label)

    if p1_locked and p2_locked:
        ready = font_medium.render("BOTH SIDES READY - PRESS ENTER", True, GREEN)
        surface.blit(ready, (WIDTH // 2 - ready.get_width() // 2, 545))

def draw_controls_ui(surface):
    p1_text = [
        "P1: [A/D] Move [W] Jump [S] Crouch",
        "Hold backward to block | [S+F] Low Attack",
        "[F] Punch [R] Kick [G] Fireball [T] Dash [H] Ultimate",
    ]
    if vs_cpu:
        p2_text = [
            f"CPU OPPONENT ENABLED - {cpu_difficulty}",
            "M/N ONLY WORK ON CHARACTER SELECT",
        ]
    else:
        p2_text = [
            "P2: [<- ->] Move [UP] Jump [DOWN] Crouch",
            "Hold backward to block | [DOWN+P] Low Attack",
            "[P] Punch [O] Kick [[] Fireball [U] Dash []] Ultimate",
        ]

    pygame.draw.rect(surface, (40, 40, 45), (50, 95, 420, 70), border_radius=5)
    pygame.draw.rect(surface, (40, 40, 45), (530, 95, 420, 70), border_radius=5)

    for i, line in enumerate(p1_text):
        surface.blit(font_small.render(line, True, LIGHT_GRAY), (60, 100 + (i * 20)))
    for i, line in enumerate(p2_text):
        surface.blit(font_small.render(line, True, LIGHT_GRAY), (540, 100 + (i * 20)))

def draw_round_icons(surface):
    for i in range(WIN_ROUNDS):
        color1 = GREEN if i < p1_rounds else (70, 70, 70)
        color2 = RED if i < p2_rounds else (70, 70, 70)
        pygame.draw.circle(surface, color1, (80 + i * 24, 85), 8)
        pygame.draw.circle(surface, color2, (920 - i * 24, 85), 8)

def draw_round_timer(surface):
    seconds = max(0, round_timer // FPS)
    timer_text = font_medium.render(str(seconds), True, WHITE)
    box = pygame.Rect(WIDTH // 2 - 40, 20, 80, 40)
    pygame.draw.rect(surface, (40, 40, 45), box, border_radius=8)
    pygame.draw.rect(surface, LIGHT_GRAY, box, 2, border_radius=8)
    surface.blit(timer_text, (WIDTH // 2 - timer_text.get_width() // 2, 27))

def draw_intro_overlay(surface):
    if round_intro_timer > 120:
        text = round_message
        color = WHITE
    elif round_intro_timer > 45:
        text = "FIGHT!"
        color = YELLOW
    else:
        return

    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 80))
    surface.blit(overlay, (0, 0))

    render = font_huge.render(text, True, color)
    surface.blit(render, (WIDTH // 2 - render.get_width() // 2, HEIGHT // 2 - 60))

def draw_round_end_overlay(surface):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 100))
    surface.blit(overlay, (0, 0))

    if p1.health <= 0 or p2.health <= 0:
        top_text = "KO!"
        top_color = ORANGE
    else:
        top_text = "TIME OVER"
        top_color = CYAN

    render1 = font_huge.render(top_text, True, top_color)
    render2 = font_medium.render(round_message, True, WHITE)
    surface.blit(render1, (WIDTH // 2 - render1.get_width() // 2, HEIGHT // 2 - 80))
    surface.blit(render2, (WIDTH // 2 - render2.get_width() // 2, HEIGHT // 2 + 10))

def draw_combo_popups(surface):
    global combo_popup_timer_p1, combo_popup_timer_p2

    if p1.combo_count >= 2 and combo_popup_timer_p1 > 0:
        text = font_medium.render(f"{p1.combo_count} HIT COMBO!", True, YELLOW)
        surface.blit(text, (90, 155))
        combo_popup_timer_p1 -= 1

    if p2.combo_count >= 2 and combo_popup_timer_p2 > 0:
        text = font_medium.render(f"{p2.combo_count} HIT COMBO!", True, CYAN)
        surface.blit(text, (WIDTH - 90 - text.get_width(), 155))
        combo_popup_timer_p2 -= 1

def draw_pause_menu(surface):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 170))
    surface.blit(overlay, (0, 0))

    title = font_large.render("PAUSED", True, WHITE)
    line1 = font_medium.render("ENTER = RESUME", True, GREEN)
    line2 = font_medium.render("R = RESTART MATCH", True, YELLOW)
    line3 = font_medium.render("C = CHARACTER SELECT", True, CYAN)
    line4 = font_medium.render("ESC = QUIT", True, RED)

    surface.blit(title, (WIDTH // 2 - title.get_width() // 2, 160))
    surface.blit(line1, (WIDTH // 2 - line1.get_width() // 2, 260))
    surface.blit(line2, (WIDTH // 2 - line2.get_width() // 2, 310))
    surface.blit(line3, (WIDTH // 2 - line3.get_width() // 2, 360))
    surface.blit(line4, (WIDTH // 2 - line4.get_width() // 2, 410))

def draw_game_over(surface):
    draw_parallax_background(surface, 0)
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    surface.blit(overlay, (0, 0))

    title = font_large.render(winner_text, True, WHITE)
    score = font_medium.render(f"FINAL SCORE  {p1_rounds} - {p2_rounds}", True, YELLOW)
    rematch = font_medium.render("R = PLAY AGAIN", True, GREEN)
    select_text = font_medium.render("C = CHARACTER SELECT", True, YELLOW)
    quit_text = font_medium.render("ESC = QUIT", True, RED)

    surface.blit(title, (WIDTH // 2 - title.get_width() // 2, 170))
    surface.blit(score, (WIDTH // 2 - score.get_width() // 2, 250))
    surface.blit(rematch, (WIDTH // 2 - rematch.get_width() // 2, 320))
    surface.blit(select_text, (WIDTH // 2 - select_text.get_width() // 2, 365))
    surface.blit(quit_text, (WIDTH // 2 - quit_text.get_width() // 2, 410))

# ---------- Main fight drawing/update ----------
def draw_fight_scene(surface):
    global round_timer, round_intro_timer, round_end_timer, round_over, hit_pause_timer

    center_focus = (p1.rect.centerx + p2.rect.centerx) // 2
    camera_offset = -(center_focus - WIDTH // 2)

    draw_parallax_background(surface, camera_offset)

    controls_locked = round_intro_timer > 0 or round_over
    should_update_game = hit_pause_timer <= 0

    if should_update_game:
        if not controls_locked:
            keys = pygame.key.get_pressed()
            p1.move(keys[pygame.K_a], keys[pygame.K_d], keys[pygame.K_w], keys[pygame.K_s], p2)

            if vs_cpu:
                cpu_control(p2, p1)
            else:
                p2.move(keys[pygame.K_LEFT], keys[pygame.K_RIGHT], keys[pygame.K_UP], keys[pygame.K_DOWN], p1)
        else:
            p1.move(False, False, False, False, p2)
            p2.move(False, False, False, False, p1)

        p1.update()
        p2.update()
    else:
        hit_pause_timer -= 1

    p1_punch, p1_kick, p1_ult_hit, p1_low = p1.draw(surface)
    p2_punch, p2_kick, p2_ult_hit, p2_low = p2.draw(surface)

    if not controls_locked and should_update_game:
        check_hit(p1, p2, p1_punch, p1.punch_damage, 10)
        check_hit(p1, p2, p1_kick, p1.kick_damage, 18)
        check_hit(p2, p1, p2_punch, p2.punch_damage, 10)
        check_hit(p2, p1, p2_kick, p2.kick_damage, 18)
        check_hit(p1, p2, p1_low, 13, 8)
        check_hit(p2, p1, p2_low, 13, 8)

        if p1_ult_hit:
            check_hit(p1, p2, p1_ult_hit, 28, 24)
        if p2_ult_hit:
            check_hit(p2, p1, p2_ult_hit, 28, 24)

    if should_update_game:
        for f in fireballs[:]:
            f["rect"].x += f["vx"]
            target = p2 if f["owner"] == p1 else p1

            if not controls_locked and f["rect"].colliderect(target.rect):
                check_hit(f["owner"], target, f["rect"], f["damage"], 15)
                if f.get("kind") == "shadow_orb":
                    f["owner"].health = min(100, f["owner"].health + 15)
                fireballs.remove(f)
            elif f["rect"].left < 0 or f["rect"].right > WIDTH:
                fireballs.remove(f)

        for s in sparks[:]:
            s["x"] += s["vx"]
            s["y"] += s["vy"]
            s["life"] -= 1
            if s["life"] <= 0:
                sparks.remove(s)

    for f in fireballs:
        if f.get("kind") == "shadow_orb":
            pygame.draw.ellipse(surface, PURPLE, f["rect"])
            pygame.draw.ellipse(surface, LIGHT_GRAY, f["rect"], 3)
        elif f.get("kind") == "ultimate_fire":
            pygame.draw.ellipse(surface, RED, f["rect"])
            inner = f["rect"].inflate(-20, -8)
            pygame.draw.ellipse(surface, YELLOW, inner)
        else:
            pygame.draw.ellipse(surface, YELLOW if f["owner"] == p1 else BLUE, f["rect"])

    for s in sparks:
        pygame.draw.circle(surface, s["color"], (int(s["x"]), int(s["y"])), 4)

    p1_health_val = max(0, min(100, p1.health))
    p2_health_val = max(0, min(100, p2.health))
    p1_stamina_val = max(0, min(100, p1.stamina))
    p2_stamina_val = max(0, min(100, p2.stamina))
    p1_ult_val = max(0, min(100, p1.ultimate_meter))
    p2_ult_val = max(0, min(100, p2.ultimate_meter))

    pygame.draw.rect(surface, (60, 60, 65), (50, 30, 400, 20), border_radius=5)
    pygame.draw.rect(surface, (60, 60, 65), (550, 30, 400, 20), border_radius=5)

    pygame.draw.rect(surface, GREEN, (50, 30, p1_health_val * 4, 20), border_radius=5)
    pygame.draw.rect(surface, YELLOW, (50, 60, p1_stamina_val * 2, 10), border_radius=3)
    pygame.draw.rect(surface, ORANGE, (50, 88, max(0, min(100, p1.guard_meter)) * 2, 7), border_radius=3)
    pygame.draw.rect(surface, CYAN, (50, 75, p1_ult_val * 2, 8), border_radius=3)

    pygame.draw.rect(surface, RED, (550 + (400 - p2_health_val * 4), 30, p2_health_val * 4, 20), border_radius=5)
    pygame.draw.rect(surface, BLUE, (750 + (200 - p2_stamina_val * 2), 60, p2_stamina_val * 2, 10), border_radius=3)
    pygame.draw.rect(surface, ORANGE, (750 + (200 - max(0, min(100, p2.guard_meter)) * 2), 88, max(0, min(100, p2.guard_meter)) * 2, 7), border_radius=3)
    pygame.draw.rect(surface, PURPLE, (750 + (200 - p2_ult_val * 2), 75, p2_ult_val * 2, 8), border_radius=3)

    p1_name = font_small.render(p1.character_name, True, WHITE)
    p2_name = font_small.render(("CPU " if vs_cpu else "") + p2.character_name, True, WHITE)
    surface.blit(p1_name, (50, 10))
    surface.blit(p2_name, (950 - p2_name.get_width(), 10))

    ult1 = font_small.render("ULT", True, CYAN)
    ult2 = font_small.render("ULT", True, CYAN)
    surface.blit(ult1, (255, 72))
    surface.blit(ult2, (720, 72))

    draw_round_icons(surface)
    draw_round_timer(surface)
    draw_controls_ui(surface)
    draw_combo_popups(surface)

    if round_intro_timer > 0 and should_update_game:
        round_intro_timer -= 1
        draw_intro_overlay(surface)
    elif not round_over and should_update_game:
        round_timer -= 1

        if p1.health <= 0 or p2.health <= 0:
            award_round()
        elif round_timer <= 0:
            award_round()

    if round_over:
        draw_round_end_overlay(surface)
        if game_state != STATE_GAME_OVER and should_update_game:
            round_end_timer -= 1
            if round_end_timer <= 0:
                start_round()

# ---------- Main loop ----------
async def main():
    global game_state, p1_selection, p2_selection, p1_locked, p2_locked
    global vs_cpu, cpu_difficulty, fireballs

    while True:
        update_screen_shake()
        world_surface = pygame.Surface((WIDTH, HEIGHT))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return

            if event.type == pygame.KEYDOWN:
                keys = pygame.key.get_pressed()

                if game_state == STATE_TITLE:
                    if event.key == pygame.K_RETURN:
                        play_sound(SND_MENU)
                        game_state = STATE_SELECT

                elif game_state == STATE_SELECT:
                    if event.key == pygame.K_m:
                        vs_cpu = not vs_cpu
                        play_sound(SND_MENU)

                    if event.key == pygame.K_n:
                        order = ["EASY", "NORMAL", "HARD"]
                        idx = order.index(cpu_difficulty)
                        cpu_difficulty = order[(idx + 1) % len(order)]
                        play_sound(SND_MENU)

                    if not p1_locked:
                        if event.key == pygame.K_a:
                            p1_selection = (p1_selection - 1) % len(CHARACTERS)
                            play_sound(SND_MENU)
                        if event.key == pygame.K_d:
                            p1_selection = (p1_selection + 1) % len(CHARACTERS)
                            play_sound(SND_MENU)
                        if event.key == pygame.K_f:
                            p1_locked = True
                            play_sound(SND_MENU)

                    if not p2_locked:
                        if event.key == pygame.K_LEFT:
                            p2_selection = (p2_selection - 1) % len(CHARACTERS)
                            play_sound(SND_MENU)
                        if event.key == pygame.K_RIGHT:
                            p2_selection = (p2_selection + 1) % len(CHARACTERS)
                            play_sound(SND_MENU)
                        if event.key == pygame.K_p:
                            p2_locked = True
                            play_sound(SND_MENU)

                    if p1_locked and p2_locked and event.key == pygame.K_RETURN:
                        play_sound(SND_MENU)
                        setup_new_match()
                        game_state = STATE_FIGHT

                elif game_state == STATE_FIGHT:
                    if event.key == pygame.K_ESCAPE:
                        play_sound(SND_MENU)
                        game_state = STATE_PAUSED
                    elif round_intro_timer <= 0 and not round_over and hit_pause_timer <= 0:
                        if event.key == pygame.K_f:
                            if p1.crouching:
                                p1.low_attack()
                            else:
                                p1.attack()
                        if event.key == pygame.K_r:
                            p1.kick()
                        if event.key == pygame.K_t:
                            p1.dash(keys[pygame.K_a], keys[pygame.K_d])

                        if event.key == pygame.K_g and p1.stamina >= p1.fireball_cost:
                            p1.stamina -= p1.fireball_cost
                            fireball_speed = 14
                            fireball_w = 40
                            fireball_h = 20

                            if p1.special == "strong_fireball":
                                fireball_speed = 16
                                fireball_w = 55
                                fireball_h = 24

                            fireballs.append({
                                "rect": pygame.Rect(p1.rect.centerx, p1.rect.y + 40, fireball_w, fireball_h),
                                "vx": (1 if p1.facing_right else -1) * fireball_speed,
                                "owner": p1,
                                "damage": p1.fireball_damage,
                                "kind": "normal",
                            })
                            play_sound(SND_FIREBALL)

                        if event.key == pygame.K_h:
                            p1.use_ultimate(fireballs)

                        if not vs_cpu:
                            if event.key == pygame.K_p:
                                if p2.crouching:
                                    p2.low_attack()
                                else:
                                    p2.attack()
                            if event.key == pygame.K_o:
                                p2.kick()
                            if event.key == pygame.K_u:
                                p2.dash(keys[pygame.K_LEFT], keys[pygame.K_RIGHT])

                            if event.key == pygame.K_LEFTBRACKET and p2.stamina >= p2.fireball_cost:
                                p2.stamina -= p2.fireball_cost
                                fireball_speed = 14
                                fireball_w = 40
                                fireball_h = 20

                                if p2.special == "strong_fireball":
                                    fireball_speed = 16
                                    fireball_w = 55
                                    fireball_h = 24

                                fireballs.append({
                                    "rect": pygame.Rect(p2.rect.centerx, p2.rect.y + 40, fireball_w, fireball_h),
                                    "vx": (1 if p2.facing_right else -1) * fireball_speed,
                                    "owner": p2,
                                    "damage": p2.fireball_damage,
                                    "kind": "normal",
                                })
                                play_sound(SND_FIREBALL)

                            if event.key == pygame.K_RIGHTBRACKET:
                                p2.use_ultimate(fireballs)

                elif game_state == STATE_PAUSED:
                    if event.key == pygame.K_RETURN:
                        play_sound(SND_MENU)
                        game_state = STATE_FIGHT
                    elif event.key == pygame.K_r:
                        play_sound(SND_MENU)
                        setup_new_match()
                        game_state = STATE_FIGHT
                    elif event.key == pygame.K_c:
                        play_sound(SND_MENU)
                        reset_to_character_select()
                    elif event.key == pygame.K_ESCAPE:
                        return

                elif game_state == STATE_GAME_OVER:
                    if event.key == pygame.K_r:
                        play_sound(SND_MENU)
                        setup_new_match()
                        game_state = STATE_FIGHT
                    elif event.key == pygame.K_c:
                        play_sound(SND_MENU)
                        reset_to_character_select()
                    elif event.key == pygame.K_ESCAPE:
                        return

        if game_state == STATE_TITLE:
            draw_title_screen(world_surface)
        elif game_state == STATE_SELECT:
            draw_character_select(world_surface)
        elif game_state == STATE_FIGHT:
            draw_fight_scene(world_surface)
        elif game_state == STATE_PAUSED:
            draw_fight_scene(world_surface)
            draw_pause_menu(world_surface)
        elif game_state == STATE_GAME_OVER:
            draw_game_over(world_surface)

        main_screen.fill(BLACK)
        main_screen.blit(world_surface, (shake_x, shake_y))
        pygame.display.flip()
        clock.tick(FPS)
        await asyncio.sleep(0)

asyncio.run(main())
