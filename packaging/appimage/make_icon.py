"""Draw the 256px app icon: a teal mic on a dark rounded square."""
import sys
from PIL import Image, ImageDraw

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((8, 8, S - 8, S - 8), radius=52, fill=(22, 27, 34, 255))
teal = (45, 212, 191, 255)
d.rounded_rectangle((100, 48, 156, 150), radius=28, fill=teal)          # capsule
d.arc((72, 90, 184, 182), start=0, end=180, fill=teal, width=12)         # cradle
d.line((128, 182, 128, 210), fill=teal, width=12)                        # stem
d.line((96, 210, 160, 210), fill=teal, width=12)                         # base
img.save(sys.argv[1])
