"""
DOOMPy Lobby Menu
Called after the main menu START button.
Returns a LobbyResult namedtuple so main.py knows what to do next.
"""

import pygame
import sys
from collections import namedtuple
from network import MatchmakingClient, get_local_ip

# ── colours (self-contained, don't rely on settings.py colours) ─────────────
BG        = (18, 18, 24)
PANEL     = (30, 30, 40)
ACCENT    = (180, 30, 30)
ACCENT2   = (220, 80, 0)
TEXT      = (220, 220, 220)
DIMTEXT   = (120, 120, 130)
WHITE     = (255, 255, 255)
BLACK     = (0, 0, 0)
GREEN     = (60, 180, 60)
RED       = (200, 40, 40)
HIGHLIGHT = (50, 50, 70)
BORDER    = (60, 60, 80)

LobbyResult = namedtuple('LobbyResult', ['action', 'code', 'host', 'port', 'server_name', 'private'])
# action: 'host' | 'join' | 'quit'


class LobbyMenu:
    def __init__(self, sc, clock, bg_picture):
        self.sc = sc
        self.clock = clock
        self.bg = bg_picture
        W, H = sc.get_size()
        self.W, self.H = W, H

        pygame.font.init()
        self.font_title  = pygame.font.SysFont('Arial', 52, bold=True)
        self.font_head   = pygame.font.SysFont('Arial', 28, bold=True)
        self.font_body   = pygame.font.SysFont('Arial', 22)
        self.font_small  = pygame.font.SysFont('Arial', 17)
        self.font_code   = pygame.font.SysFont('Courier New', 38, bold=True)

        self.client = MatchmakingClient()
        self._connected = False
        self._conn_error = ''
        self._try_connect()

        # state machine
        self.screen = 'main'   # 'main' | 'browse' | 'create' | 'code'

        # browse state
        self.lobbies = []
        self.selected_lobby = 0
        self.browse_scroll = 0

        # create state
        self.create_name   = ''
        self.create_private = False
        self.create_active  = False   # is text field focused?

        # code state
        self.code_input = ''
        self.code_active = True
        self.code_error  = ''

        # feedback
        self.status_msg  = ''
        self.status_color = TEXT

    # ── connection ──────────────────────────────────────────────────────────

    def _try_connect(self):
        try:
            self.client.connect()
            self._connected = True
        except Exception as e:
            self._connected = False
            self._conn_error = str(e)

    # ── main entry point ────────────────────────────────────────────────────

    def run(self) -> LobbyResult:
        """Block until the player picks an action. Returns LobbyResult."""
        while True:
            result = self._tick()
            if result:
                self.client.close()
                return result
            pygame.display.flip()
            self.clock.tick(30)

    # ── per-frame dispatch ──────────────────────────────────────────────────

    def _tick(self):
        events = pygame.event.get()
        for e in events:
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        self._draw_bg()

        if self.screen == 'main':
            return self._screen_main(events)
        elif self.screen == 'browse':
            return self._screen_browse(events)
        elif self.screen == 'create':
            return self._screen_create(events)
        elif self.screen == 'code':
            return self._screen_code(events)

    # ── helpers ─────────────────────────────────────────────────────────────

    def _draw_bg(self):
        # tinted bg
        bg = pygame.transform.scale(self.bg, (self.W, self.H))
        dark = pygame.Surface((self.W, self.H))
        dark.fill(BLACK)
        dark.set_alpha(160)
        self.sc.blit(bg, (0, 0))
        self.sc.blit(dark, (0, 0))

    def _draw_title(self, text):
        surf = self.font_title.render(text, True, ACCENT)
        self.sc.blit(surf, (self.W // 2 - surf.get_width() // 2, 40))

    def _button(self, rect, label, color=PANEL, text_color=TEXT, hover_color=HIGHLIGHT):
        mx, my = pygame.mouse.get_pos()
        hovered = rect.collidepoint(mx, my)
        pygame.draw.rect(self.sc, hover_color if hovered else color, rect, border_radius=8)
        pygame.draw.rect(self.sc, BORDER, rect, 2, border_radius=8)
        surf = self.font_body.render(label, True, text_color)
        self.sc.blit(surf, (rect.centerx - surf.get_width() // 2,
                             rect.centery - surf.get_height() // 2))
        return hovered

    def _clicked(self, rect, events):
        mx, my = pygame.mouse.get_pos()
        if rect.collidepoint(mx, my):
            for e in events:
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    return True
        return False

    def _back_button(self, events):
        r = pygame.Rect(30, 30, 110, 40)
        self._button(r, '← Back')
        return self._clicked(r, events)

    def _status(self, y=None):
        if self.status_msg:
            s = self.font_small.render(self.status_msg, True, self.status_color)
            y = y or self.H - 40
            self.sc.blit(s, (self.W // 2 - s.get_width() // 2, y))

    def _set_status(self, msg, ok=True):
        self.status_msg = msg
        self.status_color = GREEN if ok else RED

    # ── SCREEN: main lobby choice ────────────────────────────────────────────

    def _screen_main(self, events):
        self._draw_title('MULTIPLAYER')

        if not self._connected:
            err = self.font_body.render(f'⚠  Cannot reach server: {self._conn_error}', True, RED)
            self.sc.blit(err, (self.W // 2 - err.get_width() // 2, 120))
            retry_r = pygame.Rect(self.W // 2 - 90, 170, 180, 44)
            self._button(retry_r, 'Retry')
            if self._clicked(retry_r, events):
                self._try_connect()
            return None

        cx = self.W // 2
        bw, bh, gap = 380, 64, 24
        y0 = 160

        options = [
            ('Browse Servers',  'browse'),
            ('Join Public Game','join_any'),
            ('Create Server',   'create'),
            ('Join by Code',    'code'),
        ]

        for i, (label, action) in enumerate(options):
            r = pygame.Rect(cx - bw // 2, y0 + i * (bh + gap), bw, bh)
            self._button(r, label)
            if self._clicked(r, events):
                if action == 'browse':
                    self._refresh_lobbies()
                    self.screen = 'browse'
                elif action == 'join_any':
                    return self._do_join_any()
                elif action == 'create':
                    self.screen = 'create'
                    self.create_name = ''
                    self.create_active = True
                elif action == 'code':
                    self.screen = 'code'
                    self.code_input = ''
                    self.code_error = ''

        self._status(y0 + len(options) * (bh + gap) + 20)
        return None

    # ── SCREEN: browse servers ───────────────────────────────────────────────

    def _refresh_lobbies(self):
        try:
            self.lobbies = self.client.list_lobbies()
            self.selected_lobby = 0
            self._set_status(f'{len(self.lobbies)} server(s) found')
        except Exception as e:
            self._set_status(str(e), ok=False)

    def _screen_browse(self, events):
        self._draw_title('BROWSE SERVERS')
        if self._back_button(events):
            self.screen = 'main'
            return None

        # refresh button
        ref_r = pygame.Rect(self.W - 160, 30, 130, 40)
        self._button(ref_r, '⟳ Refresh')
        if self._clicked(ref_r, events):
            self._refresh_lobbies()

        # column headers
        hx, hy = 60, 110
        col_w = [320, 120, 80]
        headers = ['Server Name', 'Players', 'Code']
        for i, h in enumerate(headers):
            s = self.font_small.render(h, True, DIMTEXT)
            self.sc.blit(s, (hx + sum(col_w[:i]), hy))
        pygame.draw.line(self.sc, BORDER, (hx, hy + 22), (self.W - 60, hy + 22), 1)

        row_h = 46
        visible = (self.H - 200) // row_h
        self.browse_scroll = max(0, min(self.browse_scroll,
                                        max(0, len(self.lobbies) - visible)))

        # scroll via mouse wheel
        for e in events:
            if e.type == pygame.MOUSEWHEEL:
                self.browse_scroll -= e.y

        if not self.lobbies:
            s = self.font_body.render('No public servers found.', True, DIMTEXT)
            self.sc.blit(s, (self.W // 2 - s.get_width() // 2, self.H // 2))
        else:
            for idx, lobby in enumerate(self.lobbies[self.browse_scroll:
                                                       self.browse_scroll + visible]):
                real_idx = idx + self.browse_scroll
                ry = hy + 30 + idx * row_h
                row_r = pygame.Rect(hx - 8, ry - 4, self.W - 100, row_h - 4)
                color = ACCENT if real_idx == self.selected_lobby else PANEL
                pygame.draw.rect(self.sc, color, row_r, border_radius=6)

                cells = [lobby['name'], str(lobby['players']), lobby['code']]
                for ci, cell in enumerate(cells):
                    s = self.font_body.render(cell, True, TEXT)
                    self.sc.blit(s, (hx + sum(col_w[:ci]), ry + 8))

                if self._clicked(row_r, events):
                    self.selected_lobby = real_idx

        # join selected
        join_r = pygame.Rect(self.W // 2 - 120, self.H - 70, 240, 50)
        self._button(join_r, 'Join Selected', color=ACCENT, text_color=WHITE)
        if self._clicked(join_r, events) and self.lobbies:
            lobby = self.lobbies[self.selected_lobby]
            return self._do_join_code(lobby['code'])

        self._status()
        return None

    # ── SCREEN: create server ────────────────────────────────────────────────

    def _screen_create(self, events):
        self._draw_title('CREATE SERVER')
        if self._back_button(events):
            self.screen = 'main'
            return None

        cx, cy = self.W // 2, 160

        # server name field
        s = self.font_body.render('Server Name:', True, TEXT)
        self.sc.blit(s, (cx - 200, cy))
        field_r = pygame.Rect(cx - 200, cy + 34, 400, 46)
        pygame.draw.rect(self.sc, PANEL, field_r, border_radius=6)
        border_col = WHITE if self.create_active else BORDER
        pygame.draw.rect(self.sc, border_col, field_r, 2, border_radius=6)
        name_surf = self.font_body.render(self.create_name + ('|' if self.create_active else ''), True, TEXT)
        self.sc.blit(name_surf, (field_r.x + 10, field_r.y + 10))

        if self._clicked(field_r, events):
            self.create_active = True

        # handle typing
        if self.create_active:
            for e in events:
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_BACKSPACE:
                        self.create_name = self.create_name[:-1]
                    elif e.key == pygame.K_RETURN:
                        pass
                    elif len(self.create_name) < 28 and e.unicode.isprintable():
                        self.create_name += e.unicode

        # private toggle
        toggle_r = pygame.Rect(cx - 200, cy + 110, 260, 44)
        label = f"{'🔒 Private' if self.create_private else '🌐 Public'}  (click to toggle)"
        self._button(toggle_r, label)
        if self._clicked(toggle_r, events):
            self.create_private = not self.create_private

        priv_hint = 'Private: only joinable by code.' if self.create_private else 'Public: visible in Browse Servers.'
        h = self.font_small.render(priv_hint, True, DIMTEXT)
        self.sc.blit(h, (cx - 200, cy + 162))

        # create button
        create_r = pygame.Rect(cx - 150, cy + 210, 300, 54)
        self._button(create_r, 'Create & Host', color=ACCENT, text_color=WHITE)
        if self._clicked(create_r, events):
            name = self.create_name.strip() or 'My Server'
            return self._do_create(name, self.create_private)

        self._status(cy + 290)
        return None

    # ── SCREEN: join by code ─────────────────────────────────────────────────

    def _screen_code(self, events):
        self._draw_title('JOIN BY CODE')
        if self._back_button(events):
            self.screen = 'main'
            return None

        cx, cy = self.W // 2, self.H // 2 - 80

        prompt = self.font_body.render('Enter 4-letter server code:', True, TEXT)
        self.sc.blit(prompt, (cx - prompt.get_width() // 2, cy - 50))

        # big code input box
        box_r = pygame.Rect(cx - 140, cy, 280, 70)
        pygame.draw.rect(self.sc, PANEL, box_r, border_radius=10)
        pygame.draw.rect(self.sc, WHITE if self.code_active else BORDER, box_r, 2, border_radius=10)
        display = self.code_input + ('_' if len(self.code_input) < 4 and self.code_active else '')
        code_surf = self.font_code.render(display.upper(), True, ACCENT2)
        self.sc.blit(code_surf, (box_r.centerx - code_surf.get_width() // 2,
                                  box_r.centery - code_surf.get_height() // 2))

        if self._clicked(box_r, events):
            self.code_active = True

        # typing
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_BACKSPACE:
                    self.code_input = self.code_input[:-1]
                    self.code_error = ''
                elif e.key == pygame.K_RETURN and len(self.code_input) == 4:
                    return self._do_join_code(self.code_input)
                elif len(self.code_input) < 4 and e.unicode.isalpha():
                    self.code_input += e.unicode.upper()
                    self.code_error = ''

        if self.code_error:
            err = self.font_body.render(self.code_error, True, RED)
            self.sc.blit(err, (cx - err.get_width() // 2, cy + 90))

        join_r = pygame.Rect(cx - 120, cy + 120, 240, 50)
        enabled = len(self.code_input) == 4
        col = ACCENT if enabled else (50, 50, 60)
        self._button(join_r, 'Join', color=col, text_color=WHITE)
        if enabled and self._clicked(join_r, events):
            return self._do_join_code(self.code_input)

        return None

    # ── network actions ──────────────────────────────────────────────────────

    def _do_create(self, name, private):
        try:
            local_ip = get_local_ip()
            code = self.client.create_lobby(name, private, local_ip)
            self._set_status(f'Server created! Code: {code}')
            return LobbyResult('host', code, local_ip, 9998, name, private)
        except Exception as e:
            self._set_status(str(e), ok=False)
            return None

    def _do_join_code(self, code):
        try:
            host, port = self.client.join_by_code(code)
            return LobbyResult('join', code, host, port, '', False)
        except Exception as e:
            self.code_error = str(e)
            self._set_status(str(e), ok=False)
            return None

    def _do_join_any(self):
        try:
            code, host, port = self.client.join_any()
            self._set_status(f'Joining {code}…')
            return LobbyResult('join', code, host, port, '', False)
        except Exception as e:
            self._set_status(str(e), ok=False)
            return None
