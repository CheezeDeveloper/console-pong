import sys
import os
import time
import random
import math

WINDOWS = os.name == 'nt'

if WINDOWS:
    import msvcrt
else:
    import tty
    import termios
    import select


class PongGame:
    def __init__(self):
        self.width = 60
        self.height = 22

        # Paddles
        self.paddle_h = 5
        self.paddle_h_p2 = 5
        self.p1_y = 0.0
        self.p2_y = 0.0

        # Ball
        self.ball_x = 0.0
        self.ball_y = 0.0
        self.ball_dx = 0.0
        self.ball_dy = 0.0
        self.ball_speed = 1.0
        self.max_speed = 2.5

        # Trail effect
        self.ball_trail = []
        self.max_trail = 4

        # Particles
        self.particles = []

        # Scores
        self.p1_score = 0
        self.p2_score = 0
        self.win_score = 7

        # State
        self.running = True
        self.paused = False
        self.game_over = False
        self.winner = ""
        self.state = "MENU"

        # Game mode
        self.mode = "PVP"
        self.cpu_difficulty = 2
        self.cpu_reaction_timer = 0

        # Powerups
        self.powerup_x = -1
        self.powerup_y = -1
        self.powerup_type = ""
        self.powerup_timer = 0
        self.powerup_active = ""
        self.powerup_active_timer = 0
        self.powerup_active_owner = 0

        # Stats
        self.rallies = 0
        self.longest_rally = 0
        self.current_rally = 0
        self.total_time = 0
        self.start_time = 0

        # Timing
        self.tick_rate = 0.045
        self.ball_move_accum = 0.0

        # Countdown
        self.countdown = 0
        self.countdown_timer = 0.0

        # Screen shake
        self.shake_frames = 0
        self.shake_offset_x = 0
        self.shake_offset_y = 0

        # Combo
        self.p1_combo = 0
        self.p2_combo = 0

        # Flash
        self.flash_frames = 0
        self.flash_char = ""

        # Menu
        self.menu_selection = 0
        self.mode_selection = 0
        self.difficulty_selection = 1

        # Terminal
        if not WINDOWS:
            self.old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())

    def cleanup(self):
        if not WINDOWS:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
        sys.stdout.write('\033[?25h')
        sys.stdout.flush()

    def get_key(self):
        if WINDOWS:
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch in (b'\x00', b'\xe0'):
                    msvcrt.getch()
                    return None
                try:
                    return ch.decode('utf-8').lower()
                except:
                    return None
            return None
        else:
            if select.select([sys.stdin], [], [], 0)[0]:
                ch = sys.stdin.read(1)
                return ch.lower()
            return None

    def read_keys(self):
        keys = []
        for _ in range(15):
            key = self.get_key()
            if key is None:
                break
            keys.append(key)
        return keys

    def hide_cursor(self):
        sys.stdout.write('\033[?25l')
        sys.stdout.flush()

    def move_home(self):
        sys.stdout.write('\033[H')

    def clear(self):
        os.system('cls' if WINDOWS else 'clear')

    # ── Particle System ──────────────────────────────────────

    def spawn_particles(self, x, y, count=6, chars=None):
        if chars is None:
            chars = ['*', '+', '.', '·', ':', '~']
        for _ in range(count):
            self.particles.append({
                'x': float(x),
                'y': float(y),
                'dx': random.uniform(-2, 2),
                'dy': random.uniform(-1.5, 1.5),
                'life': random.randint(3, 8),
                'char': random.choice(chars)
            })

    def spawn_score_particles(self, x, y):
        chars = ['★', '!', '*', '●', '◆', '+']
        for _ in range(12):
            self.particles.append({
                'x': float(x),
                'y': float(y),
                'dx': random.uniform(-3, 3),
                'dy': random.uniform(-2, 2),
                'life': random.randint(4, 12),
                'char': random.choice(chars)
            })

    def update_particles(self):
        alive = []
        for p in self.particles:
            p['x'] += p['dx']
            p['y'] += p['dy']
            p['life'] -= 1
            p['dy'] += 0.1
            if p['life'] > 0:
                alive.append(p)
        self.particles = alive

    # ── Power-up System ──────────────────────────────────────

    def spawn_powerup(self):
        self.powerup_x = random.randint(self.width // 4, 3 * self.width // 4)
        self.powerup_y = random.randint(2, self.height - 3)
        self.powerup_type = random.choice(["BIG", "FAST", "SLOW", "TINY"])
        self.powerup_timer = 200

    def collect_powerup(self, player):
        self.powerup_active = self.powerup_type
        self.powerup_active_timer = 150
        self.powerup_active_owner = player

        if self.powerup_type == "BIG":
            if player == 1:
                self.paddle_h = 7
            else:
                self.paddle_h_p2 = 7
        elif self.powerup_type == "TINY":
            if player == 1:
                self.paddle_h_p2 = 3
            else:
                self.paddle_h = 3
        elif self.powerup_type == "FAST":
            self.ball_speed = min(self.ball_speed * 1.5, self.max_speed)
        elif self.powerup_type == "SLOW":
            self.ball_speed = max(self.ball_speed * 0.6, 0.5)

        self.spawn_particles(self.powerup_x, self.powerup_y, 10, ['★', '✦', '◆', '●'])
        self.powerup_x = -1
        self.powerup_y = -1
        self.powerup_type = ""

    def clear_powerup_effect(self):
        self.powerup_active = ""
        self.powerup_active_owner = 0
        self.paddle_h = 5
        self.paddle_h_p2 = 5
        self.ball_speed = max(0.8, min(self.ball_speed, 1.5))

    # ── CPU AI ───────────────────────────────────────────────

    def update_cpu(self):
        if self.mode != "CPU":
            return

        self.cpu_reaction_timer += 1

        react_every = {1: 6, 2: 3, 3: 1}[self.cpu_difficulty]
        if self.cpu_reaction_timer % react_every != 0:
            return

        target_y = self.ball_y
        ph = self.paddle_h_p2
        paddle_center = self.p2_y + ph / 2.0

        if self.cpu_difficulty == 1:
            target_y += random.uniform(-4, 4)
        elif self.cpu_difficulty == 2:
            target_y += random.uniform(-1.5, 1.5)

        if self.ball_dx > 0 or self.cpu_difficulty == 3:
            diff = target_y - paddle_center
            move_speed = {1: 1, 2: 2, 3: 2}[self.cpu_difficulty]
            if abs(diff) > 1:
                if diff > 0:
                    self.p2_y = min(self.height - ph, self.p2_y + move_speed)
                else:
                    self.p2_y = max(0, self.p2_y - move_speed)

    # ── Game Logic ───────────────────────────────────────────

    def init_game(self):
        self.paddle_h = 5
        self.paddle_h_p2 = 5
        self.p1_y = float(self.height // 2 - self.paddle_h // 2)
        self.p2_y = float(self.height // 2 - self.paddle_h // 2)
        self.p1_score = 0
        self.p2_score = 0
        self.game_over = False
        self.winner = ""
        self.paused = False
        self.rallies = 0
        self.longest_rally = 0
        self.current_rally = 0
        self.particles = []
        self.ball_trail = []
        self.p1_combo = 0
        self.p2_combo = 0
        self.powerup_x = -1
        self.powerup_active = ""
        self.powerup_active_timer = 0
        self.start_time = time.time()
        self.reset_ball()

    def reset_ball(self, direction=None):
        self.ball_x = float(self.width // 2)
        self.ball_y = float(self.height // 2)
        self.ball_speed = 1.0
        if direction is None:
            direction = random.choice([-1, 1])
        angle = random.uniform(-0.5, 0.5)
        self.ball_dx = float(direction)
        self.ball_dy = angle
        self.ball_trail = []
        self.countdown = 3
        self.countdown_timer = time.time()
        self.current_rally = 0
        self.ball_move_accum = 0.0

    def update_ball(self):
        if self.paused or self.game_over or self.countdown > 0:
            return

        self.ball_move_accum += self.ball_speed
        while self.ball_move_accum >= 1.0:
            self.ball_move_accum -= 1.0
            self._step_ball()

    def _step_ball(self):
        # Trail
        self.ball_trail.append((self.ball_x, self.ball_y))
        if len(self.ball_trail) > self.max_trail:
            self.ball_trail.pop(0)

        new_x = self.ball_x + self.ball_dx
        new_y = self.ball_y + self.ball_dy

        # ── WALL BOUNCE ──────────────────────────────────
        # The playable vertical range is 1.0 to height-2.0
        # We never allow the ball to sit on row 0 or row height-1
        top_limit = 1.0
        bottom_limit = float(self.height - 2)

        bounce_count = 0
        while (new_y < top_limit or new_y > bottom_limit) and bounce_count < 10:
            bounce_count += 1
            if new_y < top_limit:
                new_y = 2 * top_limit - new_y  # reflect off top
                self.ball_dy = abs(self.ball_dy)
                if abs(self.ball_dy) < 0.3:
                    self.ball_dy = 0.3
                self.spawn_particles(new_x, 0, 3, ['─', '~', '.'])
            if new_y > bottom_limit:
                new_y = 2 * bottom_limit - new_y  # reflect off bottom
                self.ball_dy = -abs(self.ball_dy)
                if abs(self.ball_dy) < 0.3:
                    self.ball_dy = -0.3
                self.spawn_particles(new_x, self.height - 1, 3, ['─', '~', '.'])

        # Hard clamp as absolute last resort — force away from edges
        if new_y <= top_limit:
            new_y = top_limit + 0.5
            self.ball_dy = abs(self.ball_dy)
            if abs(self.ball_dy) < 0.3:
                self.ball_dy = 0.3
        if new_y >= bottom_limit:
            new_y = bottom_limit - 0.5
            self.ball_dy = -abs(self.ball_dy)
            if abs(self.ball_dy) < 0.3:
                self.ball_dy = -0.3

        by = int(round(new_y))
        # Clamp the integer position too
        by = max(1, min(self.height - 2, by))
        p1h = self.paddle_h
        p2h = self.paddle_h_p2

        # Left paddle
        if new_x <= 2 and self.ball_dx < 0:
            p1_top = int(self.p1_y)
            if p1_top <= by < p1_top + p1h:
                new_x = 3.0
                self.ball_dx = abs(self.ball_dx)
                center = self.p1_y + p1h / 2.0
                offset = (by - center) / (p1h / 2.0)
                self.ball_dy = offset * 1.0
                # Enforce minimum vertical movement so ball never goes flat
                if abs(self.ball_dy) < 0.3:
                    self.ball_dy = 0.3 if self.ball_dy >= 0 else -0.3
                # Cap max so it doesn't go too steep
                if self.ball_dy > 0.9:
                    self.ball_dy = 0.9
                elif self.ball_dy < -0.9:
                    self.ball_dy = -0.9
                self.ball_speed = min(self.ball_speed + 0.08, self.max_speed)
                self.current_rally += 1
                self.p1_combo += 1
                self.p2_combo = 0
                self.spawn_particles(3, by, 4)
                self.shake_frames = 2

                if self.powerup_x >= 0:
                    bx_int = int(round(new_x))
                    if abs(bx_int - self.powerup_x) < 2 and abs(by - self.powerup_y) < 2:
                        self.collect_powerup(1)
            elif new_x < 0:
                self._score(2)
                return

        # Right paddle
        if new_x >= self.width - 3 and self.ball_dx > 0:
            p2_top = int(self.p2_y)
            if p2_top <= by < p2_top + p2h:
                new_x = float(self.width - 4)
                self.ball_dx = -abs(self.ball_dx)
                center = self.p2_y + p2h / 2.0
                offset = (by - center) / (p2h / 2.0)
                self.ball_dy = offset * 1.0
                if abs(self.ball_dy) < 0.3:
                    self.ball_dy = 0.3 if self.ball_dy >= 0 else -0.3
                if self.ball_dy > 0.9:
                    self.ball_dy = 0.9
                elif self.ball_dy < -0.9:
                    self.ball_dy = -0.9
                self.ball_speed = min(self.ball_speed + 0.08, self.max_speed)
                self.current_rally += 1
                self.p2_combo += 1
                self.p1_combo = 0
                self.spawn_particles(self.width - 4, by, 4)
                self.shake_frames = 2

                if self.powerup_x >= 0:
                    bx_int = int(round(new_x))
                    if abs(bx_int - self.powerup_x) < 2 and abs(by - self.powerup_y) < 2:
                        self.collect_powerup(2)
            elif new_x >= self.width:
                self._score(1)
                return

        # Powerup collection by ball passing through
        if self.powerup_x >= 0:
            bx_int = int(round(new_x))
            by_int = int(round(new_y))
            if abs(bx_int - self.powerup_x) <= 1 and abs(by_int - self.powerup_y) <= 1:
                owner = 1 if self.ball_dx > 0 else 2
                self.collect_powerup(owner)

        self.ball_x = new_x
        self.ball_y = new_y

    def _score(self, player):
        if player == 1:
            self.p1_score += 1
            self.spawn_score_particles(self.width - 2, self.height // 2)
            self.shake_frames = 5
        else:
            self.p2_score += 1
            self.spawn_score_particles(2, self.height // 2)
            self.shake_frames = 5

        self.longest_rally = max(self.longest_rally, self.current_rally)
        self.rallies += 1
        self.clear_powerup_effect()

        if self.p1_score >= self.win_score:
            self.game_over = True
            self.winner = "PLAYER 1"
            self.total_time = time.time() - self.start_time
            self.state = "GAME_OVER"
            self.spawn_score_particles(self.width // 2, self.height // 2)
        elif self.p2_score >= self.win_score:
            self.game_over = True
            p2name = "CPU" if self.mode == "CPU" else "PLAYER 2"
            self.winner = p2name
            self.total_time = time.time() - self.start_time
            self.state = "GAME_OVER"
            self.spawn_score_particles(self.width // 2, self.height // 2)
        else:
            direction = -1 if player == 1 else 1
            self.reset_ball(direction)

    # ── Rendering ────────────────────────────────────────────

    def build_game_frame(self):
        lines = []

        # Shake offset
        sx = 0
        if self.shake_frames > 0:
            sx = random.choice([-1, 0, 1])
            self.shake_frames -= 1

        # Score bar with visual flair
        p2name = "CPU" if self.mode == "CPU" else "P2"
        speed_bar = "●" * min(int(self.ball_speed * 3), 8)
        header = f"  P1 [{self.p1_score}]  {'◈' * self.p1_combo if self.p1_combo > 1 else ''}"
        header2 = f"{'◈' * self.p2_combo if self.p2_combo > 1 else ''}  [{self.p2_score}] {p2name}"
        mid_info = f"Speed:{speed_bar}"
        gap = self.width + 2 - len(header) - len(header2) - len(mid_info)
        half = max(gap // 2, 1)
        score_line = header + " " * half + mid_info + " " * half + header2
        lines.append(score_line[:self.width + 2])

        # Powerup status
        if self.powerup_active:
            pwr_line = f"  ★ {self.powerup_active} active ({self.powerup_active_timer // 20 + 1}s) - P{self.powerup_active_owner}"
        elif self.powerup_x >= 0:
            pwr_line = f"  ◆ Powerup: {self.powerup_type} available!"
        else:
            pwr_line = ""
        lines.append(pwr_line.ljust(self.width + 2))

        # Top border
        lines.append("╔" + "═" * self.width + "╗")

        # Build field
        bx = int(round(self.ball_x))
        by = int(round(self.ball_y))
        # Clamp display position too
        by = max(1, min(self.height - 2, by))
        mid_x = self.width // 2
        p1h = self.paddle_h
        p2h = self.paddle_h_p2

        # Pre-compute trail positions
        trail_positions = set()
        trail_chars = {}
        trail_syms = ['·', '∙', '◦', '○']
        for i, (tx, ty) in enumerate(self.ball_trail):
            txi = int(round(tx))
            tyi = int(round(ty))
            tyi = max(1, min(self.height - 2, tyi))
            trail_positions.add((txi, tyi))
            idx = min(i, len(trail_syms) - 1)
            trail_chars[(txi, tyi)] = trail_syms[idx]

        # Pre-compute particle positions
        particle_map = {}
        for p in self.particles:
            px = int(round(p['x']))
            py = int(round(p['y']))
            if 0 <= px < self.width and 0 <= py < self.height:
                particle_map[(px, py)] = p['char']

        for y in range(self.height):
            row = ["║"]
            for x in range(self.width):
                drawn = False

                # Particles (top priority visual)
                if (x, y) in particle_map:
                    row.append(particle_map[(x, y)])
                    drawn = True

                # Ball
                if not drawn and x == bx and y == by and (self.countdown == 0 or (self.countdown > 0 and int(time.time() * 4) % 2 == 0)):
                    row.append("●")
                    drawn = True

                # Trail
                if not drawn and (x, y) in trail_positions and self.countdown == 0:
                    row.append(trail_chars.get((x, y), '·'))
                    drawn = True

                # Powerup
                if not drawn and x == self.powerup_x and y == self.powerup_y:
                    powerup_syms = {"BIG": "⊕", "FAST": "⊗", "SLOW": "⊘", "TINY": "⊖"}
                    sym = powerup_syms.get(self.powerup_type, "◆")
                    if int(time.time() * 3) % 2 == 0:
                        row.append(sym)
                    else:
                        row.append("◆")
                    drawn = True

                # Left paddle
                if not drawn and x == 1 and int(self.p1_y) <= y < int(self.p1_y) + p1h:
                    if y == int(self.p1_y) or y == int(self.p1_y) + p1h - 1:
                        row.append("▐")
                    else:
                        row.append("█")
                    drawn = True

                # Right paddle
                if not drawn and x == self.width - 2 and int(self.p2_y) <= y < int(self.p2_y) + p2h:
                    if y == int(self.p2_y) or y == int(self.p2_y) + p2h - 1:
                        row.append("▌")
                    else:
                        row.append("█")
                    drawn = True

                # Center net
                if not drawn and x == mid_x:
                    if y % 2 == 0:
                        row.append("│")
                    else:
                        row.append(" ")
                    drawn = True

                if not drawn:
                    row.append(" ")

            row.append("║")
            line = "".join(row)

            # Apply shake
            if sx > 0:
                line = " " + line[:-1]
            elif sx < 0:
                line = line[1:] + " "

            lines.append(line)

        # Bottom border
        lines.append("╚" + "═" * self.width + "╝")

        # Status line
        if self.countdown > 0:
            status = f"          >>> Get ready... {self.countdown} <<<"
        elif self.current_rally >= 5:
            status = f"          🔥 RALLY: {self.current_rally} hits!"
        else:
            status = ""

        controls = "  W/S:P1"
        if self.mode == "PVP":
            controls += "  I/K:P2"
        controls += "  P:Pause  Q:Quit  R:Restart"
        lines.append(controls)
        lines.append(status.ljust(self.width + 2))

        # Pad
        for _ in range(2):
            lines.append(" " * (self.width + 2))

        return "\n".join(lines)

    def build_menu_frame(self):
        items = ["Play vs Player (PVP)", "Play vs CPU", "Quit"]
        lines = []
        lines.append("")
        lines.append("  ╔══════════════════════════════════════════════════════╗")
        lines.append("  ║                                                      ║")
        lines.append("  ║     ____    ___   _   _    ____   _                  ║")
        lines.append("  ║    |  _ \\  / _ \\ | \\ | |  / ___| | |                 ║")
        lines.append("  ║    | |_) || | | ||  \\| | | |  _  | |                 ║")
        lines.append("  ║    |  __/ | |_| || |\\  | | |_| | |_|                 ║")
        lines.append("  ║    |_|     \\___/ |_| \\_|  \\____| (_)                 ║")
        lines.append("  ║                                                      ║")
        lines.append("  ║              ═══ CONSOLE EDITION ═══                 ║")
        lines.append("  ║                                                      ║")

        for i, item in enumerate(items):
            if i == self.menu_selection:
                lines.append(f"  ║        ►  {item:<40}  ║")
            else:
                lines.append(f"  ║           {item:<40}  ║")

        lines.append("  ║                                                      ║")
        lines.append("  ║     Controls:                                        ║")
        lines.append("  ║       W/S or I/K  - Move paddle                      ║")
        lines.append("  ║       P - Pause   Q - Quit   R - Restart             ║")
        lines.append("  ║       ↑/↓ or W/S  - Navigate menu                    ║")
        lines.append("  ║       SPACE/ENTER - Select                           ║")
        lines.append("  ║                                                      ║")
        lines.append("  ║     Features:                                        ║")
        lines.append("  ║       ★ Powerups   ● Ball trails   ◈ Combos          ║")
        lines.append("  ║       ✦ Particles  ⊕ Screen shake                    ║")
        lines.append("  ║                                                      ║")
        lines.append("  ╚══════════════════════════════════════════════════════╝")
        lines.append("")

        for _ in range(5):
            lines.append(" " * 60)

        return "\n".join(lines)

    def build_difficulty_frame(self):
        diffs = ["Easy   - CPU is sleepy", "Medium - A fair match", "Hard   - CPU is relentless"]
        lines = []
        lines.append("")
        lines.append("  ╔══════════════════════════════════════════════════════╗")
        lines.append("  ║                                                      ║")
        lines.append("  ║              SELECT CPU DIFFICULTY                   ║")
        lines.append("  ║                                                      ║")

        for i, d in enumerate(diffs):
            if i == self.difficulty_selection:
                lines.append(f"  ║        ►  {d:<42}║")
            else:
                lines.append(f"  ║           {d:<42}║")

        lines.append("  ║                                                      ║")
        lines.append("  ║     W/S to select, SPACE/ENTER to confirm            ║")
        lines.append("  ║                                                      ║")
        lines.append("  ╚══════════════════════════════════════════════════════╝")

        for _ in range(20):
            lines.append(" " * 60)

        return "\n".join(lines)

    def build_game_over_frame(self):
        elapsed = int(self.total_time)
        mins = elapsed // 60
        secs = elapsed % 60

        lines = []
        lines.append("")
        lines.append("  ╔══════════════════════════════════════════════════════╗")
        lines.append("  ║                                                      ║")
        lines.append("  ║                  ★ GAME OVER ★                       ║")
        lines.append("  ║                                                      ║")
        lines.append(f"  ║          {self.winner:^42}  ║")
        lines.append("  ║                    WINS!                             ║")
        lines.append("  ║                                                      ║")
        p2label = 'CPU' if self.mode == 'CPU' else 'P2'
        lines.append(f"  ║     Final Score:  P1 [{self.p1_score}]  -  [{self.p2_score}] {p2label}               ║")
        lines.append("  ║                                                      ║")
        lines.append("  ║     ── Stats ──────────────────────────              ║")
        lines.append(f"  ║     Time:          {mins}m {secs:02d}s                            ║")
        lines.append(f"  ║     Total Rallies: {self.rallies:<36}║")
        lines.append(f"  ║     Longest Rally: {self.longest_rally} hits{' ' * 30}║")
        lines.append("  ║                                                      ║")
        lines.append("  ║     [R] Play Again    [M] Menu    [Q] Quit           ║")
        lines.append("  ║                                                      ║")
        lines.append("  ╚══════════════════════════════════════════════════════╝")

        for _ in range(12):
            lines.append(" " * 60)

        return "\n".join(lines)

    # ── Input Handlers ───────────────────────────────────────

    def handle_menu_input(self, keys):
        for key in keys:
            if key == 'q':
                self.running = False
            elif key in ('w', 'i'):
                self.menu_selection = (self.menu_selection - 1) % 3
            elif key in ('s', 'k'):
                self.menu_selection = (self.menu_selection + 1) % 3
            elif key in (' ', '\r', '\n'):
                if self.menu_selection == 0:
                    self.mode = "PVP"
                    self.state = "PLAYING"
                    self.init_game()
                elif self.menu_selection == 1:
                    self.mode = "CPU"
                    self.state = "DIFFICULTY"
                elif self.menu_selection == 2:
                    self.running = False

    def handle_difficulty_input(self, keys):
        for key in keys:
            if key == 'q':
                self.state = "MENU"
            elif key in ('w', 'i'):
                self.difficulty_selection = (self.difficulty_selection - 1) % 3
            elif key in ('s', 'k'):
                self.difficulty_selection = (self.difficulty_selection + 1) % 3
            elif key in (' ', '\r', '\n'):
                self.cpu_difficulty = self.difficulty_selection + 1
                self.state = "PLAYING"
                self.init_game()

    def handle_game_input(self, keys):
        for key in keys:
            if key == 'q':
                self.running = False
            elif key == 'p':
                self.paused = not self.paused
            elif key == 'r':
                self.init_game()
            elif not self.paused and not self.game_over:
                p1h = self.paddle_h
                p2h = self.paddle_h_p2
                if key == 'w':
                    self.p1_y = max(0, self.p1_y - 2)
                elif key == 's':
                    self.p1_y = min(self.height - p1h, self.p1_y + 2)
                if self.mode == "PVP":
                    if key == 'i':
                        self.p2_y = max(0, self.p2_y - 2)
                    elif key == 'k':
                        self.p2_y = min(self.height - p2h, self.p2_y + 2)

    def handle_gameover_input(self, keys):
        for key in keys:
            if key == 'q':
                self.running = False
            elif key == 'r':
                self.init_game()
                self.state = "PLAYING"
            elif key == 'm':
                self.state = "MENU"

    # ── Main Loop ────────────────────────────────────────────

    def run(self):
        try:
            self.hide_cursor()
            self.clear()

            while self.running:
                start = time.time()
                keys = self.read_keys()

                if self.state == "MENU":
                    self.handle_menu_input(keys)
                    frame = self.build_menu_frame()

                elif self.state == "DIFFICULTY":
                    self.handle_difficulty_input(keys)
                    frame = self.build_difficulty_frame()

                elif self.state == "PLAYING":
                    self.handle_game_input(keys)

                    if not self.paused and not self.game_over:
                        # Countdown
                        if self.countdown > 0:
                            if time.time() - self.countdown_timer >= 1.0:
                                self.countdown -= 1
                                self.countdown_timer = time.time()

                        self.update_ball()
                        self.update_cpu()
                        self.update_particles()

                        # Powerup spawning
                        if self.powerup_x >= 0:
                            self.powerup_timer -= 1
                            if self.powerup_timer <= 0:
                                self.powerup_x = -1
                        elif random.random() < 0.003 and self.countdown == 0:
                            self.spawn_powerup()

                        # Active powerup timer
                        if self.powerup_active_timer > 0:
                            self.powerup_active_timer -= 1
                            if self.powerup_active_timer <= 0:
                                self.clear_powerup_effect()

                    frame = self.build_game_frame()

                    if self.paused:
                        frame += "\n\n       >>> PAUSED - Press P to resume <<<"

                elif self.state == "GAME_OVER":
                    self.handle_gameover_input(keys)
                    self.update_particles()
                    frame = self.build_game_over_frame()

                else:
                    frame = ""

                self.move_home()
                sys.stdout.write(frame)
                sys.stdout.flush()

                elapsed = time.time() - start
                sleep = self.tick_rate - elapsed
                if sleep > 0:
                    time.sleep(sleep)

        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()
            self.clear()
            print("\n  Thanks for playing PONG! 🏓\n")


if __name__ == "__main__":
    game = PongGame()
    game.run()
