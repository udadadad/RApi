from PIL import Image, ImageDraw

def create_icon():
    # Создаем изображение 256x256 с прозрачным фоном
    size = (256, 256)
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Цвета как на скриншоте (Windows Generic App Icon)
    border_color = (0, 103, 192) # Тёмно-синий
    inner_color = (135, 206, 250) # Светло-синий/голубой
    
    # Рисуем основной синий прямоугольник (тело иконки)
    draw.rectangle([40, 60, 216, 196], fill=border_color)
    
    # Рисуем внутренний "экран" (светлый прямоугольник)
    draw.rectangle([60, 80, 150, 150], fill=inner_color)
    
    # Дополнительная синяя полоска справа
    draw.rectangle([165, 80, 195, 100], fill=inner_color)
    draw.rectangle([165, 120, 195, 140], fill=inner_color)
    
    # Сохраняем как .ico
    img.save('app.ico', format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("Icon created successfully: app.ico")

if __name__ == "__main__":
    create_icon()
