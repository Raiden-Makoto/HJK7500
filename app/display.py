"""Draws the rows full-screen in the Luminator Horizon LED font."""

import pygame

# Widest right-hand texts the layout should fit without shrinking.
TIME_TEMPLATES = ["now, 88 min", "88, 88 min"]
MARGIN_X = 16
GAP = 24


class Board:
    def __init__(self, font_path, labels, size=None, fullscreen=False, fg=(255, 170, 0), bg=(0, 0, 0)):
        pygame.display.init()
        pygame.font.init()
        if fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            pygame.mouse.set_visible(False)
        else:
            self.screen = pygame.display.set_mode(size or (800, 480))
        pygame.display.set_caption("HJK7500")
        self.font_path, self.fg, self.bg = font_path, fg, bg
        self.width, self.height = self.screen.get_size()
        self.row_h = self.height // len(labels)
        self.font = self._fit_font(labels)
        # Shared vertical placement so every row lines up on the same baseline.
        ink = self.font.render("Rg0123456789", False, fg).get_bounding_rect()
        self.ink_top, self.ink_h = ink.top, ink.height

    def _fits(self, font, labels):
        ink = font.render("Rg0123456789", False, self.fg).get_bounding_rect()
        if ink.height > self.row_h * 0.86:
            return False
        times_w = max(font.size(t)[0] for t in TIME_TEMPLATES)
        widest = max(font.size(label)[0] for label in labels)
        return widest + GAP + times_w <= self.width - 2 * MARGIN_X

    def _fit_font(self, labels):
        lo, hi = 8, self.row_h * 2
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self._fits(pygame.font.Font(self.font_path, mid), labels):
                lo = mid
            else:
                hi = mid - 1
        return pygame.font.Font(self.font_path, lo)

    def _text(self, text, max_w):
        surf = self.font.render(text, False, self.fg)
        if surf.get_width() > max_w:
            scale = max_w / surf.get_width()
            surf = pygame.transform.scale(surf, (max_w, int(surf.get_height() * scale)))
        return surf

    def draw(self, lines):
        """lines: [(left_text, right_text)], one per row."""
        self.screen.fill(self.bg)
        usable = self.width - 2 * MARGIN_X
        for i, (left, right) in enumerate(lines):
            y = i * self.row_h + (self.row_h - self.ink_h) // 2 - self.ink_top
            r = self._text(right, usable // 2)
            l = self._text(left, usable - r.get_width() - GAP)
            self.screen.blit(l, (MARGIN_X, y))
            self.screen.blit(r, (self.width - MARGIN_X - r.get_width(), y))
        pygame.display.flip()

    def message(self, text):
        self.screen.fill(self.bg)
        surf = self._text(text, self.width - 2 * MARGIN_X)
        self.screen.blit(surf, surf.get_rect(center=(self.width // 2, self.height // 2)))
        pygame.display.flip()

    def save(self, path):
        pygame.image.save(self.screen, str(path))
