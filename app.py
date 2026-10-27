# /// script
# requires-python = ">=3.10"
# dependencies = ["opencv-python<5", "pygame-ce"]
# ///
"""A local, distance-responsive sensory light canvas.

Run with: uv run app.py

The camera is opened only after SPACE is pressed. Frames are processed locally:
they are never shown, saved, or sent anywhere. Haar detection locates a face;
the face box's relative area is only a rough near/far cue, not a measurement.
"""

from __future__ import annotations

import colorsys
import math
import random
import time
from pathlib import Path

import cv2
import pygame

WIDTH, HEIGHT = 1000, 700
FPS = 30
NEUTRAL = (7, 6, 2)
FAR_BACKGROUND = (7, 6, 2)
FAR_FACE_AREA = 0.010
NEAR_FACE_AREA = 0.10
SMOOTHING_SECONDS = 0.75


def mix_color(start: tuple[int, int, int], end: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    """Blend RGB colors gradually."""
    amount = max(0.0, min(1.0, amount))
    return tuple(round(a + (b - a) * amount) for a, b in zip(start, end))


def hsv_rgb(hue: float, saturation: float, value: float) -> tuple[int, int, int]:
    """Convert an HSV palette choice to the RGB values Pygame draws."""
    red, green, blue = colorsys.hsv_to_rgb(hue % 1.0, saturation, value)
    return round(red * 255), round(green * 255), round(blue * 255)


class SensoryCanvas:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Signal Garden | Distance-Responsive Sensory Canvas")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.title_font = pygame.font.SysFont("segoeui", 31, bold=True)
        self.body_font = pygame.font.SysFont("segoeui", 19)
        self.small_font = pygame.font.SysFont("segoeui", 15)
        self.glow_layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.particles = self.make_pigment()
        self.streaks = self.make_streaks()
        self.idle_glitches = self.make_idle_glitches()

        self.mode = "idle"  # idle, camera, or manual demo
        self.capture: cv2.VideoCapture | None = None
        self.detector: cv2.CascadeClassifier | None = None
        self.message = "Press SPACE to start the camera, or M for keyboard demo."
        self.manual_level = 0.0
        self.manual_present = False
        self.level = 0.0
        self.background = NEUTRAL
        self.orb_x = WIDTH * 0.5
        self.orb_y = HEIGHT * 0.48
        self.target_x = self.orb_x
        self.target_y = self.orb_y
        self.last_time = time.monotonic()
        self.running = True

    def make_pigment(self) -> list[tuple[float, float, float, tuple[int, int, int], int]]:
        """Build a fixed, sharp-edged field of neon fragments."""
        rng = random.Random(23)
        palette = [
            (255, 25, 150),  # neon pink
            (255, 62, 177),
            (30, 255, 112),  # fluorescent green
            (91, 255, 162),
        ]
        lobes = [
            (-0.34, -0.18, 0.20, 0.18, 100),
            (0.34, -0.18, 0.20, 0.18, 100),
            (-0.29, 0.18, 0.21, 0.16, 95),
            (0.29, 0.18, 0.21, 0.16, 95),
            (0.0, 0.0, 0.08, 0.32, 100),
        ]
        pigment = []
        for center_x, center_y, spread_x, spread_y, count in lobes:
            for _ in range(count):
                x = max(-0.95, min(0.95, rng.gauss(center_x, spread_x * 0.52)))
                y = max(-0.9, min(0.9, rng.gauss(center_y, spread_y * 0.52)))
                distance = ((x - center_x) / spread_x) ** 2 + ((y - center_y) / spread_y) ** 2
                edge = max(0.10, math.exp(-0.28 * distance))
                pigment.append((x, y, rng.uniform(0.48, 1.0) * edge,
                                rng.choice(palette), rng.choice((2, 3, 4))))
        return pigment

    def make_streaks(self) -> list[tuple[float, float, float, float, tuple[int, int, int], int]]:
        """Create stable broken scan streaks; their geometry never flickers."""
        rng = random.Random(91)
        palette = [(255, 25, 150), (30, 255, 112)]
        return [(rng.uniform(-0.95, 0.95), rng.uniform(-0.82, 0.82),
                 rng.uniform(0.24, 1.0), rng.uniform(-0.16, 0.16),
                 rng.choice(palette), rng.choice((4, 7, 11, 15))) for _ in range(62)]
    def make_idle_glitches(self) -> list[tuple[int, int, int, tuple[int, int, int], int]]:
        """Make faint, fixed glitch marks visible even before a face is detected."""
        rng = random.Random(2026)
        colors = [(30, 255, 112), (255, 25, 150), (101, 110, 67)]
        return [(rng.randrange(WIDTH), rng.randrange(HEIGHT), rng.randrange(18, 115),
                 rng.choice(colors), rng.choice((1, 1, 2))) for _ in range(34)]

    def draw_idle_glitches(self) -> None:
        """Show a quiet, non-flickering trace on the empty dark canvas."""
        self.glow_layer.fill((0, 0, 0, 0))
        for x, y, length, color, thickness in self.idle_glitches:
            tint = (color[0], color[1], color[2], 30 if color != (101, 110, 67) else 24)
            pygame.draw.line(self.glow_layer, tint, (x, y), (min(WIDTH, x + length), y), thickness)
        self.screen.blit(self.glow_layer, (0, 0))

    def close_camera(self) -> None:
        if self.capture is not None:
            self.capture.release()
            self.capture = None
        if self.mode == "camera":
            self.mode = "idle"

    def start_camera(self) -> None:
        self.close_camera()
        try:
            cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
            detector = cv2.CascadeClassifier(str(cascade_path))
            if detector.empty():
                raise RuntimeError("Could not load the built-in face detector.")
            capture = cv2.VideoCapture(0)
            if not capture.isOpened():
                capture.release()
                raise RuntimeError("Camera unavailable. Check camera permission or use the keyboard demo.")
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.detector = detector
            self.capture = capture
            self.mode = "camera"
            self.message = "Camera runs on this computer only. Move closer or step back slowly."
        except (AttributeError, RuntimeError, cv2.error) as error:
            self.mode = "idle"
            self.message = f"{error} Press M for keyboard demo or SPACE to retry."

    def read_camera_input(self) -> tuple[bool, float, float, float]:
        """Return face presence, relative closeness, and a target position."""
        if self.capture is None or self.detector is None:
            return False, 0.0, self.orb_x, self.orb_y
        ok, frame = self.capture.read()
        if not ok or frame is None:
            self.close_camera()
            self.message = "Camera feed interrupted. Press SPACE to retry or M for keyboard demo."
            return False, 0.0, self.orb_x, self.orb_y

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.detector.detectMultiScale(
            gray, scaleFactor=1.15, minNeighbors=5, minSize=(48, 48)
        )
        if len(faces) == 0:
            return False, 0.0, self.orb_x, self.orb_y

        x, y, width, height = max(faces, key=lambda box: int(box[2]) * int(box[3]))
        frame_height, frame_width = gray.shape[:2]
        face_area = (int(width) * int(height)) / max(1, frame_width * frame_height)
        span = max(0.001, NEAR_FACE_AREA - FAR_FACE_AREA)
        closeness = max(0.0, min(1.0, (face_area - FAR_FACE_AREA) / span))

        # Mirror the light response horizontally, like a gentle mirror.
        target_x = WIDTH * (1.0 - (int(x) + int(width) / 2) / frame_width)
        target_y = HEIGHT * ((int(y) + int(height) / 2) / frame_height)
        return True, closeness, target_x, target_y

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    if self.mode == "camera":
                        self.close_camera()
                        self.message = "Camera off. Press SPACE to start it or M for keyboard demo."
                    else:
                        self.start_camera()
                elif event.key == pygame.K_m:
                    self.close_camera()
                    self.mode = "manual"
                    self.manual_present = True
                    self.message = "Keyboard demo: LEFT steps back; RIGHT moves closer."
                elif event.key == pygame.K_r and self.mode == "manual":
                    self.manual_level = 0.0
                    self.manual_present = False
                    self.message = "Demo reset. Press LEFT or RIGHT to begin."
                elif self.mode == "manual" and event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    self.manual_present = True
                    step = 0.08 if event.key == pygame.K_RIGHT else -0.08
                    self.manual_level = max(0.0, min(1.0, self.manual_level + step))

    def input_state(self) -> tuple[bool, float, float, float, str]:
        if self.mode == "camera":
            present, closeness, target_x, target_y = self.read_camera_input()
            if not present:
                return False, 0.0, target_x, target_y, "No face detected · the canvas stays still"
            if closeness >= 0.88:
                label = "Very close · the signal gently recedes"
            elif closeness >= 0.35:
                label = "Closer · the signal grows brighter and more fragmented"
            else:
                label = "Farther away · a quieter, smaller signal"
            return True, closeness, target_x, target_y, label
        if self.mode == "manual":
            label = "Keyboard demo · farther away" if self.manual_level < 0.35 else "Keyboard demo · moving closer"
            return self.manual_present, self.manual_level, self.orb_x, self.orb_y, label
        return False, 0.0, self.orb_x, self.orb_y, self.message

    def draw_glow(self, closeness: float) -> None:
        """Draw a high-contrast, fragmented signal with fixed scanline geometry."""
        if closeness <= 0.0 or closeness >= 0.88:
            return
        self.glow_layer.fill((0, 0, 0, 0))
        amount = max(0.0, min(1.0, closeness))
        fade = max(0.0, min(1.0, (0.88 - amount) / 0.20))
        opacity = (0.26 + 0.72 * amount) * fade
        bloom_width = 260 + 390 * amount
        bloom_height = 190 + 310 * amount

        for nx, ny, pigment_strength, color, base_size in self.particles:
            x = round(self.orb_x + nx * bloom_width)
            y = round(self.orb_y + ny * bloom_height)
            alpha = round(220 * opacity * pigment_strength)
            if alpha < 3 or x < 0 or y < 0 or x >= WIDTH or y >= HEIGHT:
                continue
            radius = max(1, round(base_size * (0.75 + amount * 1.15)))
            points = [(x, y - radius * 2), (x + radius, y),
                      (x, y + radius), (x - radius * 2, y + radius // 2)]
            pygame.draw.polygon(self.glow_layer, (*color, alpha), points)
        for nx, ny, length, tilt, color, thickness in self.streaks:
            x = round(self.orb_x + nx * bloom_width)
            y = round(self.orb_y + ny * bloom_height)
            end_x = x + round(length * bloom_width)
            end_y = y + round(tilt * bloom_height)
            alpha = round((55 + 125 * amount) * opacity)
            pygame.draw.line(self.glow_layer, (*color, alpha), (x, y),
                             (end_x, end_y), max(1, round(thickness * (0.7 + amount))))

        scan_alpha = round(18 + 36 * amount)
        for offset in range(-int(bloom_height), int(bloom_height), 13):
            y = round(self.orb_y + offset)
            pygame.draw.line(self.glow_layer, (154, 255, 197, scan_alpha),
                             (max(0, round(self.orb_x - bloom_width)), y),
                             (min(WIDTH, round(self.orb_x + bloom_width)), y), 1)
        self.screen.blit(self.glow_layer, (0, 0))
    def draw(self, present: bool, target_level: float, label: str, dt: float) -> None:
        easing = 1.0 - math.exp(-dt / SMOOTHING_SECONDS)
        self.level += (target_level - self.level) * easing
        too_close = max(0.0, min(1.0, (self.level - 0.82) / 0.18)) if present else 0.0

        base = FAR_BACKGROUND
        self.background = mix_color(self.background, base, easing)
        self.screen.fill(self.background)
        self.draw_idle_glitches()

        if present:
            pos_easing = min(1.0, easing * 1.8)
            self.orb_x += (self.target_x - self.orb_x) * pos_easing
            self.orb_y += (self.target_y - self.orb_y) * pos_easing
            self.draw_glow(self.level)

        light_text = True
        title_color = (235, 245, 242)
        body_color = (159, 179, 179)
        title = self.title_font.render("SIGNAL GARDEN", True, title_color)
        subtitle = self.body_font.render("Move closer to intensify the signal. Step back to soften it.", True, body_color)
        self.screen.blit(title, (40, 32))
        self.screen.blit(subtitle, (42, 75))

        state = self.body_font.render(label, True, title_color)
        self.screen.blit(state, (42, HEIGHT - 112))
        controls = "SPACE camera on/off   ·   M keyboard demo   ·   LEFT farther / RIGHT closer   ·   R reset   ·   ESC quit"
        help_text = self.small_font.render(controls, True, body_color)
        self.screen.blit(help_text, (42, HEIGHT - 73))
        privacy = self.small_font.render(
            "Abstract metaphor for sensory overload; experiences differ. No emotion detection. Camera stays local.",
            True,
            body_color,
        )
        self.screen.blit(privacy, (42, HEIGHT - 48))
        pygame.display.flip()

    def run(self) -> None:
        while self.running:
            self.handle_events()
            now = time.monotonic()
            dt = max(0.0, min(0.1, now - self.last_time))
            self.last_time = now
            present, target, target_x, target_y, label = self.input_state()
            if present:
                self.target_x, self.target_y = target_x, target_y
            self.draw(present, target, label, dt)
            self.clock.tick(FPS)
        self.close_camera()
        pygame.quit()


if __name__ == "__main__":
    SensoryCanvas().run()












