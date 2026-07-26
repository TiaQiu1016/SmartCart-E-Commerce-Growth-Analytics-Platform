"""
SmartCart logo generator.
Palette matched to the sage/olive-green Canva deck theme.
Builds: icon-only badge (square), horizontal lockup with wordmark, and a
transparent-background icon for use on dark or light surfaces.

Requires the Outfit-Bold.ttf and WorkSans-Regular.ttf font files (Google
Fonts, OFL license) on disk. Point FONT_DIR at wherever you have them, e.g.
a local Google Fonts checkout or the system font directory. Not bundled in
this repo to keep it free of third-party binary assets.
"""

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = "./fonts"  # update to a local path containing Outfit-Bold.ttf and WorkSans-Regular.ttf

# ---- palette (sampled from the deck: sage cream bg, olive/forest greens) ----
CREAM      = (234, 240, 221, 255)   # slide background sage-cream
LIGHT_GRN  = (180, 210, 150, 255)   # lightest bar
MID_GRN    = (130, 175, 100, 255)   # mid bar
DARK_GRN   = (75, 120, 60, 255)     # tallest bar, wordmark accent (distinct from outline)
CHARCOAL   = (30, 32, 24, 255)      # near-black text
TRANSPARENT = (0, 0, 0, 0)

SS = 4  # supersample factor for crisp anti-aliasing


def draw_cart_mark(size=2000):
    """Draws the cart+bars icon on a transparent RGBA canvas of `size`x`size`."""
    img = Image.new("RGBA", (size, size), TRANSPARENT)
    d = ImageDraw.Draw(img)

    stroke = int(size * 0.030)
    OUTLINE = (36, 54, 28, 255)   # near-black forest, distinct from every bar shade

    # Handle: short grip + diagonal down to basket top-left
    handle_grip = [(int(size * 0.235), int(size * 0.255)), (int(size * 0.320), int(size * 0.255))]
    handle_diag = [(int(size * 0.320), int(size * 0.255)), (int(size * 0.400), int(size * 0.380))]
    d.line(handle_grip, fill=OUTLINE, width=stroke, joint="curve")
    d.line(handle_diag, fill=OUTLINE, width=stroke, joint="curve")
    for pt in (handle_grip[0], handle_grip[1]):
        r = stroke // 2
        d.ellipse([pt[0] - r, pt[1] - r, pt[0] + r, pt[1] + r], fill=OUTLINE)

    # Basket trapezoid (wide, shallow, wider top / tapered bottom), outline only
    top_l, top_r = int(size * 0.300), int(size * 0.820)
    top_y = int(size * 0.380)
    bot_l, bot_r = int(size * 0.400), int(size * 0.760)
    bot_y = int(size * 0.760)
    basket = [
        (top_l, top_y),
        (top_r, top_y),
        (bot_r, bot_y),
        (bot_l, bot_y),
        (top_l, top_y),
    ]
    d.line(basket, fill=OUTLINE, width=stroke, joint="curve")
    for pt in basket:
        r = stroke // 2
        d.ellipse([pt[0] - r, pt[1] - r, pt[0] + r, pt[1] + r], fill=OUTLINE)

    # Wheels
    for cx in (int(size * 0.470), int(size * 0.700)):
        cy = int(size * 0.855)
        r = int(size * 0.036)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=OUTLINE)

    # Ascending bars "inside" the basket (growth-analytics cue), safely clear of the slanted walls
    base_y = int(size * 0.735)
    bar_w = int(size * 0.075)
    gap = int(size * 0.030)
    start_x = int(size * 0.4275)
    heights = [int(size * 0.095), int(size * 0.175), int(size * 0.265)]
    colors = [LIGHT_GRN, MID_GRN, DARK_GRN]
    x = start_x
    for h, color in zip(heights, colors):
        d.rectangle([x, base_y - h, x + bar_w, base_y], fill=color)
        x += bar_w + gap

    return img


def rounded_mask(size, radius):
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def make_icon_badge(out_path, size=1024):
    ss_size = size * SS
    icon = draw_cart_mark(ss_size)

    badge = Image.new("RGBA", (ss_size, ss_size), TRANSPARENT)
    bd = ImageDraw.Draw(badge)
    radius = int(ss_size * 0.22)
    bd.rounded_rectangle([0, 0, ss_size - 1, ss_size - 1], radius=radius, fill=CREAM)
    badge.alpha_composite(icon)

    badge = badge.resize((size, size), Image.LANCZOS)
    badge.save(out_path)


def make_icon_transparent(out_path, size=1024):
    ss_size = size * SS
    icon = draw_cart_mark(ss_size)
    icon = icon.resize((size, size), Image.LANCZOS)
    icon.save(out_path)


def make_horizontal_lockup(out_path, height=800):
    ss_h = height * SS
    icon_size = int(ss_h * 0.90)
    icon = draw_cart_mark(icon_size)

    font_bold = ImageFont.truetype(f"{FONT_DIR}/Outfit-Bold.ttf", int(ss_h * 0.42))
    tagline_font = ImageFont.truetype(f"{FONT_DIR}/WorkSans-Regular.ttf", int(ss_h * 0.115))

    word_smart = "Smart"
    word_cart = "Cart"
    tagline = "E-COMMERCE GROWTH ANALYTICS"

    tmp = Image.new("RGBA", (10, 10), TRANSPARENT)
    td = ImageDraw.Draw(tmp)
    w_smart = td.textlength(word_smart, font=font_bold)
    w_cart = td.textlength(word_cart, font=font_bold)
    w_tagline = td.textlength(tagline, font=tagline_font)

    pad = int(ss_h * 0.12)
    gap_icon_text = int(ss_h * 0.16)
    total_w = pad + icon_size + gap_icon_text + int(w_smart + w_cart) + pad
    total_w = max(total_w, pad + icon_size + gap_icon_text + int(w_tagline) + pad)

    canvas = Image.new("RGBA", (total_w, ss_h), TRANSPARENT)
    canvas.alpha_composite(icon, (pad, (ss_h - icon_size) // 2))

    cd = ImageDraw.Draw(canvas)
    text_x = pad + icon_size + gap_icon_text
    word_y = int(ss_h * 0.20)
    cd.text((text_x, word_y), word_smart, font=font_bold, fill=DARK_GRN)
    cd.text((text_x + w_smart, word_y), word_cart, font=font_bold, fill=CHARCOAL)

    tagline_y = int(ss_h * 0.66)
    cd.text((text_x + int(ss_h * 0.01), tagline_y), tagline, font=tagline_font, fill=(90, 100, 78, 255))

    canvas = canvas.resize((total_w // SS, height), Image.LANCZOS)
    canvas.save(out_path)


def make_on_cream_lockup(out_path, height=900):
    """Horizontal lockup on the deck's cream background, for direct use in slides."""
    ss_h = height * SS
    icon_size = int(ss_h * 0.72)

    badge_ss = int(icon_size * 1.35)
    badge = Image.new("RGBA", (badge_ss, badge_ss), TRANSPARENT)
    bd = ImageDraw.Draw(badge)
    radius = int(badge_ss * 0.24)
    bd.rounded_rectangle([0, 0, badge_ss - 1, badge_ss - 1], radius=radius,
                          fill=(210, 226, 187, 255))
    icon = draw_cart_mark(icon_size)
    badge.alpha_composite(icon, ((badge_ss - icon_size) // 2, (badge_ss - icon_size) // 2))

    font_bold = ImageFont.truetype(f"{FONT_DIR}/Outfit-Bold.ttf", int(ss_h * 0.40))
    tagline_font = ImageFont.truetype(f"{FONT_DIR}/WorkSans-Regular.ttf", int(ss_h * 0.11))

    word_smart, word_cart = "Smart", "Cart"
    tagline = "E-COMMERCE GROWTH ANALYTICS"

    tmp = Image.new("RGBA", (10, 10), TRANSPARENT)
    td = ImageDraw.Draw(tmp)
    w_smart = td.textlength(word_smart, font=font_bold)
    w_cart = td.textlength(word_cart, font=font_bold)
    w_tagline = td.textlength(tagline, font=tagline_font)

    pad = int(ss_h * 0.14)
    gap = int(ss_h * 0.14)
    total_w = int(pad * 2 + badge_ss + gap + max(w_smart + w_cart, w_tagline))

    canvas = Image.new("RGBA", (total_w, ss_h), CREAM)
    canvas.alpha_composite(badge, (pad, (ss_h - badge_ss) // 2))

    cd = ImageDraw.Draw(canvas)
    text_x = pad + badge_ss + gap
    word_y = int(ss_h * 0.24)
    cd.text((text_x, word_y), word_smart, font=font_bold, fill=DARK_GRN)
    cd.text((text_x + w_smart, word_y), word_cart, font=font_bold, fill=CHARCOAL)
    cd.text((text_x, int(ss_h * 0.66)), tagline, font=tagline_font, fill=(90, 100, 78, 255))

    canvas = canvas.resize((total_w // SS, height), Image.LANCZOS)
    canvas.save(out_path)


if __name__ == "__main__":
    make_icon_transparent("smartcart_icon_transparent.png", size=1024)
    make_icon_badge("smartcart_icon_badge.png", size=1024)
    make_horizontal_lockup("smartcart_logo_horizontal.png", height=800)
    make_on_cream_lockup("smartcart_logo_on_cream.png", height=900)
    print("done")
