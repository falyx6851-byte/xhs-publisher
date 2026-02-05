# xhs_core.py - 小红书图片生成核心引擎 (多风格版)
# 此文件为测试工具专用副本，不影响主脚本

import os
import re
from PIL import Image, ImageDraw, ImageFont, ImageColor

# ================= 1. 模板与配色配置 =================

STYLES = {
    'breath': {
        'BG_COLOR': "#F6F7F9", 'CARD_COLOR': "#F6F7F9", 'TEXT_MAIN': "#333333",
        'ACCENT_COLOR': "#FF2442", 'SHADOW_COLOR': None, 'HEADER_COLOR': "#666666",
        'type': 'flat'
    },
    'tech_card': {
        'BG_COLOR': "#F0F5FF", 'CARD_COLOR': "#FFFFFF", 'TEXT_MAIN': "#1E293B", 
        'ACCENT_COLOR': "#2563EB", 'SHADOW_COLOR': "#DBEAFE", 'HEADER_COLOR': "#64748B",
        'type': 'card'
    },
    'receipt': {
        'BG_COLOR': "#0099FF", 'CARD_COLOR': "#FFFFFF", 'TEXT_MAIN': "#000000",
        'ACCENT_COLOR': "#FFE66D", 'SHADOW_COLOR': None, 'HEADER_COLOR': "#FFFFFF",
        'type': 'flat'
    },
    'quote': {
        'BG_COLOR': "#D4F5D4", 'CARD_COLOR': "#FFFFFF", 'TEXT_MAIN': "#333333",
        'ACCENT_COLOR': "#FFADD2", 'SHADOW_COLOR': None, 'HEADER_COLOR': "#2E7D32",
        'type': 'flat'
    },
    'cyber': {
        'BG_COLOR': "#0F172A", 'CARD_COLOR': "#1E293B", 'TEXT_MAIN': "#F1F5F9",
        'ACCENT_COLOR': "#00E5FF", 'SHADOW_COLOR': "#000000", 'HEADER_COLOR': "#94A3B8",
        'type': 'card_outline'
    },
    'notion': {
        'BG_COLOR': "#F7F7F5", 'CARD_COLOR': "#FFFFFF", 'TEXT_MAIN': "#37352F",
        'ACCENT_COLOR': "#E16259", 'SHADOW_COLOR': "#E0E0E0", 'HEADER_COLOR': "#787774",
        'type': 'card_minimal'
    },
    'magazine': {
        'BG_COLOR': "#EAEAEA", 'CARD_COLOR': "#FFFFFF", 'TEXT_MAIN': "#000000",
        'ACCENT_COLOR': "#FF4500", 'SHADOW_COLOR': "#000000", 'HEADER_COLOR': "#000000",
        'type': 'magazine_layout'
    },
    # ===== 新增：小红书官方风格 =====
    'quote_blue': {
        'BG_COLOR': "#FAF8F5", 'CARD_COLOR': "#FAF8F5", 'TEXT_MAIN': "#1A56DB",
        'ACCENT_COLOR': "#1A56DB", 'SHADOW_COLOR': None, 'HEADER_COLOR': "#1A56DB",
        'type': 'quote_style'
    },
    'sticky': {
        'BG_COLOR': "#FFD966", 'CARD_COLOR': "#FFFFFF", 'TEXT_MAIN': "#333333",
        'ACCENT_COLOR': "#FFD966", 'SHADOW_COLOR': None, 'HEADER_COLOR': "#666666",
        'type': 'sticky_note'
    },
    'card_blue': {
        'BG_COLOR': "#4285F4", 'CARD_COLOR': "#FFFFFF", 'TEXT_MAIN': "#000000",
        'ACCENT_COLOR': "#4285F4", 'SHADOW_COLOR': None, 'HEADER_COLOR': "#4285F4",
        'type': 'card_style'
    },
    'postit': {
        'BG_COLOR': "#E8F5B4", 'CARD_COLOR': "#E8F5B4", 'TEXT_MAIN': "#333333",
        'ACCENT_COLOR': "#C5D99A", 'SHADOW_COLOR': "#CCCCCC", 'HEADER_COLOR': "#999999",
        'type': 'postit_style'
    },
    'ticket': {
        'BG_COLOR': "#2ECC71", 'CARD_COLOR': "#FFFFFF", 'TEXT_MAIN': "#000000",
        'ACCENT_COLOR': "#2ECC71", 'SHADOW_COLOR': None, 'HEADER_COLOR': "#2ECC71",
        'type': 'ticket_style'
    }
}

# ================= 2. 全局参数 =================

WIDTH = 1242
HEIGHT = 1660
BODY_FONT_SIZE = 48
TITLE_FONT_SIZE = 52
LINE_SPACING = 22
PARA_SPACING = 44
CARD_MARGIN_OUTER = 50
CARD_PADDING_INNER = 50

FONT_PATH_REGULAR = "C:/Windows/Fonts/msyh.ttc"
FONT_PATH_BOLD = "C:/Windows/Fonts/msyhbd.ttc" 
FONT_PATH_EN = "C:/Windows/Fonts/times.ttf"

# ================= 3. 工具函数库 =================

def get_font(path, size):
    try: return ImageFont.truetype(path, size)
    except: return ImageFont.load_default()

def hex_to_rgba(hex_color, opacity):
    rgb = ImageColor.getrgb(hex_color)
    return rgb + (int(opacity * 255),)

def clean_text(text):
    return re.sub(r'[^\u0000-\uFFFF]', '', text)

def tokenize(text):
    pattern = r'([a-zA-Z0-9\-\_\.]+|[^\x00-\xff]|\S|\s)'
    tokens = re.findall(pattern, text)
    return [t for t in tokens if t]

def layout_paragraph(text, font, max_width):
    tokens = tokenize(text)
    lines = []
    current_line = ""
    current_w = 0
    avoid_chars = ".,;!?)]}。，；！？、）】"
    
    for token in tokens:
        try: w = font.getlength(token)
        except: w = len(token) * font.size
        
        if current_w + w <= max_width:
            current_line += token
            current_w += w
        else:
            if token in avoid_chars and w < 60: 
                current_line += token
            elif token.isspace():
                pass 
            else:
                lines.append(current_line)
                current_line = token
                current_w = w
    if current_line:
        lines.append(current_line)
    return lines

def layout_cover_title(title, font, max_width, max_lines=4):
    """
    封面标题专用：信任用户手动分行，不再二次切分
    直接返回用户分好的行（最多 max_lines 行）
    """
    # 处理转义的换行符
    title = title.replace('\\n', '\n')
    lines = [line.strip() for line in title.split('\n') if line.strip()]
    return lines[:max_lines] if lines else [title[:15]]

def get_adaptive_font_for_title(lines, base_font_size, min_font_size, max_width, font_path):
    """
    自适应字体大小：
    - 优先使用 base_font_size
    - 如果有行超出 max_width，逐步缩小字体
    - 最小不低于 min_font_size
    返回：(font, font_size)
    """
    font_size = base_font_size
    while font_size >= min_font_size:
        font = get_font(font_path, font_size)
        all_fit = True
        for line in lines:
            try:
                w = font.getlength(line)
            except:
                w = len(line) * font_size
            if w > max_width:
                all_fit = False
                break
        if all_fit:
            return font, font_size
        font_size -= 5
    # 返回最小字体
    return get_font(font_path, min_font_size), min_font_size

def draw_text_native(draw, xy, text, font, fill):
    draw.text(xy, text.strip(), font=font, fill=fill)

def draw_text_centered(draw, xy, text, font, fill):
    x, y = xy
    try: w = font.getlength(text)
    except: w = len(text) * font.size
    draw.text((x - w/2, y), text, font=font, fill=fill)

# ================= 4. 渲染逻辑 =================

class XHSGenerator:
    def __init__(self, template_name, header_text, footer_text, output_dir="xhs_output"):
        self.template_name = template_name
        self.style = STYLES.get(template_name, STYLES['tech_card'])
        self.header_text = header_text
        self.footer_text = footer_text
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def _draw_cover_magazine(self, img, draw, title):
        cfg = self.style
        draw.rectangle([(0, 0), (100, HEIGHT)], fill=cfg['ACCENT_COLOR'])
        draw.rectangle([(100, 0), (WIDTH, HEIGHT)], fill=cfg['CARD_COLOR'])
        draw.text((150, 100), "ISSUE 01", font=get_font(FONT_PATH_EN, 60), fill=cfg['ACCENT_COLOR'])
        
        # 信任用户分行 + 自适应字体
        margin_left = 130 
        max_title_width = WIDTH - margin_left - 60
        lines = layout_cover_title(title, None, max_title_width, max_lines=5)
        font, font_size = get_adaptive_font_for_title(lines, 160, 90, max_title_width, FONT_PATH_BOLD)
        
        line_height = font_size + 40
        current_y = 400
        
        for line in lines:
            draw.text((margin_left, current_y), line, font=font, fill=cfg['TEXT_MAIN'])
            current_y += line_height
        
        draw.rectangle([(margin_left, HEIGHT - 300), (WIDTH - 100, HEIGHT - 290)], fill="#000000")
        f_font = get_font(FONT_PATH_BOLD, 50)
        try: f_w = f_font.getlength(self.footer_text)
        except: f_w = len(self.footer_text) * 50
        draw.text((WIDTH - 100 - f_w, HEIGHT - 250), self.footer_text, font=f_font, fill="#000000")

    def _draw_cover_standard(self, img, draw, title):
        cfg = self.style
        img.paste(Image.new('RGB', img.size, cfg['BG_COLOR']))
        draw = ImageDraw.Draw(img)

        # ===== Breath 呼吸感风格 =====
        if self.template_name == 'breath':
            # 顶部深色色块
            draw.rectangle([(0, 0), (WIDTH, 200)], fill=cfg['TEXT_MAIN'])
            draw.text((60, 60), "AI DAILY NEWS", font=get_font(FONT_PATH_BOLD, 40), fill="#FFFFFF")
            
            # 标题绘制：信任用户分行 + 自适应字体
            max_title_width = WIDTH - 200
            lines = layout_cover_title(title, None, max_title_width, max_lines=4)
            font, font_size = get_adaptive_font_for_title(lines, 120, 75, max_title_width, FONT_PATH_BOLD)
            
            line_height = font_size + 40
            start_y = 500
            
            for i, line in enumerate(lines):
                line_y = start_y + i * line_height
                # 阴影效果
                draw.text((105, line_y+5), line, font=font, fill="#dddddd")
                # 正文
                draw.text((100, line_y), line, font=font, fill=cfg['TEXT_MAIN'])
            
            # 底部红色装饰线
            final_y = start_y + len(lines) * line_height + 50
            draw.line([100, final_y, 300, final_y], fill=cfg['ACCENT_COLOR'], width=10)
            return  # breath 封面处理完毕

        # ===== quote_blue 蓝色引言风格 =====
        if self.template_name == 'quote_blue':
            # 圆角背景卡片
            draw.rounded_rectangle([(40, 40), (WIDTH-40, HEIGHT-40)], radius=60, fill=cfg['BG_COLOR'])
            # 左上角蓝色引号 (使用中文引号)
            quote_font = get_font(FONT_PATH_BOLD, 120)
            draw.text((80, 80), '"', font=quote_font, fill=cfg['ACCENT_COLOR'])
            # 右下角蓝色引号
            draw.text((80, HEIGHT-220), '"', font=quote_font, fill=cfg['ACCENT_COLOR'])
            # 标题绘制：信任用户分行 + 自适应字体
            max_title_width = WIDTH - 240
            lines = layout_cover_title(title, None, max_title_width, max_lines=4)
            font, font_size = get_adaptive_font_for_title(lines, 110, 65, max_title_width, FONT_PATH_BOLD)
            line_height = font_size + 40
            start_y = 400
            for i, line in enumerate(lines):
                draw.text((120, start_y + i * line_height), line, font=font, fill=cfg['TEXT_MAIN'])
            return

        # ===== sticky 黄色便签风格 =====
        if self.template_name == 'sticky':
            margin = 60
            # 黄色外框
            draw.rounded_rectangle([(margin, margin), (WIDTH-margin, HEIGHT-margin)], radius=40, fill=cfg['ACCENT_COLOR'])
            # 白色内卡
            inner_margin = margin + 30
            inner_top = margin + 100
            draw.rounded_rectangle([(inner_margin, inner_top), (WIDTH-inner_margin, HEIGHT-inner_margin-30)], radius=30, fill=cfg['CARD_COLOR'])
            # 顶部装饰
            draw.text((inner_margin + 20, margin + 25), "Sticky Notes", font=get_font(FONT_PATH_BOLD, 36), fill="#666666")
            draw.ellipse((WIDTH//2 - 15, margin + 25, WIDTH//2 + 15, margin + 55), fill="#FFB800")
            draw.text((WIDTH - inner_margin - 160, margin + 25), "AI Daily", font=get_font(FONT_PATH_BOLD, 36), fill="#666666")
            # 横线装饰
            line_start_y = inner_top + 60
            for i in range(12):
                y = line_start_y + i * 85
                if y < HEIGHT - inner_margin - 100:
                    draw.line([(inner_margin + 30, y), (WIDTH - inner_margin - 30, y)], fill="#E0E0E0", width=2)
            # 标题绘制：信任用户分行 + 自适应字体
            max_title_width = WIDTH - 2 * inner_margin - 100
            lines = layout_cover_title(title, None, max_title_width, max_lines=4)
            font, font_size = get_adaptive_font_for_title(lines, 100, 65, max_title_width, FONT_PATH_BOLD)
            line_height = font_size + 30
            start_y = inner_top + 200
            for i, line in enumerate(lines):
                draw.text((inner_margin + 50, start_y + i * line_height), line, font=font, fill=cfg['TEXT_MAIN'])
            return

        # ===== card_blue 蓝色卡片风格 =====
        if self.template_name == 'card_blue':
            margin = 50
            # 蓝色背景
            draw.rounded_rectangle([(0, 0), (WIDTH, HEIGHT)], radius=0, fill=cfg['BG_COLOR'])
            # 白色卡片
            card_margin = 80
            card_top = 100
            card_bottom = HEIGHT - 180
            draw.rounded_rectangle([(card_margin, card_top), (WIDTH-card_margin, card_bottom)], radius=40, fill=cfg['CARD_COLOR'])
            # 底部标签
            draw.text((card_margin + 40, card_bottom + 40), "Monday", font=get_font(FONT_PATH_BOLD, 36), fill="#FFFFFF")
            draw.text((WIDTH - card_margin - 180, card_bottom + 40), "Text Note", font=get_font(FONT_PATH_BOLD, 36), fill="#FFFFFF")
            # 标题绘制：信任用户分行 + 自适应字体
            max_title_width = WIDTH - 2 * card_margin - 160
            lines = layout_cover_title(title, None, max_title_width, max_lines=4)
            font, font_size = get_adaptive_font_for_title(lines, 110, 65, max_title_width, FONT_PATH_BOLD)
            line_height = font_size + 40
            start_y = card_top + 250
            for i, line in enumerate(lines):
                draw.text((card_margin + 80, start_y + i * line_height), line, font=font, fill=cfg['TEXT_MAIN'])
            return

        # ===== postit 便利贴风格 (浅粉色系) =====
        if self.template_name == 'postit':
            margin = 60
            # 阴影效果
            draw.polygon([(margin+15, margin+20), (WIDTH-margin+8, margin+15), 
                         (WIDTH-margin+12, HEIGHT-margin+8), (margin+8, HEIGHT-margin+12)], fill="#E0E0E0")
            # 便利贴主体 (浅粉色)
            draw.rectangle([(margin, margin), (WIDTH-margin, HEIGHT-margin)], fill="#FFE4EC")
            # 右上角胶带效果
            tape_w, tape_h = 100, 50
            tape_x, tape_y = WIDTH - margin - 60, margin - 15
            draw.polygon([(tape_x, tape_y), (tape_x+tape_w, tape_y-10), 
                         (tape_x+tape_w+5, tape_y+tape_h), (tape_x-5, tape_y+tape_h+10)], fill="#F5DEB3")
            # 标题绘制：信任用户分行 + 自适应字体
            max_title_width = WIDTH - 2 * margin - 160
            lines = layout_cover_title(title, None, max_title_width, max_lines=4)
            font, font_size = get_adaptive_font_for_title(lines, 100, 65, max_title_width, FONT_PATH_BOLD)
            line_height = font_size + 40
            start_y = 400
            for i, line in enumerate(lines):
                draw.text((margin + 80, start_y + i * line_height), line, font=font, fill="#333333")
            # 右下角签名
            draw.text((WIDTH - margin - 200, HEIGHT - margin - 80), "...Note!", font=get_font(FONT_PATH_REGULAR, 40), fill="#CC6699")
            return

        # ===== ticket 绿色票据风格 =====
        if self.template_name == 'ticket':
            margin = 50
            # 绿色背景
            draw.rounded_rectangle([(0, 0), (WIDTH, HEIGHT)], radius=50, fill=cfg['BG_COLOR'])
            # 白色票据卡片
            card_margin = 80
            card_top = 100
            card_bottom = HEIGHT - 100
            draw.rounded_rectangle([(card_margin, card_top), (WIDTH-card_margin, card_bottom)], radius=30, fill=cfg['CARD_COLOR'])
            # 顶部绿色装饰条
            draw.rectangle([(card_margin, card_top), (WIDTH-card_margin, card_top + 50)], fill=cfg['ACCENT_COLOR'])
            # 底部锯齿效果
            tooth_size = 25
            tooth_y = card_bottom
            for i in range(int((WIDTH - 2 * card_margin) / tooth_size) + 1):
                cx_t = card_margin + i * tooth_size + tooth_size/2
                draw.polygon([(cx_t - tooth_size/2, tooth_y), (cx_t, tooth_y + tooth_size), 
                             (cx_t + tooth_size/2, tooth_y)], fill=cfg['BG_COLOR'])
            # 底部文字
            draw.text((card_margin + 30, card_bottom - 80), "MONDAY", font=get_font(FONT_PATH_EN, 32), fill="#AAAAAA")
            draw.text((WIDTH - card_margin - 100, card_bottom - 80), "###", font=get_font(FONT_PATH_EN, 32), fill="#AAAAAA")
            # 标题绘制：信任用户分行 + 自适应字体
            max_title_width = WIDTH - 2 * card_margin - 160
            lines = layout_cover_title(title, None, max_title_width, max_lines=4)
            font, font_size = get_adaptive_font_for_title(lines, 110, 65, max_title_width, FONT_PATH_BOLD)
            line_height = font_size + 40
            start_y = card_top + 250
            for i, line in enumerate(lines):
                draw.text((card_margin + 80, start_y + i * line_height), line, font=font, fill=cfg['TEXT_MAIN'])
            return

        # ===== tech_card 顶部装饰 =====
        if self.template_name == 'tech_card':
            draw.rectangle([(0, 0), (WIDTH, 50)], fill=cfg['ACCENT_COLOR'])
        
        cx, cy, cw, ch = 80, 250, WIDTH-160, HEIGHT-500
        
        if self.template_name == 'tech_card':
            draw.rounded_rectangle([(cx+15, cy+15), (cx+cw+15, cy+ch+15)], radius=40, fill=cfg['SHADOW_COLOR'])
            draw.rounded_rectangle([(cx, cy), (cx+cw, cy+ch)], radius=40, fill=cfg['CARD_COLOR'])
            for i in range(3): draw.ellipse((cx+50+i*30, cy+50, cx+70+i*30, cy+70), fill=cfg['ACCENT_COLOR'])
            
        elif self.template_name == 'cyber':
            draw.rounded_rectangle([(cx, cy), (cx+cw, cy+ch)], radius=20, outline=cfg['ACCENT_COLOR'], width=4)
            draw.rounded_rectangle([(cx, cy), (cx+cw, cy+ch)], radius=20, fill=cfg['CARD_COLOR'])
            draw.ellipse((cx+40, cy+40, cx+60, cy+60), fill="#FF5F56")
            draw.ellipse((cx+80, cy+40, cx+100, cy+60), fill="#FFBD2E")
            draw.ellipse((cx+120, cy+40, cx+140, cy+60), fill="#27C93F")
            
        elif self.template_name == 'notion':
            cx, cy, cw, ch = 100, 300, WIDTH-200, HEIGHT-600
            draw.rectangle([(cx, cy), (cx+cw, cy+ch)], fill=cfg['CARD_COLOR'])
            icon_y = cy - 100
            draw.ellipse((WIDTH//2 - 80, icon_y, WIDTH//2 + 80, icon_y + 160), fill="#FFFFFF")

        elif self.template_name == 'receipt':
            paper_margin = 100
            paper_top, paper_bottom = 150, HEIGHT - 200
            draw.rectangle([(paper_margin, paper_top), (WIDTH - paper_margin, paper_bottom)], fill=cfg['CARD_COLOR'])
            draw.rectangle([(paper_margin, paper_top-20), (WIDTH - paper_margin, paper_top+20)], fill="#007ACC")
            tooth_size = 30
            for i in range(int((WIDTH - 2 * paper_margin) / tooth_size) + 1):
                cx_t = paper_margin + i * tooth_size + tooth_size/2
                draw.ellipse((cx_t - tooth_size/2, paper_bottom - tooth_size/2, cx_t + tooth_size/2, paper_bottom + tooth_size/2), fill=cfg['BG_COLOR'])
            cx, cy, cw, ch = paper_margin, paper_top, WIDTH - 2*paper_margin, paper_bottom - paper_top
        
        elif self.template_name == 'quote':
            margin = 120
            draw.text((margin - 20, 150), '"', font=get_font(FONT_PATH_EN, 400), fill="#A8E6A8")
            cx, cy, cw, ch = margin, 550, WIDTH-2*margin, HEIGHT-600

        # 信任用户分行 + 自适应字体
        max_title_width = cw - 100 if 'cw' in dir() else WIDTH - 200
        base_font_size = 130 if self.template_name != 'receipt' else 140
        lines = layout_cover_title(title, None, max_title_width, max_lines=4)
        font, font_size = get_adaptive_font_for_title(lines, base_font_size, 75, max_title_width, FONT_PATH_BOLD)
        
        line_height = font_size + 50
        if self.template_name == 'notion': start_y = cy + 150
        elif self.template_name == 'quote': start_y = 550
        else: start_y = cy + (ch - len(lines)*line_height) // 2
        
        for i, line in enumerate(lines):
            try: w = font.getlength(line.strip())
            except: w = len(line)*font_size
            
            if self.template_name == 'quote': line_x = cx
            else: line_x = (WIDTH - w) // 2
            
            line_y = start_y + i * line_height
            
            if self.template_name == 'tech_card' or (self.template_name == 'notion' and i==0):
                highlight = Image.new('RGBA', img.size, (0,0,0,0))
                h_draw = ImageDraw.Draw(highlight)
                h_color = hex_to_rgba(cfg['ACCENT_COLOR'], 0.15 if self.template_name=='tech_card' else 0.2)
                h_draw.rectangle([(line_x+10, line_y + font_size - 30), (line_x+w+10, line_y + font_size)], fill=h_color)
                img.paste(Image.alpha_composite(img.convert('RGBA'), highlight), (0,0))
                draw = ImageDraw.Draw(img)
            elif self.template_name in ['receipt', 'quote'] and (i > 0 or len(lines)==1 or i == len(lines)-1):
                draw.rounded_rectangle([(line_x - 10, line_y + 10), (line_x + w + 10, line_y + font_size + 20)], radius=10, fill=cfg['ACCENT_COLOR'])

            fill_color = cfg['TEXT_MAIN']
            if self.template_name == 'cyber':
                draw.text((line_x, line_y), line, font=font, fill=cfg['ACCENT_COLOR'])
                draw.text((line_x-2, line_y-2), line, font=font, fill=cfg['TEXT_MAIN'])
            else:
                draw.text((line_x, line_y), line.strip(), font=font, fill=fill_color)

        f_font = get_font(FONT_PATH_REGULAR, 40)
        if self.template_name == 'cyber':
            draw_text_centered(draw, (WIDTH/2, HEIGHT-150), ">>> " + self.footer_text + " <<<", get_font(FONT_PATH_EN, 40), cfg['ACCENT_COLOR'])
        elif self.template_name == 'receipt':
            try: f_w = f_font.getlength(self.footer_text)
            except: f_w = len(self.footer_text) * 40
            draw_text_native(draw, (WIDTH - 100 - f_w - 30, HEIGHT - 200 - 80), self.footer_text, f_font, "#B0B0B0")
        elif self.template_name != 'quote':
            try: f_w = f_font.getlength(self.footer_text)
            except: f_w = len(self.footer_text) * 40
            draw_text_native(draw, ((WIDTH - 100) - f_w, HEIGHT-150), self.footer_text, f_font, "#64748B" if self.template_name=='tech_card' else "#999")

    def generate_cover(self, title):
        clean_title = clean_text(title)
        img = Image.new('RGB', (WIDTH, HEIGHT), "#FFFFFF")
        draw = ImageDraw.Draw(img)
        
        if self.template_name == 'magazine':
            self._draw_cover_magazine(img, draw, clean_title)
        else:
            self._draw_cover_standard(img, draw, clean_title)
            
        filename = "01_cover.png"
        img.save(os.path.join(self.output_dir, filename))
        print(f"封面已生成: {filename}")

    def generate_body(self, content):
        cfg = self.style
        clean_content = clean_text(content)
        
        font_reg = get_font(FONT_PATH_REGULAR, BODY_FONT_SIZE)
        font_bold = get_font(FONT_PATH_BOLD, TITLE_FONT_SIZE)
        
        content_width = WIDTH - (CARD_MARGIN_OUTER * 2) - (CARD_PADDING_INNER * 2)
        
        all_items = []
        for para in clean_content.split('\n'):
            para = para.strip()
            if not para:
                all_items.append(('space', ""))
                continue
            is_title = (para[0].isdigit() and "." in para[:3]) or para.startswith("#")
            clean_para = para.lstrip("#").strip()
            target_font = font_bold if is_title else font_reg
            
            layout_lines = layout_paragraph(clean_para, target_font, content_width)
            for line in layout_lines:
                all_items.append(('title' if is_title else 'text', line))

        page_num = 1
        card_x, card_y = CARD_MARGIN_OUTER, 150
        card_w, card_h = WIDTH - (CARD_MARGIN_OUTER * 2), HEIGHT - 200
        
        def init_page_img():
            img = Image.new('RGB', (WIDTH, HEIGHT), cfg['BG_COLOR'])
            draw = ImageDraw.Draw(img)
            
            if self.template_name == 'tech_card':
                draw.rounded_rectangle([(card_x+15, card_y+15), (card_x+card_w+15, card_y+card_h+15)], radius=30, fill=cfg['SHADOW_COLOR'])
                draw.rounded_rectangle([(card_x, card_y), (card_x+card_w, card_y+card_h)], radius=30, fill=cfg['CARD_COLOR'])
            elif self.template_name == 'cyber':
                draw.rounded_rectangle([(card_x, card_y), (card_x+card_w, card_y+card_h)], radius=20, outline=cfg['ACCENT_COLOR'], width=2)
                draw.rounded_rectangle([(card_x, card_y), (card_x+card_w, card_y+card_h)], radius=20, fill=cfg['CARD_COLOR'])
            elif self.template_name == 'magazine':
                draw.rectangle([(card_x, card_y), (card_x+card_w, card_y+card_h)], outline="#000", width=4, fill="#FFFFFF")
            elif self.template_name in ['breath', 'quote_blue']:
                # 呼吸感和蓝色引言：白色卡片 + 浅色边框
                draw.rounded_rectangle([(card_x, card_y), (card_x+card_w, card_y+card_h)], radius=30, fill="#FFFFFF", outline="#E0E0E0", width=2)
            else:
                draw.rounded_rectangle([(card_x, card_y), (card_x+card_w, card_y+card_h)], radius=30, fill=cfg['CARD_COLOR'])
            
            draw.text((card_x, 60), clean_text(self.header_text), font=get_font(FONT_PATH_BOLD, 40), fill=cfg['HEADER_COLOR'])
            return img, draw

        img, draw = init_page_img()
        cursor_y = card_y + CARD_PADDING_INNER
        cursor_x = card_x + CARD_PADDING_INNER
        
        for item_type, text in all_items:
            if item_type == 'title':
                h = TITLE_FONT_SIZE + LINE_SPACING + 10
                font = font_bold
                color = cfg['TEXT_MAIN']
                if self.template_name == 'cyber': color = cfg['ACCENT_COLOR']
            elif item_type == 'space':
                h = PARA_SPACING
            else:
                h = BODY_FONT_SIZE + LINE_SPACING
                font = font_reg
                color = "#DDDDDD" if self.template_name == 'cyber' else ("#333333" if cfg['TEXT_MAIN'] != "#000000" else "#000000")
            
            if cursor_y + h > card_y + card_h - CARD_PADDING_INNER:
                filename = f"02_body_{page_num}.png"
                img.save(os.path.join(self.output_dir, filename))
                print(f"正文页 {page_num} 已生成")
                page_num += 1
                img, draw = init_page_img()
                cursor_y = card_y + CARD_PADDING_INNER
            
            if item_type != 'space':
                draw_text_native(draw, (cursor_x, cursor_y), text, font, color)
            cursor_y += h

        filename = f"02_body_{page_num}.png"
        img.save(os.path.join(self.output_dir, filename))
        print(f"正文页 {page_num} 已生成 (完成)")
