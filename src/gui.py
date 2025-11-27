"""
Earworm - Enhanced GUI window for STT status display.
Features smooth transitions, fluid animations, and modern visual design.
"""

import tkinter as tk
from tkinter import ttk
import threading
import math
import time
from typing import Callable, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
from PIL import Image, ImageDraw, ImageTk, ImageFilter


# =============================================================================
# Utility Functions
# =============================================================================

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb: Tuple[float, float, float]) -> str:
    """Convert RGB tuple to hex color."""
    return '#{:02x}{:02x}{:02x}'.format(
        max(0, min(255, int(rgb[0]))),
        max(0, min(255, int(rgb[1]))),
        max(0, min(255, int(rgb[2])))
    )


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation."""
    return a + (b - a) * t


def lerp_color(color1: str, color2: str, t: float) -> str:
    """Linearly interpolate between two hex colors."""
    r1, g1, b1 = hex_to_rgb(color1)
    r2, g2, b2 = hex_to_rgb(color2)
    return rgb_to_hex((lerp(r1, r2, t), lerp(g1, g2, t), lerp(b1, b2, t)))


def ease_out_cubic(t: float) -> float:
    """Cubic ease-out function for smooth deceleration."""
    return 1 - pow(1 - t, 3)


def ease_in_out_sine(t: float) -> float:
    """Sine ease-in-out for smooth oscillation."""
    return -(math.cos(math.pi * t) - 1) / 2


def ease_out_elastic(t: float) -> float:
    """Elastic ease-out for bouncy effect."""
    if t == 0 or t == 1:
        return t
    return pow(2, -10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi) / 3) + 1


def ease_out_back(t: float) -> float:
    """Back ease-out for overshoot effect."""
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)


def create_ear_icon(size: int = 32, color: str = "#4CAF50") -> Image.Image:
    """Create an ear-shaped icon programmatically."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    s = size / 64

    margin = int(2 * s)
    draw.ellipse([margin, margin, size - margin, size - margin],
                 fill="#1e1e1e", outline=color, width=max(1, int(2 * s)))

    ear_points = [
        (40 * s, 12 * s), (50 * s, 20 * s), (52 * s, 32 * s),
        (48 * s, 44 * s), (40 * s, 50 * s), (32 * s, 50 * s),
        (28 * s, 46 * s), (30 * s, 40 * s), (34 * s, 44 * s),
        (40 * s, 40 * s), (44 * s, 32 * s), (42 * s, 22 * s),
        (34 * s, 16 * s), (26 * s, 20 * s), (22 * s, 30 * s),
        (24 * s, 42 * s),
    ]

    for i in range(len(ear_points) - 1):
        draw.line([ear_points[i], ear_points[i + 1]], fill=color, width=max(2, int(3 * s)))

    wave_color = color
    draw.arc([int(8 * s), int(24 * s), int(18 * s), int(40 * s)],
             start=60, end=300, fill=wave_color, width=max(1, int(2 * s)))
    draw.arc([int(2 * s), int(20 * s), int(14 * s), int(44 * s)],
             start=60, end=300, fill=wave_color, width=max(1, int(2 * s)))

    return img


# =============================================================================
# Animation System
# =============================================================================

@dataclass
class AnimatedValue:
    """Represents a value that animates smoothly between targets."""
    current: float
    target: float
    velocity: float = 0.0

    def update(self, damping: float = 0.15, speed: float = 0.3) -> bool:
        """Update using spring physics. Returns True if still animating."""
        diff = self.target - self.current
        self.velocity = self.velocity * (1 - damping) + diff * speed
        self.current += self.velocity

        # Check if settled
        if abs(diff) < 0.001 and abs(self.velocity) < 0.001:
            self.current = self.target
            self.velocity = 0
            return False
        return True

    def set_target(self, target: float) -> None:
        """Set new target value."""
        self.target = target

    def set_immediate(self, value: float) -> None:
        """Set value immediately without animation."""
        self.current = value
        self.target = value
        self.velocity = 0


class AnimatedColor:
    """Animates smoothly between colors."""

    def __init__(self, initial: str):
        self._r = AnimatedValue(0, 0)
        self._g = AnimatedValue(0, 0)
        self._b = AnimatedValue(0, 0)
        self.set_immediate(initial)

    @property
    def current(self) -> str:
        return rgb_to_hex((self._r.current, self._g.current, self._b.current))

    def set_target(self, color: str) -> None:
        r, g, b = hex_to_rgb(color)
        self._r.set_target(r)
        self._g.set_target(g)
        self._b.set_target(b)

    def set_immediate(self, color: str) -> None:
        r, g, b = hex_to_rgb(color)
        self._r.set_immediate(r)
        self._g.set_immediate(g)
        self._b.set_immediate(b)

    def update(self, damping: float = 0.12, speed: float = 0.25) -> bool:
        a1 = self._r.update(damping, speed)
        a2 = self._g.update(damping, speed)
        a3 = self._b.update(damping, speed)
        return a1 or a2 or a3


# =============================================================================
# Main Status Window
# =============================================================================

class StatusWindow:
    """
    Enhanced status window with fluid animations and modern design.

    Features:
    - Smooth state transitions with spring physics
    - Real-time audio level visualization
    - Recording timer
    - Particle effects
    - Glow and gradient effects
    """

    STATE_IDLE = "idle"
    STATE_RECORDING = "recording"
    STATE_PROCESSING = "processing"

    # Enhanced color scheme with gradients
    COLORS = {
        "bg": "#0a0a0a",
        "bg_secondary": "#141414",
        "bg_elevated": "#1a1a1a",
        "border": "#2a2a2a",

        "idle": "#00d26a",
        "idle_glow": "#00ff88",
        "idle_dim": "#00a855",

        "recording": "#ff4757",
        "recording_glow": "#ff6b7a",
        "recording_dim": "#cc3945",

        "processing": "#ffa502",
        "processing_glow": "#ffbe33",
        "processing_dim": "#cc8400",

        "success": "#00d26a",
        "info": "#3b82f6",
        "warning": "#f59e0b",
        "error": "#ef4444",

        "text": "#ffffff",
        "text_secondary": "#a0a0a0",
        "text_dim": "#666666",
    }

    def __init__(self):
        self._root: Optional[tk.Tk] = None
        self._canvas: Optional[tk.Canvas] = None
        self._state = self.STATE_IDLE
        self._previous_state = self.STATE_IDLE
        self._callbacks = {}
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._icon_photo = None
        self._animation_id = None
        self._frame = 0

        # Window state
        self._width = 240
        self._height = 90
        self._drag_x = 0
        self._drag_y = 0

        # Animation state
        self._transition_progress = AnimatedValue(1.0, 1.0)
        self._primary_color = AnimatedColor(self.COLORS["idle"])
        self._glow_intensity = AnimatedValue(0.5, 0.5)
        self._indicator_scale = AnimatedValue(1.0, 1.0)
        self._text_opacity = AnimatedValue(1.0, 1.0)

        # Recording state
        self._recording_start_time: Optional[float] = None
        self._audio_level = AnimatedValue(0.0, 0.0)
        self._audio_levels_history: List[float] = [0.0] * 30

        # Particles for effects
        self._particles: List[dict] = []

        # Canvas item IDs
        self._bg_rect = None
        self._indicator_items: List[int] = []
        self._text_items: List[int] = []
        self._waveform_items: List[int] = []
        self._glow_image = None
        self._glow_photo = None
        self._glow_item = None

    def _create_window(self) -> None:
        """Create the tkinter window with enhanced canvas-based UI."""
        self._root = tk.Tk()
        self._root.title("Earworm")
        self._root.attributes('-topmost', True)
        self._root.resizable(False, False)
        self._root.overrideredirect(True)

        # Transparency (Windows)
        try:
            self._root.attributes('-transparentcolor', '#010101')
        except tk.TclError:
            pass

        # Set window icon
        try:
            icon = create_ear_icon(32, self.COLORS["idle"])
            self._icon_photo = ImageTk.PhotoImage(icon)
            self._root.iconphoto(True, self._icon_photo)
        except (tk.TclError, OSError):
            pass

        # Position bottom-right
        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        x = screen_w - self._width - 20
        y = screen_h - self._height - 60
        self._root.geometry(f"{self._width}x{self._height}+{x}+{y}")

        # Main canvas
        self._canvas = tk.Canvas(
            self._root,
            width=self._width,
            height=self._height,
            bg=self.COLORS["bg"],
            highlightthickness=0
        )
        self._canvas.pack(fill=tk.BOTH, expand=True)

        # Draw static background
        self._draw_background()

        # Initial state
        self._setup_state_visuals()

        # Event bindings
        self._canvas.bind("<Button-1>", self._start_drag)
        self._canvas.bind("<B1-Motion>", self._drag)
        self._canvas.bind("<Button-3>", lambda e: self._on_close())
        self._canvas.bind("<Enter>", self._on_hover_enter)
        self._canvas.bind("<Leave>", self._on_hover_leave)

        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._ready.set()

        # Start animation loop at 60 FPS
        self._animate()

    def _draw_background(self) -> None:
        """Draw the static background elements."""
        # Outer glow/shadow effect
        self._canvas.create_rectangle(
            0, 0, self._width, self._height,
            fill=self.COLORS["bg"],
            outline=""
        )

        # Main rounded rectangle with subtle border
        self._bg_rect = self._draw_rounded_rect(
            3, 3, self._width - 3, self._height - 3,
            radius=18,
            fill=self.COLORS["bg_secondary"],
            outline=self.COLORS["border"],
            width=1
        )

    def _draw_rounded_rect(
        self, x1: int, y1: int, x2: int, y2: int,
        radius: int, fill: str, outline: str = "", width: int = 0
    ) -> int:
        """Draw a rounded rectangle on the canvas."""
        points = []
        # Top-left corner
        for i in range(90, 181, 10):
            points.append(x1 + radius + radius * math.cos(math.radians(i)))
            points.append(y1 + radius + radius * math.sin(math.radians(i)))
        # Bottom-left corner
        for i in range(180, 271, 10):
            points.append(x1 + radius + radius * math.cos(math.radians(i)))
            points.append(y2 - radius + radius * math.sin(math.radians(i)))
        # Bottom-right corner
        for i in range(270, 361, 10):
            points.append(x2 - radius + radius * math.cos(math.radians(i)))
            points.append(y2 - radius + radius * math.sin(math.radians(i)))
        # Top-right corner
        for i in range(0, 91, 10):
            points.append(x2 - radius + radius * math.cos(math.radians(i)))
            points.append(y1 + radius + radius * math.sin(math.radians(i)))

        return self._canvas.create_polygon(
            points,
            fill=fill,
            outline=outline,
            width=width,
            smooth=True
        )

    def _setup_state_visuals(self) -> None:
        """Setup visuals for the current state."""
        # Clear previous items
        for item in self._indicator_items + self._text_items + self._waveform_items:
            self._canvas.delete(item)
        self._indicator_items = []
        self._text_items = []
        self._waveform_items = []

        if self._glow_item:
            self._canvas.delete(self._glow_item)
            self._glow_item = None

        # Get state-specific colors
        if self._state == self.STATE_IDLE:
            color = self.COLORS["idle"]
            glow_color = self.COLORS["idle_glow"]
            main_text = "Ready"
            sub_text = "Hold F9 to speak"
        elif self._state == self.STATE_RECORDING:
            color = self.COLORS["recording"]
            glow_color = self.COLORS["recording_glow"]
            main_text = "Listening"
            sub_text = "Release to finish"
            self._recording_start_time = time.time()
        else:  # processing
            color = self.COLORS["processing"]
            glow_color = self.COLORS["processing_glow"]
            main_text = "Transcribing"
            sub_text = "Please wait..."
            self._recording_start_time = None

        # Animate to new colors
        self._primary_color.set_target(color)

        # Create glow effect
        self._create_glow_effect(glow_color)

        # Create indicator based on state
        self._create_indicator()

        # Create text
        self._create_text(main_text, sub_text)

    def _create_glow_effect(self, color: str) -> None:
        """Create a soft glow effect behind the indicator."""
        size = 60
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        r, g, b = hex_to_rgb(color)
        center = size // 2

        # Draw multiple circles with decreasing opacity
        for i in range(center, 0, -2):
            alpha = int(80 * (i / center) ** 2)
            draw.ellipse(
                [center - i, center - i, center + i, center + i],
                fill=(r, g, b, alpha)
            )

        # Apply blur
        img = img.filter(ImageFilter.GaussianBlur(radius=8))

        self._glow_image = img
        self._glow_photo = ImageTk.PhotoImage(img)
        self._glow_item = self._canvas.create_image(
            45, 45,
            image=self._glow_photo,
            tags="glow"
        )
        self._canvas.tag_lower(self._glow_item)

    def _create_indicator(self) -> None:
        """Create the state indicator (circle, waveform, or spinner)."""
        cx, cy = 45, 45

        if self._state == self.STATE_IDLE:
            # Simple pulsing circle
            item = self._canvas.create_oval(
                cx - 14, cy - 14, cx + 14, cy + 14,
                fill=self._primary_color.current,
                outline="",
                tags="indicator"
            )
            self._indicator_items.append(item)

        elif self._state == self.STATE_RECORDING:
            # Waveform bars
            bar_count = 7
            bar_width = 4
            bar_gap = 2
            total_width = bar_count * bar_width + (bar_count - 1) * bar_gap
            start_x = cx - total_width // 2

            for i in range(bar_count):
                x = start_x + i * (bar_width + bar_gap)
                item = self._canvas.create_rectangle(
                    x, cy - 10,
                    x + bar_width, cy + 10,
                    fill=self._primary_color.current,
                    outline="",
                    tags="indicator"
                )
                self._indicator_items.append(item)

        else:  # processing
            # Spinning arc segments
            radius = 14
            for i in range(3):
                item = self._canvas.create_arc(
                    cx - radius, cy - radius,
                    cx + radius, cy + radius,
                    start=i * 120,
                    extent=60,
                    style=tk.ARC,
                    outline=self._primary_color.current,
                    width=3,
                    tags="indicator"
                )
                self._indicator_items.append(item)

    def _create_text(self, main: str, sub: str) -> None:
        """Create the text labels."""
        # Main status text
        item = self._canvas.create_text(
            145, 35,
            text=main,
            font=("Segoe UI", 15, "bold"),
            fill=self.COLORS["text"],
            anchor="w",
            tags="text"
        )
        self._text_items.append(item)

        # Sub text
        item = self._canvas.create_text(
            145, 58,
            text=sub,
            font=("Segoe UI", 10),
            fill=self.COLORS["text_secondary"],
            anchor="w",
            tags="text"
        )
        self._text_items.append(item)

    def _animate(self) -> None:
        """Main animation loop at 60 FPS."""
        if self._canvas is None or self._root is None:
            return

        self._frame += 1

        # Update animated values
        self._primary_color.update(damping=0.15, speed=0.2)
        self._glow_intensity.update()
        self._indicator_scale.update()
        self._audio_level.update(damping=0.2, speed=0.4)

        # Animate based on state
        if self._state == self.STATE_IDLE:
            self._animate_idle()
        elif self._state == self.STATE_RECORDING:
            self._animate_recording()
        else:
            self._animate_processing()

        # Update particles
        self._update_particles()

        # Schedule next frame (~60 FPS)
        self._animation_id = self._root.after(16, self._animate)

    def _animate_idle(self) -> None:
        """Animate idle state - gentle breathing pulse."""
        if not self._indicator_items:
            return

        cx, cy = 45, 45

        # Breathing effect
        t = self._frame * 0.03
        pulse = (math.sin(t) + 1) / 2  # 0 to 1

        # Scale the circle
        base_radius = 12
        radius = base_radius + pulse * 4

        self._canvas.coords(
            self._indicator_items[0],
            cx - radius, cy - radius,
            cx + radius, cy + radius
        )

        # Color pulse
        color = lerp_color(
            self.COLORS["idle"],
            self.COLORS["idle_glow"],
            pulse * 0.4
        )
        self._canvas.itemconfig(self._indicator_items[0], fill=color)

        # Glow pulse
        if self._glow_item:
            # Update glow opacity via alpha
            self._update_glow_opacity(0.3 + pulse * 0.4)

    def _animate_recording(self) -> None:
        """Animate recording state - dynamic waveform."""
        if not self._indicator_items:
            return

        cx, cy = 45, 45
        bar_count = len(self._indicator_items)
        bar_width = 4
        bar_gap = 2
        total_width = bar_count * bar_width + (bar_count - 1) * bar_gap
        start_x = cx - total_width // 2

        # Get audio level (simulated if not connected)
        level = self._audio_level.current

        for i, item in enumerate(self._indicator_items):
            # Create wave pattern with audio influence
            t = self._frame * 0.12 + i * 0.6

            # Base wave
            wave = math.sin(t) * 0.5 + 0.5

            # Add some variation per bar
            variation = math.sin(t * 1.5 + i * 1.2) * 0.3

            # Combine with audio level
            height = 8 + (wave + variation + level * 0.5) * 14
            height = max(4, min(height, 28))

            x = start_x + i * (bar_width + bar_gap)
            self._canvas.coords(
                item,
                x, cy - height,
                x + bar_width, cy + height
            )

            # Color intensity based on height
            intensity = height / 28
            color = lerp_color(
                self.COLORS["recording"],
                self.COLORS["recording_glow"],
                intensity * 0.7
            )
            self._canvas.itemconfig(item, fill=color)

        # Update recording time in subtext
        if self._recording_start_time and len(self._text_items) > 1:
            elapsed = time.time() - self._recording_start_time
            mins = int(elapsed // 60)
            secs = int(elapsed % 60)
            tenths = int((elapsed % 1) * 10)
            time_str = f"{mins}:{secs:02d}.{tenths}"
            self._canvas.itemconfig(self._text_items[1], text=f"Recording {time_str}")

        # Glow intensity follows audio
        if self._glow_item:
            self._update_glow_opacity(0.4 + level * 0.4)

    def _animate_processing(self) -> None:
        """Animate processing state - smooth spinning arcs."""
        if not self._indicator_items:
            return

        cx, cy = 45, 45
        radius = 14

        # Rotation
        rotation = self._frame * 3

        # Pulsing extent
        t = self._frame * 0.08
        extent_pulse = 50 + math.sin(t) * 20

        for i, item in enumerate(self._indicator_items):
            start_angle = rotation + i * 120

            self._canvas.coords(
                item,
                cx - radius, cy - radius,
                cx + radius, cy + radius
            )
            self._canvas.itemconfig(
                item,
                start=start_angle,
                extent=extent_pulse
            )

            # Color shimmer
            shimmer = (math.sin(t + i * 0.5) + 1) / 2
            color = lerp_color(
                self.COLORS["processing"],
                self.COLORS["processing_glow"],
                shimmer * 0.6
            )
            self._canvas.itemconfig(item, outline=color)

        # Glow pulse
        if self._glow_item:
            pulse = (math.sin(t) + 1) / 2
            self._update_glow_opacity(0.3 + pulse * 0.3)

    def _update_glow_opacity(self, opacity: float) -> None:
        """Update glow effect opacity."""
        if not self._glow_image:
            return

        # Adjust alpha channel
        opacity = max(0, min(1, opacity))

        # Only recreate if opacity changed significantly
        # (to avoid performance issues)
        pass  # Glow is static for now, could enhance later

    def _update_particles(self) -> None:
        """Update particle effects."""
        # Remove dead particles
        self._particles = [p for p in self._particles if p.get('life', 0) > 0]

        # Update remaining particles
        for p in self._particles:
            p['x'] += p.get('vx', 0)
            p['y'] += p.get('vy', 0)
            p['life'] = p.get('life', 0) - 1
            p['vy'] += 0.1  # gravity

            if p.get('canvas_id'):
                alpha = p['life'] / p.get('max_life', 30)
                self._canvas.coords(
                    p['canvas_id'],
                    p['x'] - 2, p['y'] - 2,
                    p['x'] + 2, p['y'] + 2
                )
                # Could update color/opacity here

    def _spawn_particle(self, x: float, y: float, color: str) -> None:
        """Spawn a new particle at the given position."""
        import random

        particle = {
            'x': x,
            'y': y,
            'vx': random.uniform(-2, 2),
            'vy': random.uniform(-3, -1),
            'life': 30,
            'max_life': 30,
            'color': color
        }

        canvas_id = self._canvas.create_oval(
            x - 2, y - 2, x + 2, y + 2,
            fill=color,
            outline="",
            tags="particle"
        )
        particle['canvas_id'] = canvas_id
        self._particles.append(particle)

    def _start_drag(self, event) -> None:
        """Start window drag."""
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag(self, event) -> None:
        """Drag window."""
        x = self._root.winfo_x() + (event.x - self._drag_x)
        y = self._root.winfo_y() + (event.y - self._drag_y)
        self._root.geometry(f"+{x}+{y}")

    def _on_hover_enter(self, event) -> None:
        """Handle mouse hover enter."""
        # Could add hover effects here
        pass

    def _on_hover_leave(self, event) -> None:
        """Handle mouse hover leave."""
        pass

    def _on_close(self) -> None:
        """Handle window close."""
        if "exit" in self._callbacks:
            self._callbacks["exit"]()

    def _run_loop(self) -> None:
        """Run the tkinter main loop."""
        self._create_window()
        self._root.mainloop()

    # ==========================================================================
    # Public API
    # ==========================================================================

    def set_callback(self, action: str, callback: Callable) -> None:
        """Register a callback."""
        self._callbacks[action] = callback

    def set_state(self, state: str) -> None:
        """Update the display state with smooth transition."""
        if state == self._state:
            return

        self._previous_state = self._state
        self._state = state

        if self._root is None:
            return

        def update():
            if self._canvas is None:
                return
            self._setup_state_visuals()

        self._root.after(0, update)

    def set_audio_level(self, level: float) -> None:
        """
        Set the current audio input level (0.0 to 1.0).
        Call this during recording to show real-time audio visualization.
        """
        self._audio_level.set_target(max(0.0, min(1.0, level)))
        self._audio_levels_history.append(level)
        self._audio_levels_history = self._audio_levels_history[-30:]

    def update_title(self, title: str) -> None:
        """Update window title (no-op for borderless window)."""
        pass

    def notify(self, title: str, message: str, type: str = "success") -> None:
        """Show a brief notification with animation."""
        if self._root is None or self._canvas is None:
            return

        def show():
            # Clear current visuals
            for item in self._indicator_items + self._text_items:
                self._canvas.delete(item)
            self._indicator_items = []
            self._text_items = []

            if self._glow_item:
                self._canvas.delete(self._glow_item)
                self._glow_item = None

            cx, cy = 45, 45

            # Choose color based on type
            if type == "success":
                color = self.COLORS["success"]
                icon_type = "check"
            elif type == "error":
                color = self.COLORS["error"]
                icon_type = "x"
            elif type == "warning":
                color = self.COLORS["warning"]
                icon_type = "!"
            else:
                color = self.COLORS["info"]
                icon_type = "i"

            # Create glow
            self._create_glow_effect(color)

            # Draw icon
            if icon_type == "check":
                # Checkmark
                item = self._canvas.create_line(
                    cx - 10, cy,
                    cx - 3, cy + 8,
                    cx + 12, cy - 10,
                    fill=color,
                    width=4,
                    capstyle=tk.ROUND,
                    joinstyle=tk.ROUND,
                    tags="indicator"
                )
                self._indicator_items.append(item)
            elif icon_type == "x":
                # X mark
                item1 = self._canvas.create_line(
                    cx - 8, cy - 8, cx + 8, cy + 8,
                    fill=color, width=4, capstyle=tk.ROUND
                )
                item2 = self._canvas.create_line(
                    cx + 8, cy - 8, cx - 8, cy + 8,
                    fill=color, width=4, capstyle=tk.ROUND
                )
                self._indicator_items.extend([item1, item2])
            else:
                # Circle with letter
                item = self._canvas.create_oval(
                    cx - 12, cy - 12, cx + 12, cy + 12,
                    outline=color, width=3, fill=""
                )
                self._indicator_items.append(item)
                item = self._canvas.create_text(
                    cx, cy,
                    text=icon_type,
                    font=("Segoe UI", 12, "bold"),
                    fill=color
                )
                self._indicator_items.append(item)

            # Text
            item = self._canvas.create_text(
                145, 35,
                text=title,
                font=("Segoe UI", 15, "bold"),
                fill=self.COLORS["text"],
                anchor="w"
            )
            self._text_items.append(item)

            # Truncate message if too long
            if len(message) > 25:
                message = message[:22] + "..."

            item = self._canvas.create_text(
                145, 58,
                text=message,
                font=("Segoe UI", 10),
                fill=self.COLORS["text_secondary"],
                anchor="w"
            )
            self._text_items.append(item)

            # Restore state after delay
            def restore():
                self._setup_state_visuals()

            self._root.after(2000, restore)

        self._root.after(0, show)

    def start(self) -> None:
        """Start the GUI in a background thread."""
        if self._thread is not None:
            return

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)

    def stop(self) -> None:
        """Stop the GUI."""
        if self._animation_id and self._root:
            self._root.after_cancel(self._animation_id)
        if self._root:
            self._root.after(0, self._root.destroy)


# =============================================================================
# Testing
# =============================================================================

if __name__ == "__main__":
    import time
    import random

    print("Testing Enhanced Earworm GUI...")

    window = StatusWindow()
    window.start()

    print("Showing idle state for 3 seconds...")
    time.sleep(3)

    print("Switching to recording state...")
    window.set_state(StatusWindow.STATE_RECORDING)

    # Simulate audio levels
    for _ in range(50):
        window.set_audio_level(random.uniform(0.2, 0.9))
        time.sleep(0.1)

    print("Switching to processing state...")
    window.set_state(StatusWindow.STATE_PROCESSING)
    time.sleep(3)

    print("Showing success notification...")
    window.notify("Transcribed", "Hello world!")
    time.sleep(3)

    print("Back to idle...")
    window.set_state(StatusWindow.STATE_IDLE)
    time.sleep(2)

    print("Done!")
    window.stop()
