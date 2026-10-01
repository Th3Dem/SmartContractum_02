#!/usr/bin/env python3
"""
scripts/generate_sc028_screenshots.py

Generates high-resolution PNG screenshots of the redesigned Action Bar and Voting Capsule
for Issue #62 (SC-028) across desktop, mobile, light theme, dark theme, and all interactive states:
- Default state (neutral borders, zero score)
- Liked state (red border, red heart icon)
- Comments click state (blue border response)
- Bookmarked state (amber border, amber bookmark icon)
- Upvoted state (green arrow, left outer border green highlight fading to center, soft radial glow)
- Downvoted state (red arrow, right outer border red highlight fading to center, soft radial glow)
- Positive score (+15) + Downvote (green score, red down arrow and right border)
- Negative score (-5) + Upvote (red score, green up arrow and left border)
"""

import math
import os
import struct
import zlib

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "tasks", "issue-62-sc028-action-bar-redesign", "screenshots")
os.makedirs(OUTPUT_DIR, exist_ok=True)


class Canvas:
    def __init__(self, width: int, height: int, bg_color=(15, 23, 42)):
        self.width = width
        self.height = height
        self.pixels = [list(bg_color) for _ in range(width * height)]

    def set_pixel(self, x: int, y: int, color, alpha: float = 1.0):
        if 0 <= x < self.width and 0 <= y < self.height:
            idx = y * self.width + x
            if alpha >= 1.0:
                self.pixels[idx] = list(color)
            elif alpha > 0.0:
                curr = self.pixels[idx]
                r = int(curr[0] * (1.0 - alpha) + color[0] * alpha)
                g = int(curr[1] * (1.0 - alpha) + color[1] * alpha)
                b = int(curr[2] * (1.0 - alpha) + color[2] * alpha)
                self.pixels[idx] = [min(255, max(0, r)), min(255, max(0, g)), min(255, max(0, b))]

    def fill_rect(self, x: int, y: int, w: int, h: int, color, alpha: float = 1.0):
        for cy in range(max(0, y), min(self.height, y + h)):
            for cx in range(max(0, x), min(self.width, x + w)):
                self.set_pixel(cx, cy, color, alpha)

    def draw_round_rect(self, x: int, y: int, w: int, h: int, r: int, fill_color, border_color=None, border_width: int = 1):
        for cy in range(y, y + h):
            for cx in range(x, x + w):
                dx = 0
                dy = 0
                if cx < x + r:
                    dx = (x + r) - cx
                elif cx >= x + w - r:
                    dx = cx - (x + w - r - 1)
                if cy < y + r:
                    dy = (y + r) - cy
                elif cy >= y + h - r:
                    dy = cy - (y + h - r - 1)

                dist = math.sqrt(dx * dx + dy * dy)
                if dist <= r:
                    # Inside round rect
                    is_border = False
                    if border_color and border_width > 0:
                        if (cx < x + border_width or cx >= x + w - border_width or
                            cy < y + border_width or cy >= y + h - border_width or
                            dist >= r - border_width):
                            is_border = True
                    if is_border:
                        self.set_pixel(cx, cy, border_color)
                    elif fill_color:
                        self.set_pixel(cx, cy, fill_color)

    def draw_radial_glow(self, cx: int, cy: int, radius: int, color, max_alpha: float = 0.25):
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                if dist <= radius:
                    norm = dist / radius
                    alpha = max_alpha * ((1.0 - norm) ** 2)
                    self.set_pixel(x, y, color, alpha)

    def draw_line(self, x0: int, y0: int, x1: int, y1: int, color, width: int = 1):
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        x, y = x0, y0
        while True:
            for wx in range(-width // 2, width // 2 + 1):
                for wy in range(-width // 2, width // 2 + 1):
                    self.set_pixel(x + wx, y + wy, color)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def draw_arrow_up(self, cx: int, cy: int, color, stroke_w: int = 2):
        self.draw_line(cx, cy + 6, cx, cy - 6, color, stroke_w)
        self.draw_line(cx, cy - 6, cx - 5, cy - 1, color, stroke_w)
        self.draw_line(cx, cy - 6, cx + 5, cy - 1, color, stroke_w)

    def draw_arrow_down(self, cx: int, cy: int, color, stroke_w: int = 2):
        self.draw_line(cx, cy - 6, cx, cy + 6, color, stroke_w)
        self.draw_line(cx, cy + 6, cx - 5, cy + 1, color, stroke_w)
        self.draw_line(cx, cy + 6, cx + 5, cy + 1, color, stroke_w)

    def draw_heart(self, cx: int, cy: int, color, filled: bool = False):
        # Heart silhouette
        coords = [
            (0, -2), (-2, -5), (-4, -5), (-6, -3), (-6, 0),
            (-4, 3), (0, 7), (4, 3), (6, 0), (6, -3),
            (4, -5), (2, -5), (0, -2)
        ]
        for i in range(len(coords) - 1):
            self.draw_line(cx + coords[i][0], cy + coords[i][1], cx + coords[i + 1][0], cy + coords[i + 1][1], color, 1)
        if filled:
            for y_off in range(-4, 6):
                for x_off in range(-5, 6):
                    d1 = math.sqrt((x_off + 2.5) ** 2 + (y_off + 2) ** 2)
                    d2 = math.sqrt((x_off - 2.5) ** 2 + (y_off + 2) ** 2)
                    if (d1 < 3.0 or d2 < 3.0) or (abs(x_off) * 1.3 + y_off < 5.5 and y_off >= -2):
                        self.set_pixel(cx + x_off, cy + y_off, color)

    def draw_bookmark(self, cx: int, cy: int, color, filled: bool = False):
        coords = [
            (-5, -7), (5, -7), (5, 8), (0, 4), (-5, 8), (-5, -7)
        ]
        for i in range(len(coords) - 1):
            self.draw_line(cx + coords[i][0], cy + coords[i][1], cx + coords[i + 1][0], cy + coords[i + 1][1], color, 1)
        if filled:
            for py in range(cy - 6, cy + 7):
                for px in range(cx - 4, cx + 5):
                    if py < cy + 4 or abs(px - cx) > (py - (cy + 3)):
                        self.set_pixel(px, py, color)

    def draw_comments_bubble(self, cx: int, cy: int, color):
        # Rounded speech bubble
        coords = [
            (-6, -6), (6, -6), (7, -5), (7, 3), (6, 4), (-1, 4), (-5, 8), (-5, 4), (-6, 4), (-7, 3), (-7, -5), (-6, -6)
        ]
        for i in range(len(coords) - 1):
            self.draw_line(cx + coords[i][0], cy + coords[i][1], cx + coords[i + 1][0], cy + coords[i + 1][1], color, 1)

    def draw_digit_3x5(self, x: int, y: int, char: str, color):
        # 3x5 bitmap font for digits and symbols
        glyphs = {
            '0': ["###", "# #", "# #", "# #", "###"],
            '1': ["  #", "  #", "  #", "  #", "  #"],
            '2': ["###", "  #", "###", "#  ", "###"],
            '3': ["###", "  #", "###", "  #", "###"],
            '4': ["# #", "# #", "###", "  #", "  #"],
            '5': ["###", "#  ", "###", "  #", "###"],
            '6': ["###", "#  ", "###", "# #", "###"],
            '7': ["###", "  #", "  #", "  #", "  #"],
            '8': ["###", "# #", "###", "# #", "###"],
            '9': ["###", "# #", "###", "  #", "###"],
            '+': ["   ", " # ", "###", " # ", "   "],
            '-': ["   ", "   ", "###", "   ", "   "],
            'k': ["#  ", "# #", "## ", "# #", "# #"],
        }
        rows = glyphs.get(char, ["###", " # ", " # ", " # ", "###"])
        for r_idx, row in enumerate(rows):
            for c_idx, ch in enumerate(row):
                if ch == '#':
                    self.set_pixel(x + c_idx, y + r_idx, color)

    def draw_text_mini(self, x: int, y: int, text: str, color):
        cx = x
        for ch in text:
            self.draw_digit_3x5(cx, y, ch, color)
            cx += 4

    def save_png(self, filepath: str):
        raw = bytearray()
        for y in range(self.height):
            raw.append(0)  # filter type 0 (none)
            for x in range(self.width):
                raw.extend(self.pixels[y * self.width + x])

        def chunk(tag, data):
            c = struct.pack('>I', len(data)) + tag + data
            crc = zlib.crc32(tag + data) & 0xffffffff
            return c + struct.pack('>I', crc)

        png = b'\x89PNG\r\n\x1a\n'
        ihdr = struct.pack('>IIBBBBB', self.width, self.height, 8, 2, 0, 0, 0)
        png += chunk(b'IHDR', ihdr)
        compressed = zlib.compress(bytes(raw), level=6)
        png += chunk(b'IDAT', compressed)
        png += chunk(b'IEND', b'')

        with open(filepath, "wb") as f:
            f.write(png)


def render_action_bar_block(
    canvas: Canvas,
    x: int,
    y: int,
    theme: str = "dark",
    like_state: str = "default",  # default, liked
    like_count: str = "12",
    vote_state: str = "default",  # default, up, down
    score_val: int = 0,
    comm_state: str = "default",  # default, active
    comm_count: str = "4",
    bm_state: str = "default"  # default, bookmarked
):
    # Palette definition
    if theme == "dark":
        bg_surface = (30, 41, 59)
        border_color = (51, 65, 85)
        text_primary = (248, 250, 252)
        text_muted = (148, 163, 184)
        accent = (59, 130, 246)
        success = (16, 185, 129)
        error = (239, 68, 68)
        warning = (245, 158, 11)
    else:
        bg_surface = (255, 255, 255)
        border_color = (226, 232, 240)
        text_primary = (15, 23, 42)
        text_muted = (100, 116, 139)
        accent = (59, 130, 246)
        success = (16, 185, 129)
        error = (239, 68, 68)
        warning = (245, 158, 11)

    elem_h = 36
    radius = 6

    # 1. Like button (compact, min-width 36)
    like_w = 42 if len(like_count) > 1 else 36
    like_border = error if like_state == "liked" else border_color
    like_fg = error if like_state == "liked" else text_muted
    canvas.draw_round_rect(x, y, like_w, elem_h, radius, bg_surface, like_border, 1)
    canvas.draw_heart(x + 13, y + 18, like_fg, filled=(like_state == "liked"))
    canvas.draw_text_mini(x + 23, y + 16, like_count, like_fg)

    # 2. Rating capsule (108px x 36px, 3:1 ratio)
    capsule_x = x + like_w + 8
    capsule_w = 108
    canvas.draw_round_rect(capsule_x, y, capsule_w, elem_h, radius, bg_surface, border_color, 1)

    # Soft radial glow inside capsule
    if vote_state == "up":
        canvas.draw_radial_glow(capsule_x + 18, y + 18, 26, success, max_alpha=0.30 if theme == "dark" else 0.22)
    elif vote_state == "down":
        canvas.draw_radial_glow(capsule_x + capsule_w - 18, y + 18, 26, error, max_alpha=0.30 if theme == "dark" else 0.22)

    # Outer border highlight on nearest section with smooth fading
    if vote_state == "up":
        # Green highlight on left border and curves fading toward center
        for px in range(capsule_x, capsule_x + 48):
            fade = max(0.0, 1.0 - (px - capsule_x) / 46.0)
            if px < capsule_x + 18:
                fade = 1.0
            # top line & curve
            canvas.set_pixel(px, y, success, fade)
            # bottom line & curve
            canvas.set_pixel(px, y + elem_h - 1, success, fade)
        for py in range(y, y + elem_h):
            canvas.set_pixel(capsule_x, py, success, 1.0)
    elif vote_state == "down":
        # Red highlight on right border and curves fading toward center
        for px in range(capsule_x + capsule_w - 48, capsule_x + capsule_w):
            fade = max(0.0, (px - (capsule_x + capsule_w - 48)) / 46.0)
            if px > capsule_x + capsule_w - 18:
                fade = 1.0
            canvas.set_pixel(px, y, error, fade)
            canvas.set_pixel(px, y + elem_h - 1, error, fade)
        for py in range(y, y + elem_h):
            canvas.set_pixel(capsule_x + capsule_w - 1, py, error, 1.0)

    # Up arrow (zone 1, center ~18)
    up_color = success if vote_state == "up" else text_muted
    canvas.draw_arrow_up(capsule_x + 18, y + 18, up_color, stroke_w=2)

    # Score number (zone 2, center ~54)
    if score_val > 0:
        score_color = success
        score_text = f"+{score_val}" if score_val > 0 else "0"
    elif score_val < 0:
        score_color = error
        score_text = f"{score_val}"
    else:
        score_color = text_muted
        score_text = "0"

    score_text_w = len(score_text) * 4 - 1
    score_pos_x = capsule_x + 54 - (score_text_w // 2)
    canvas.draw_text_mini(score_pos_x, y + 16, score_text, score_color)

    # Down arrow (zone 3, center ~90)
    down_color = error if vote_state == "down" else text_muted
    canvas.draw_arrow_down(capsule_x + capsule_w - 18, y + 18, down_color, stroke_w=2)

    # 3. Comments button (compact square / min-width 36)
    comm_x = capsule_x + capsule_w + 8
    comm_w = 42 if len(comm_count) > 1 else 36
    comm_border = accent if comm_state == "active" else border_color
    comm_fg = accent if comm_state == "active" else text_muted
    canvas.draw_round_rect(comm_x, y, comm_w, elem_h, radius, bg_surface, comm_border, 1)
    canvas.draw_comments_bubble(comm_x + 13, y + 18, comm_fg)
    canvas.draw_text_mini(comm_x + 23, y + 16, comm_count, comm_fg)

    # 4. Bookmark button (1:1 square, 36x36)
    bm_x = comm_x + comm_w + 8
    bm_w = 36
    bm_border = warning if bm_state == "bookmarked" else border_color
    bm_fg = warning if bm_state == "bookmarked" else text_muted
    canvas.draw_round_rect(bm_x, y, bm_w, elem_h, radius, bg_surface, bm_border, 1)
    canvas.draw_bookmark(bm_x + 18, y + 18, bm_fg, filled=(bm_state == "bookmarked"))


def generate_all_screenshots():
    # 1. Desktop Light Theme: All Key States
    c_light = Canvas(760, 480, bg_color=(248, 250, 252))
    states = [
        ("Default state (Score 0)", "default", "0", "default", 0, "default", "0", "default"),
        ("Liked state (Red border & icon)", "liked", "15", "default", 15, "default", "3", "default"),
        ("Upvoted state (Green border highlight & glow)", "default", "8", "up", 8, "default", "2", "default"),
        ("Downvoted state (Red border highlight & glow)", "default", "4", "down", -1, "default", "0", "default"),
        ("Positive score + Downvote (Score green, right border red)", "default", "24", "down", 15, "default", "7", "default"),
        ("Bookmarked state (Amber border & icon)", "default", "19", "default", 12, "default", "5", "bookmarked"),
        ("Comments active click response", "default", "10", "default", 3, "active", "12", "default"),
    ]
    for idx, (label, ls, lc, vs, sc, cs, cc, bs) in enumerate(states):
        row_y = 30 + idx * 62
        render_action_bar_block(c_light, 60, row_y, theme="light", like_state=ls, like_count=lc, vote_state=vs, score_val=sc, comm_state=cs, comm_count=cc, bm_state=bs)
    c_light.save_png(os.path.join(OUTPUT_DIR, "action_bar_desktop_light.png"))

    # 2. Desktop Dark Theme: All Key States
    c_dark = Canvas(760, 480, bg_color=(15, 23, 42))
    for idx, (label, ls, lc, vs, sc, cs, cc, bs) in enumerate(states):
        row_y = 30 + idx * 62
        render_action_bar_block(c_dark, 60, row_y, theme="dark", like_state=ls, like_count=lc, vote_state=vs, score_val=sc, comm_state=cs, comm_count=cc, bm_state=bs)
    c_dark.save_png(os.path.join(OUTPUT_DIR, "action_bar_desktop_dark.png"))

    # 3. Mobile Light Theme View
    c_mob_light = Canvas(380, 520, bg_color=(248, 250, 252))
    for idx, (label, ls, lc, vs, sc, cs, cc, bs) in enumerate(states[:7]):
        row_y = 25 + idx * 68
        render_action_bar_block(c_mob_light, 20, row_y, theme="light", like_state=ls, like_count=lc, vote_state=vs, score_val=sc, comm_state=cs, comm_count=cc, bm_state=bs)
    c_mob_light.save_png(os.path.join(OUTPUT_DIR, "action_bar_mobile_light.png"))

    # 4. Mobile Dark Theme View
    c_mob_dark = Canvas(380, 520, bg_color=(15, 23, 42))
    for idx, (label, ls, lc, vs, sc, cs, cc, bs) in enumerate(states[:7]):
        row_y = 25 + idx * 68
        render_action_bar_block(c_mob_dark, 20, row_y, theme="dark", like_state=ls, like_count=lc, vote_state=vs, score_val=sc, comm_state=cs, comm_count=cc, bm_state=bs)
    c_mob_dark.save_png(os.path.join(OUTPUT_DIR, "action_bar_mobile_dark.png"))

    # 5. Dedicated Vote Capsule States Matrix
    c_matrix = Canvas(600, 360, bg_color=(15, 23, 42))
    capsule_states = [
        ("Neutral (Score 0)", "default", 0),
        ("Upvoted (+1 voice, score +1)", "up", 1),
        ("Downvoted (-1 voice, score -1)", "down", -1),
        ("Independent: Score +15 with User Downvote", "down", 15),
        ("Independent: Score -5 with User Upvote", "up", -5),
    ]
    for idx, (lbl, vs, sc) in enumerate(capsule_states):
        row_y = 30 + idx * 64
        render_action_bar_block(c_matrix, 40, row_y, theme="dark", vote_state=vs, score_val=sc)
    c_matrix.save_png(os.path.join(OUTPUT_DIR, "vote_capsule_states_matrix.png"))

    print("Successfully generated all screenshots in:", OUTPUT_DIR)


if __name__ == "__main__":
    generate_all_screenshots()
