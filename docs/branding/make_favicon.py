"""
Bold, simplified SmartCart favicon.
Browser favicons render at 16-32px, so this uses much thicker strokes and
fewer details than the full logo icon, which goes muddy at that size.
"""

from PIL import Image, ImageDraw

DARK_GRN = (52, 87, 43, 255)
MID_GRN = (110, 155, 85, 255)
LIGHT_GRN = (170, 205, 140, 255)
TRANSPARENT = (0, 0, 0, 0)

SS = 8  # supersample heavily since target is tiny


def draw_bold_cart(size):
    img = Image.new("RGBA", (size, size), TRANSPARENT)
    d = ImageDraw.Draw(img)

    stroke = int(size * 0.070)  # much thicker than the main icon (was ~0.030)

    # Basket trapezoid only, no handle, no fine detail, wide and bold
    top_l, top_r = int(size * 0.18), int(size * 0.86)
    top_y = int(size * 0.30)
    bot_l, bot_r = int(size * 0.30), int(size * 0.78)
    bot_y = int(size * 0.74)

    basket = [(top_l, top_y), (top_r, top_y), (bot_r, bot_y), (bot_l, bot_y), (top_l, top_y)]
    d.line(basket, fill=DARK_GRN, width=stroke, joint="curve")
    for pt in basket:
        r = stroke // 2
        d.ellipse([pt[0] - r, pt[1] - r, pt[0] + r, pt[1] + r], fill=DARK_GRN)

    # Two bold bars inside, high contrast, simplified to 2 (not 3)
    base_y = int(size * 0.68)
    bar_w = int(size * 0.13)
    gap = int(size * 0.05)
    heights = [int(size * 0.16), int(size * 0.30)]
    colors = [LIGHT_GRN, MID_GRN]
    x = int(size * 0.38)
    for h, color in zip(heights, colors):
        d.rectangle([x, base_y - h, x + bar_w, base_y], fill=color)
        x += bar_w + gap

    # Wheels, bold and simple
    for cx in (int(size * 0.38), int(size * 0.63)):
        cy = int(size * 0.82)
        r = int(size * 0.06)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=DARK_GRN)

    return img


def make_favicon(out_path, size=256):
    ss_size = size * SS
    icon = draw_bold_cart(ss_size)
    icon = icon.resize((size, size), Image.LANCZOS)
    icon.save(out_path)


if __name__ == "__main__":
    make_favicon("smartcart_favicon.png", size=256)
    print("done")
