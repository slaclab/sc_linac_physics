from random import randint
from unittest import TestCase

from sc_linac_physics.utils.qt import make_rainbow, highlight_text


class Test(TestCase):
    def test_highlight_text(self):
        r = randint(0, 255)
        g = randint(0, 255)
        b = randint(0, 255)
        text = "text"
        self.assertEqual(
            f"\033[48;2;{r};{g};{b}m{text}\033[0m", highlight_text(r, g, b, text)
        )

    def test_make_rainbow(self):
        num_colors = randint(0, 100)
        result = make_rainbow(num_colors)
        self.assertEqual(num_colors, len(result))

        text = ""

        for r, g, b, a in result:
            text += highlight_text(r, g, b, " ")

        print(text)
