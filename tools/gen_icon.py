# DevDash 图标生成：深色圆角底 + 青色「谜」字 + 语义色点阵
import os

from PIL import Image, ImageDraw, ImageFont

SIZE = 512
BG = (11, 16, 32, 255)        # #0B1020
INFO = (34, 211, 238, 255)    # #22D3EE
ACCENT = (167, 139, 250, 255) # #A78BFA
WARN = (251, 191, 36, 255)    # #FBBF24
OK = (52, 211, 153, 255)      # #34D399

out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
os.makedirs(out_dir, exist_ok=True)

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# 圆角底板 + 青色描边（两层制造微光感）
d.rounded_rectangle([8, 8, SIZE - 8, SIZE - 8], radius=110, fill=BG, outline=(34, 211, 238, 90), width=14)
d.rounded_rectangle([22, 22, SIZE - 22, SIZE - 22], radius=100, outline=INFO, width=6)

# 中央「谜」字
font = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 300)
bbox = d.textbbox((0, 0), "谜", font=font)
tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
d.text(((SIZE - tw) / 2 - bbox[0], (SIZE - th) / 2 - bbox[1] - 20), "谜", font=font, fill=INFO)

# 右下角天气语义点阵（晴/多云/雨）
cx, cy, r, gap = SIZE - 150, SIZE - 110, 16, 56
for i, c in enumerate((OK, WARN, ACCENT)):
    d.ellipse([cx + i * gap - r, cy - r, cx + i * gap + r, cy + r], fill=c)

png_path = os.path.join(out_dir, "icon.png")
ico_path = os.path.join(out_dir, "icon.ico")
img.save(png_path)
img.save(ico_path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(png_path)
print(ico_path)
