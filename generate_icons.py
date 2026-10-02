from PIL import Image, ImageDraw

def create_icon(size, filename, radius=0):
    img = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    if radius > 0:
        draw.rounded_rectangle([(0, 0), (512, 512)], radius=radius, fill=(8, 8, 10, 255))
    else:
        draw.rectangle([(0, 0), (512, 512)], fill=(8, 8, 10, 255))
        
    points = [(120, 380), (256, 120), (392, 380)]
    draw.polygon(points, outline=(157, 0, 255, 255), width=36)
    
    inner_points = [(256, 180), (340, 340), (172, 340)]
    draw.polygon(inner_points, fill=(157, 0, 255, 204))
    
    if size != 512:
        img = img.resize((size, size), Image.Resampling.LANCZOS)
    img.save(filename)

create_icon(512, 'static/assets/app_icon_512.png', radius=112)
create_icon(192, 'static/assets/app_icon_192.png', radius=42)
create_icon(180, 'static/assets/apple-touch-icon.png') # iOS handles rounded corners itself
create_icon(64, 'static/favicon.ico')
print('Images generated')
