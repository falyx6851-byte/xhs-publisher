# pipeline.py - 发布流水线核心逻辑
# 串联抓取、AI生成、渲染、发布全流程

import asyncio
import os
import sys
import json
import re
import shutil
import glob
from datetime import datetime
from playwright.async_api import async_playwright
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import httpx
from bs4 import BeautifulSoup

# 添加父目录到路径，以便导入核心模块
try:
    from .xhs_core import XHSGenerator
    from .config_manager import ConfigManager
except ImportError:
    # 尝试直接导入 (兼容 old style)
    try:
        from xhs_core import XHSGenerator
        from config_manager import ConfigManager
    except ImportError:
        # 尝试从 core 导入 (兼容 root execution)
        from core.xhs_core import XHSGenerator
        from core.config_manager import ConfigManager

# ================== 常量 ==================
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USER_DATA_DIR = os.path.join(PARENT_DIR, "xhs_browser_data")
LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
ARCHIVES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "archives")

# 确保目录存在
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(ARCHIVES_DIR, exist_ok=True)


class Logger:
    """日志管理器"""
    def __init__(self, callback=None):
        self.callback = callback  # GUI 回调
        self.logs = []
        self.log_file = os.path.join(LOGS_DIR, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] {message}"
        self.logs.append(full_msg)
        
        # 写入文件
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(full_msg + "\n")
        
        # GUI 回调
        if self.callback:
            self.callback(full_msg)
        else:
            print(full_msg)
    
    async def save_screenshot(self, page, name):
        """保存错误截图"""
        path = os.path.join(LOGS_DIR, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{name}.png")
        try:
            await page.screenshot(path=path)
            self.log(f"📸 截图已保存: {path}")
            return path
        except:
            return None


class PublishPipeline:
    """发布流水线"""
    
    def __init__(self, config_manager: ConfigManager, logger: Logger = None):
        self.config = config_manager
        self.logger = logger or Logger()
        self.progress_callback = None  # 进度回调 (0-100)
        
        # 运行时数据
        self.scraped_data = None
        self.ai_data = None
        self.image_paths = []
        self.archive_dir = None
        self.image_template = 'breath'  # 默认图文模板
    
    def set_progress_callback(self, callback):
        self.progress_callback = callback
    
    def update_progress(self, value):
        if self.progress_callback:
            self.progress_callback(value)
    
    # ================== 1. 抓取模块 ==================
    async def scrape(self, url, headless=False):
        """抓取文章内容"""
        self.logger.log(f"🕷️ 正在抓取: {url}")
        self.update_progress(10)
        
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                headless=headless,
                channel="chrome",
                viewport={'width': 1280, 'height': 800},
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = context.pages[0]
            
            try:
                await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                await page.goto(url, timeout=60000)
                await page.wait_for_timeout(3000)
                
                title = await page.title()
                content = await page.evaluate("""() => {
                    document.querySelectorAll('script, style, nav, footer, iframe').forEach(e => e.remove());
                    return document.body.innerText;
                }""")
                
                self.scraped_data = {
                    "title": title,
                    "url": url,
                    "full_text": content[:15000]
                }
                
                self.logger.log(f"✅ 抓取成功: {title[:30]}... ({len(content)}字)")
                self.update_progress(25)
                return self.scraped_data
                
            except Exception as e:
                self.logger.log(f"❌ 抓取失败: {e}")
                await self.logger.save_screenshot(page, "scrape_error")
                return None
            finally:
                await context.close()
    
    async def scrape_lightweight(self, url):
        """轻量级 HTTP 抓取 (用于云端环境，不需要浏览器)"""
        self.logger.log(f"🌐 [轻量模式] 正在抓取: {url}")
        self.update_progress(10)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 移除不需要的元素
                for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'iframe', 'noscript']):
                    tag.decompose()
                
                # 提取标题
                title = soup.title.string if soup.title else "未知标题"
                
                # 提取正文
                # 微信公众号特定选择器
                article = soup.find('div', id='js_content') or soup.find('div', class_='rich_media_content')
                if article:
                    content = article.get_text(separator='\n', strip=True)
                else:
                    content = soup.body.get_text(separator='\n', strip=True) if soup.body else ""
                
                self.scraped_data = {
                    "title": title.strip() if title else "未知标题",
                    "url": url,
                    "full_text": content[:15000]
                }
                
                self.logger.log(f"✅ [轻量模式] 抓取成功: {self.scraped_data['title'][:30]}... ({len(content)}字)")
                self.update_progress(25)
                return self.scraped_data
                
        except httpx.HTTPStatusError as e:
            self.logger.log(f"❌ HTTP 错误: {e.response.status_code}")
            return None
        except Exception as e:
            self.logger.log(f"❌ 抓取失败: {e}")
            return None
    
    # ================== 2. AI 生成模块 ==================
    def generate_content(self, prompt_template):
        """调用 Gemini 生成内容"""
        if not self.scraped_data:
            self.logger.log("❌ 没有抓取数据")
            return None
        
        api_key = self.config.get_current_api_key()
        model_name = self.config.get_current_model()
        
        if not api_key:
            self.logger.log("❌ 未设置 API Key")
            return None
        
        if not prompt_template or not prompt_template.strip():
            self.logger.log("❌ 提示词模板为空，请先编辑模板内容")
            return None
        
        self.logger.log(f"🧠 AI 正在思考 (模型: {model_name})...")
        self.update_progress(35)
        
        genai.configure(api_key=api_key)
        
        user_prompt = prompt_template.format(
            url=self.scraped_data['url'],
            full_text=self.scraped_data['full_text']
        )
        
        safety_settings = {HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE}
        
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(user_prompt, safety_settings=safety_settings)
            
            txt = response.text
            self.logger.log(f"📄 AI 返回 {len(txt)} 字符")
            
            # 多种方式提取 JSON
            json_str = None
            
            # 方式1: ```json ... ```
            if "```json" in txt:
                try:
                    json_str = txt.split("```json")[1].split("```")[0].strip()
                except:
                    pass
            
            # 方式2: ``` ... ```
            if not json_str and "```" in txt:
                try:
                    json_str = txt.split("```")[1].split("```")[0].strip()
                except:
                    pass
            
            # 方式3: 直接查找 { ... }
            if not json_str:
                match = re.search(r'\{[\s\S]*\}', txt)
                if match:
                    json_str = match.group(0)
            
            # 方式4: 直接使用原文
            if not json_str:
                json_str = txt.strip()
            
            # 尝试解析
            self.ai_data = json.loads(json_str)
            
            # 验证必需字段
            if 'cover_title' not in self.ai_data:
                self.logger.log("⚠️ 缺少 cover_title 字段")
                return None
            if 'content_body' not in self.ai_data:
                self.logger.log("⚠️ 缺少 content_body 字段")
                return None
            
            self.logger.log(f"✅ 内容生成成功: {self.ai_data.get('cover_title', 'No Title')[:20]}")
            self.update_progress(50)
            return self.ai_data
            
        except json.JSONDecodeError as e:
            self.logger.log(f"❌ JSON 解析失败: {e}")
            self.logger.log(f"📝 原始返回 (前500字): {txt[:500] if txt else 'N/A'}")
            return None
        except Exception as e:
            self.logger.log(f"❌ AI 生成失败: {e}")
            return None

    
    # ================== 3. 渲染模块 ==================
    def render_images(self, output_dir=None):
        """渲染小红书图片"""
        if not self.ai_data:
            self.logger.log("❌ 没有 AI 数据")
            return []
        
        self.logger.log("🎨 正在渲染图片...")
        self.update_progress(60)
        
        if not output_dir:
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_output")
        
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir)
        
        try:
            template_name = getattr(self, 'image_template', 'breath') or 'breath'
            generator = XHSGenerator(
                template_name=template_name,
                header_text='AI NEWS',
                footer_text='@AI Daily',
                output_dir=output_dir
            )
            
            # 清洗标题并智能换行
            raw_title = self.ai_data['cover_title'].replace("\\n", "\n")
            clean_title = self._remove_emojis(raw_title)
            clean_title = self._smart_wrap_title(clean_title)
            generator.generate_cover(clean_title)
            
            # 清洗正文
            clean_body = self._remove_emojis(self.ai_data['content_body'])
            generator.generate_body(clean_body)
            
            # 收集图片
            self.image_paths = []
            cover_path = os.path.join(output_dir, "01_cover.png")
            if os.path.exists(cover_path):
                self.image_paths.append(cover_path)
            
            body_files = glob.glob(os.path.join(output_dir, "02_body_*.png"))
            body_files.sort(key=lambda x: int(re.search(r'body_(\d+)', x).group(1)))
            self.image_paths.extend(body_files)
            
            self.logger.log(f"✅ 渲染完成，共 {len(self.image_paths)} 张图片")
            self.update_progress(75)
            return self.image_paths
            
        except Exception as e:
            self.logger.log(f"❌ 渲染失败: {e}")
            return []
    
    def _remove_emojis(self, text):
        if not text:
            return ""
        return re.sub(r'[\U00010000-\U0010ffff\u2600-\u26ff\u2700-\u27bf\ufe00-\ufe0f\u2300-\u23ff\u200d\u2b50]', '', text).strip()
    
    def _smart_wrap_title(self, title, max_chars_per_line=7, max_lines=3):
        """
        智能换行标题：
        - 每行不超过 max_chars_per_line 个字符
        - 不拆分英文单词
        - 最多 max_lines 行
        """
        if not title:
            return title
        
        # 如果已有换行且格式合理，保持原样
        existing_lines = title.split('\n')
        all_ok = all(len(line.strip()) <= max_chars_per_line + 3 for line in existing_lines if line.strip())
        if len(existing_lines) > 1 and all_ok:
            return title
        
        # 合并所有文字
        full_text = title.replace('\n', '')
        
        # 智能分词：将英文单词作为整体
        tokens = []
        current_word = ''
        for char in full_text:
            if char.isascii() and char.isalpha():
                current_word += char
            else:
                if current_word:
                    tokens.append(current_word)
                    current_word = ''
                if char.strip():  # 非空白字符
                    tokens.append(char)
        if current_word:
            tokens.append(current_word)
        
        # 按行分配
        lines = []
        current_line = ''
        current_len = 0
        
        for token in tokens:
            token_len = len(token) if not token.isascii() else len(token)
            
            if current_len + token_len <= max_chars_per_line:
                current_line += token
                current_len += token_len
            else:
                if current_line:
                    lines.append(current_line)
                current_line = token
                current_len = token_len
                
                if len(lines) >= max_lines - 1:
                    # 最后一行放剩余所有内容
                    break
        
        if current_line:
            lines.append(current_line)
        
        # 如果还有剩余 token，追加到最后一行
        remaining_idx = sum(len(l.replace(' ', '')) for l in lines)
        remaining = ''.join(tokens)[remaining_idx:]
        if remaining and lines:
            lines[-1] += remaining
        
        return '\n'.join(lines[:max_lines])
    
    # ================== 4. 发布模块 ==================
    async def publish(self, headless=False, auto_publish=True):
        """发布到小红书"""
        if not self.image_paths:
            self.logger.log("❌ 没有图片可发布")
            return False
        
        self.logger.log("🚀 启动发布流程...")
        self.update_progress(80)
        
        title = self.ai_data.get('caption_title', '未命名')
        content = self.ai_data['content_body'].replace("## ", "").replace("**", "")
        
        async with async_playwright() as p:
            # 云端模式强制使用 headless
            actual_headless = headless and auto_publish
            
            # 使用标准浏览器上下文 (兼容 GitHub Actions)
            browser = await p.chromium.launch(
                headless=actual_headless,
                args=["--disable-blink-features=AutomationControlled", "--disable-notifications"]
            )
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800}
            )
            
            # --- Cookie 注入逻辑 (GitHub Actions 专用) ---
            xhs_cookie_str = self.config.get("xhs_cookie")
            if xhs_cookie_str:
                self.logger.log("🍪 检测到 Cookie 配置，正在注入...")
                # 解析 Cookie 字符串 (name=value; name2=value2)
                cookies = []
                try:
                    for item in xhs_cookie_str.split(';'):
                        if '=' in item:
                            name, value = item.strip().split('=', 1)
                            cookies.append({
                                "name": name,
                                "value": value,
                                "domain": ".xiaohongshu.com",
                                "path": "/"
                            })
                    await context.add_cookies(cookies)
                    self.logger.log(f"✅ 成功注入 {len(cookies)} 个 Cookie")
                except Exception as e:
                     self.logger.log(f"⚠️ Cookie 注入失败: {e}")
            # -------------------------------------------

            page = await context.new_page()
            
            try:
                # 访问发布页
                self.logger.log("🌐 前往小红书创作中心...")
                await page.goto("https://creator.xiaohongshu.com/publish/publish", timeout=60000)
                
                # 登录检测
                try:
                    await page.wait_for_selector(".creator-container", timeout=15000)
                except:
                    self.logger.log("⚠️ 需要登录，请扫码...")
                    await self.logger.save_screenshot(page, "need_login")
                    await page.wait_for_url("**/publish/publish**", timeout=120000)
                
                await page.wait_for_timeout(3000)
                await page.keyboard.press("Escape")
                
                # 切换图文模式
                self.logger.log("🔄 切换图文模式...")
                await page.evaluate("""() => {
                    const allElements = document.querySelectorAll('*');
                    for (const el of allElements) {
                        if (el.innerText && el.innerText.trim() === '上传图文' && el.offsetParent !== null) {
                            el.click();
                            if(el.parentElement) el.parentElement.click();
                        }
                    }
                }""")
                await page.wait_for_timeout(2000)
                
                # 上传图片
                self.logger.log(f"📤 上传 {len(self.image_paths)} 张图片...")
                try:
                    async with page.expect_file_chooser(timeout=10000) as fc_info:
                        buttons = await page.locator("div, button, span").filter(has_text="上传图片").all()
                        for btn in buttons:
                            if await btn.is_visible():
                                await btn.click()
                                break
                    file_chooser = await fc_info.value
                    await file_chooser.set_files(self.image_paths)
                    self.logger.log("✅ 图片上传成功")
                except Exception as e:
                    self.logger.log(f"⚠️ 图片上传异常: {e}")
                
                await page.wait_for_timeout(8000)
                
                # 填写标题
                self.logger.log("✍️ 填写标题...")
                try:
                    await page.locator("input[placeholder*='标题']").first.fill(title)
                except:
                    await page.locator("input.el-input__inner").first.fill(title)
                
                # 填写正文
                self.logger.log("✍️ 填写正文...")
                editor = page.locator(".ProseMirror")
                if await editor.count() > 0:
                    await editor.click()
                    await page.keyboard.type(content, delay=30)
                
                # 自动选择推荐标签
                self.logger.log("🏷️ 自动选择标签...")
                await page.wait_for_timeout(2000)
                try:
                    for i in range(5):  # 点击5个标签
                        # 定位第一个可见的 # 开头的标签
                        tag_selector = ".tag-group > span.tag"
                        tags = page.locator(tag_selector)
                        count = await tags.count()
                        
                        if count > 0:
                            first_tag = tags.first
                            if await first_tag.is_visible():
                                text = await first_tag.inner_text()
                                if text.startswith('#') and '展开' not in text:
                                    self.logger.log(f"   👉 选择: {text}")
                                    await first_tag.click()
                                    await page.wait_for_timeout(1500)  # 等待列表刷新
                except Exception as e:
                    self.logger.log(f"⚠️ 标签选择异常: {e}")
                
                self.update_progress(90)
                
                # 发布或手动
                if auto_publish:
                    self.logger.log("🚀 点击发布...")
                    await page.wait_for_timeout(3000)
                    
                    # 尝试多种选择器查找发布按钮
                    btn = None
                    selectors = [
                        "button.publishBtn",
                        "button:has-text('发布')",
                        ".publish-btn",
                        "button.css-1gl8z4q",  # 备用类名
                        "[class*='publish']"
                    ]
                    
                    for sel in selectors:
                        try:
                            candidate = page.locator(sel).first
                            if await candidate.count() > 0 and await candidate.is_visible(timeout=3000):
                                btn = candidate
                                self.logger.log(f"✅ 找到发布按钮: {sel}")
                                break
                        except:
                            continue
                    
                    if btn is None:
                        self.logger.log("❌ 找不到发布按钮")
                        await self.logger.save_screenshot(page, "no_publish_btn")
                        return False
                    
                    try:
                        await btn.click(timeout=10000)
                        self.logger.log("✅ 发布指令已发送！")
                        await page.wait_for_timeout(5000)
                        self.update_progress(100)
                        return True
                    except Exception as e:
                        self.logger.log(f"❌ 点击发布按钮失败: {e}")
                        await self.logger.save_screenshot(page, "publish_click_error")
                        return False
                else:
                    self.logger.log("⏸️ 手动发布模式：请检查内容后手动点击发布")
                    self.update_progress(95)
                    # 等待用户操作
                    await page.wait_for_timeout(600000)  # 10分钟
                    return True
                    
            except Exception as e:
                self.logger.log(f"❌ 发布出错: {e}")
                await self.logger.save_screenshot(page, "publish_error")
                return False
            finally:
                if auto_publish:
                    await page.wait_for_timeout(5000)
                    await context.close()
                    await browser.close()
    
    # ================== 5. 归档模块 ==================
    def archive(self):
        """归档所有内容"""
        if not self.scraped_data or not self.ai_data:
            return None
        
        self.logger.log("📦 正在归档...")
        
        # 创建归档目录
        date_str = datetime.now().strftime("%Y-%m-%d")
        title = self.ai_data.get('caption_title', '未命名')[:20]
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)
        self.archive_dir = os.path.join(ARCHIVES_DIR, f"{date_str}_{safe_title}")
        
        if os.path.exists(self.archive_dir):
            shutil.rmtree(self.archive_dir)
        os.makedirs(self.archive_dir)
        
        # 保存原文
        with open(os.path.join(self.archive_dir, "原文.txt"), 'w', encoding='utf-8') as f:
            f.write(f"URL: {self.scraped_data['url']}\n")
            f.write(f"标题: {self.scraped_data['title']}\n\n")
            f.write(self.scraped_data['full_text'])
        
        # 保存 AI 生成结果
        with open(os.path.join(self.archive_dir, "AI生成.json"), 'w', encoding='utf-8') as f:
            json.dump(self.ai_data, f, ensure_ascii=False, indent=2)
        
        # 保存配置
        config_snapshot = {
            "api_key": self.config.get_current_api_key()[:10] + "...",
            "model": self.config.get_current_model(),
            "silent_mode": self.config.is_silent_mode(),
            "auto_publish": self.config.is_auto_publish()
        }
        with open(os.path.join(self.archive_dir, "配置.json"), 'w', encoding='utf-8') as f:
            json.dump(config_snapshot, f, ensure_ascii=False, indent=2)
        
        # 复制图片
        images_dir = os.path.join(self.archive_dir, "images")
        os.makedirs(images_dir)
        for img_path in self.image_paths:
            if os.path.exists(img_path):
                shutil.copy(img_path, images_dir)
        
        self.logger.log(f"✅ 归档完成: {self.archive_dir}")
        return self.archive_dir
    
    # ================== 完整流程 ==================
    async def run_full_pipeline(self, url, prompt_template, cloud_mode=False):
        """执行完整发布流程
        
        Args:
            url: 文章链接
            prompt_template: AI 提示词模板
            cloud_mode: 是否为云端模式 (GitHub Actions)，云端模式使用轻量抓取 + Cookie发布
        """
        self.update_progress(0)
        
        # 1. 抓取 (云端用轻量模式)
        if cloud_mode:
            self.logger.log("☁️ 云端模式：使用轻量级 HTTP 抓取")
            result = await self.scrape_lightweight(url)
        else:
            headless = self.config.is_silent_mode()
            result = await self.scrape(url, headless=headless)
        
        if not result:
            return False
        
        # 2. AI 生成
        result = self.generate_content(prompt_template)
        if not result:
            return False
        
        # 3. 渲染
        result = self.render_images()
        if not result:
            return False
        
        # 4. 发布 (云端模式也发布，使用 Cookie 认证)
        if cloud_mode:
            self.logger.log("☁️ 云端模式：使用 Cookie 认证发布")
            # 云端强制 headless + 自动发布
            success = await self.publish(headless=True, auto_publish=True)
        else:
            headless = self.config.is_silent_mode()
            auto_publish = self.config.is_auto_publish()
            success = await self.publish(headless=headless, auto_publish=auto_publish)
        
        # 5. 归档
        self.archive()
        
        return success
