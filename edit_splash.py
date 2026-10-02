
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import os

img_path = r"C:\Users\Vill3\.gemini\antigravity\brain\f9732238-5384-4f24-8075-ded12557e9eb\shadowtrade_splash_v1_1790950228971.jpg"
out_path = r"C:\Users\Vill3\.gemini\antigravity\brain\f9732238-5384-4f24-8075-ded12557e9eb\shadowtrade_splash_v3.jpg"

img = Image.open(img_path).convert("RGB")
draw = ImageDraw.Draw(img)

# We want to cover JUST the subtitle and draw the bar lower down.
# The previous box started at 650, which cut off the main title. 
# The main title ends around 660. The subtitle is probably 665-685.

# Sample the background color from an empty area inside the phone
bg_color = img.getpixel((512, 750)) 

# Cover the subtitle softly
box = (330, 665, 694, 695)
draw.rectangle(box, fill=bg_color)

# Draw loading bar further down
bar_y = 710
bar_box = (350, bar_y, 674, bar_y + 10)
draw.rounded_rectangle(bar_box, radius=5, outline=(0, 255, 255), width=2)
fill_box = (352, bar_y + 2, 500, bar_y + 8)
draw.rounded_rectangle(fill_box, radius=3, fill=(0, 255, 255))

# Draw text
try:
    font = ImageFont.truetype("arial.ttf", 12)
    draw.text((485, bar_y - 20), "Loading...", fill=(200, 200, 200), font=font)
except:
    pass

img.save(out_path, quality=95)
print("Done")

