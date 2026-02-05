"""
小红书一键发布工具 v2 - 主程序
现代化 Material Design 界面
"""
import flet as ft
import asyncio
import threading
import os
import sys
import json
import base64
from config import config, AVAILABLE_MODELS, AVAILABLE_TEMPLATES, PROMPT_STYLES

# 导入核心模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "core"))
from pipeline import PublishPipeline, Logger, ConfigManager as PipelineConfig

class XHSPublisherApp:
    """主应用类"""
    
    def __init__(self, page: ft.Page):
        self.page = page
        self.pipeline = None
        self.pipeline_config = PipelineConfig() # 适配 pipeline 的 config manager
        self.setup_page()
        self.build_ui()
        
        # 加载配置到 pipeline config
        self.sync_config()
    
    def sync_config(self):
        """同步配置到 pipeline"""
        pass

    def close_dialog(self, dialog):
        dialog.open = False
        self.page.update()

    def setup_page(self):
        """页面初始化设置"""
        self.page.title = "小红书一键发布 v2"
        self.page.window.width = 500
        self.page.window.height = 800
        self.page.window.resizable = True
        self.page.window_min_width = 400
        self.page.window_min_height = 600
        
        # 深色主题
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.theme = ft.Theme(
            color_scheme_seed=ft.Colors.CYAN,
            visual_density=ft.VisualDensity.COMFORTABLE,
        )
        self.page.bgcolor = "#0a0a0f"
    
    def build_ui(self):
        """构建主界面"""
        # 顶部标题栏
        title_bar = ft.Container(
            content=ft.Row(
                [
                    ft.Row([
                        ft.Icon(ft.Icons.AUTO_AWESOME, color=ft.Colors.CYAN_400, size=28),
                        ft.Text("小红书一键发布", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    ], spacing=10),
                    ft.IconButton(
                        icon=ft.Icons.SETTINGS,
                        icon_color=ft.Colors.WHITE54,
                        on_click=self.open_settings,
                        tooltip="设置",
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=ft.padding.symmetric(horizontal=20, vertical=15),
        )
        
        # 链接输入区
        self.url_input = ft.TextField(
            label="输入文章链接",
            hint_text="粘贴微信公众号文章链接...",
            prefix_icon=ft.Icons.LINK,
            border_radius=12,
            filled=True,
            bgcolor="#1a1a2e",
            border_color=ft.Colors.TRANSPARENT,
            focused_border_color=ft.Colors.CYAN_400,
            text_style=ft.TextStyle(color=ft.Colors.WHITE),
            label_style=ft.TextStyle(color=ft.Colors.WHITE54),
        )
        
        # 快速配置区
        self.template_dropdown = ft.Dropdown(
            label="封面模板",
            value=config.get("template", "tech_card"),
            options=[ft.dropdown.Option(key=k, text=v) for k, v in AVAILABLE_TEMPLATES],
            border_radius=12,
            filled=True,
            bgcolor="#1a1a2e",
            border_color=ft.Colors.TRANSPARENT,
            focused_border_color=ft.Colors.CYAN_400,
            text_style=ft.TextStyle(color=ft.Colors.WHITE),
            label_style=ft.TextStyle(color=ft.Colors.WHITE54),
            expand=True,
        )
        self.template_dropdown.on_change = self.on_template_change
        
        self.style_dropdown = ft.Dropdown(
            label="写作风格",
            value=config.get("prompt_style", "深度科技主笔"),
            options=[ft.dropdown.Option(key=k, text=k) for k, v in PROMPT_STYLES],
            border_radius=12,
            filled=True,
            bgcolor="#1a1a2e",
            border_color=ft.Colors.TRANSPARENT,
            focused_border_color=ft.Colors.CYAN_400,
            text_style=ft.TextStyle(color=ft.Colors.WHITE),
            label_style=ft.TextStyle(color=ft.Colors.WHITE54),
            expand=True,
        )
        self.style_dropdown.on_change = self.on_style_change
        
        config_row = ft.Row(
            [self.template_dropdown, self.style_dropdown],
            spacing=15,
        )
        
        # 主按钮
        self.generate_btn = ft.ElevatedButton(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ROCKET_LAUNCH, size=20),
                    ft.Text("一键生成", size=16, weight=ft.FontWeight.W_600),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
            style=ft.ButtonStyle(
                bgcolor={
                    ft.ControlState.DEFAULT: ft.Colors.CYAN_700,
                    ft.ControlState.HOVERED: ft.Colors.CYAN_600,
                    ft.ControlState.DISABLED: ft.Colors.GREY_800,
                },
                color={
                    ft.ControlState.DEFAULT: ft.Colors.WHITE,
                    ft.ControlState.DISABLED: ft.Colors.WHITE24,
                },
                padding=ft.padding.symmetric(horizontal=30, vertical=18),
                shape=ft.RoundedRectangleBorder(radius=14),
                elevation={"": 4, "hovered": 8},
            ),
            on_click=self.on_generate,
        )

        # 发布按钮 (移至主界面)
        self.publish_btn = ft.ElevatedButton(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.SEND_ROUNDED, size=20),
                    ft.Text("发布到小红书", size=16, weight=ft.FontWeight.W_600),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
            style=ft.ButtonStyle(
                bgcolor={
                    ft.ControlState.DEFAULT: ft.Colors.GREEN_700,
                    ft.ControlState.HOVERED: ft.Colors.GREEN_600,
                    ft.ControlState.DISABLED: ft.Colors.GREY_800,
                },
                color={
                    ft.ControlState.DEFAULT: ft.Colors.WHITE,
                    ft.ControlState.DISABLED: ft.Colors.WHITE24,
                },
                padding=ft.padding.symmetric(horizontal=30, vertical=18),
                shape=ft.RoundedRectangleBorder(radius=14),
                elevation={"": 4, "hovered": 8},
            ),
            on_click=self.on_publish,
            visible=False, # 初始隐藏
        )
        
        # 进度条
        self.progress_bar = ft.ProgressBar(
            width=400,
            color=ft.Colors.CYAN_400,
            bgcolor=ft.Colors.GREY_900,
            value=0,
            visible=False,
        )

        # 状态指示器
        self.status_text = ft.Text(
            "准备就绪",
            size=13,
            color=ft.Colors.WHITE54,
            text_align=ft.TextAlign.CENTER,
        )
        
        # 日志输出区域（可折叠）
        self.log_view = ft.ListView(
            expand=True,
            spacing=5,
            padding=10,
            auto_scroll=True,
            height=150,
        )
        self.log_container = ft.Container(
            content=self.log_view,
            bgcolor="#12121a",
            border_radius=10,
            padding=10,
            visible=False, # 默认隐藏
            height=150, 
        )

        
        # 高级编辑展开面板
        self.advanced_panel = ft.ExpansionPanelList(
            expand_icon_color=ft.Colors.CYAN_400,
            elevation=0,
            divider_color=ft.Colors.TRANSPARENT,
            controls=[
                ft.ExpansionPanel(
                    header=ft.ListTile(
                        leading=ft.Icon(ft.Icons.EDIT_NOTE, color=ft.Colors.CYAN_400),
                        title=ft.Text("高级编辑", color=ft.Colors.WHITE70),
                        subtitle=ft.Text("编辑标题和正文内容", color=ft.Colors.WHITE38, size=12),
                    ),
                    content=self.build_editor_panel(),
                    bgcolor="#12121a",
                    can_tap_header=True,
                )
            ],
        )
        
        # 预览区域
        self.preview_image = ft.Image(
            src="",
            width=200,
            height=200,
            fit="contain",
            visible=False,
            border_radius=10,
        )
        self.preview_grid = ft.Row(
            wrap=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=10,
            run_spacing=10,
        )
        
        self.preview_container = ft.Container(
            content=ft.Column([
                ft.Text("生成预览", size=14, color=ft.Colors.WHITE54),
                self.preview_grid,
                ft.Container(
                    content=ft.Text("暂无内容，请点击'一键生成'", color=ft.Colors.WHITE38, size=13),
                    visible=True,
                    padding=20,
                    alignment=ft.Alignment(0, 0),
                ) if not self.preview_grid.controls else ft.Container(),
            ]),
            visible=True,
        )
        
        # 动作按钮区 (发布)
        self.action_area = ft.Container(
            content=self.publish_btn,
            alignment=ft.Alignment(0, 0),
            visible=False, # 初始隐藏
        )
        
        # 主内容区
        main_content = ft.Container(
            content=ft.Column(
                [
                    self.url_input,
                    ft.Container(height=15),
                    config_row,
                    ft.Container(height=20),
                    ft.Container(
                        content=self.generate_btn,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Container(height=10),
                    self.progress_bar,
                    self.status_text,
                    ft.Container(height=10),
                    self.log_container,
                    ft.Divider(color="#2a2a3e", height=1),
                    self.advanced_panel,
                    ft.Container(height=15),
                    self.preview_container,
                    ft.Container(height=10),
                    self.action_area,
                ],
                spacing=5,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=ft.padding.symmetric(horizontal=20, vertical=10),
            expand=True,
        )
        
        # 组装页面
        self.page.add(
            ft.Column(
                [title_bar, main_content],
                spacing=0,
                expand=True,
            )
        )
    
    def build_editor_panel(self) -> ft.Container:
        """构建高级编辑面板"""
        self.title_editor = ft.TextField(
            label="封面标题",
            hint_text="每行用换行分隔...",
            multiline=True,
            min_lines=2,
            max_lines=3,
            border_radius=10,
            filled=True,
            bgcolor="#1a1a2e",
            border_color=ft.Colors.TRANSPARENT,
            text_style=ft.TextStyle(color=ft.Colors.WHITE),
        )
        
        self.content_editor = ft.TextField(
            label="正文内容",
            hint_text="Markdown 格式正文...",
            multiline=True,
            min_lines=6,
            max_lines=12,
            border_radius=10,
            filled=True,
            bgcolor="#1a1a2e",
            border_color=ft.Colors.TRANSPARENT,
            text_style=ft.TextStyle(color=ft.Colors.WHITE, size=13),
        )
        
        return ft.Container(
            content=ft.Column([
                self.title_editor,
                ft.Container(height=10),
                self.content_editor,
                ft.Container(height=15),
                ft.Row([
                    ft.OutlinedButton(
                        "重新生成",
                        icon=ft.Icons.REFRESH,
                        style=ft.ButtonStyle(
                            color=ft.Colors.CYAN_400,
                            side=ft.BorderSide(1, ft.Colors.CYAN_400),
                        ),
                        on_click=self.on_regenerate,
                    ),

                ], alignment=ft.MainAxisAlignment.END, spacing=15),
            ]),
            padding=ft.padding.only(left=15, right=15, bottom=15),
        )
    
    def open_settings(self, e):
        """打开设置对话框"""
        api_key_field = ft.TextField(
            label="Gemini API Key",
            value=config.get("api_key", ""),
            password=True,
            can_reveal_password=True,
            border_radius=10,
            filled=True,
            bgcolor="#1a1a2e",
            text_style=ft.TextStyle(color=ft.Colors.WHITE),
        )
        
        model_dropdown = ft.Dropdown(
            label="AI 模型",
            value=config.get("model", "gemini-2.5-flash"),
            options=[ft.dropdown.Option(m) for m in AVAILABLE_MODELS],
            border_radius=10,
            filled=True,
            bgcolor="#1a1a2e",
            text_style=ft.TextStyle(color=ft.Colors.WHITE),
        )

        # 运行模式配置
        mode_dropdown = ft.Dropdown(
            label="运行模式",
            value=config.get("execution_mode", "manual"),
            options=[
                ft.dropdown.Option("manual", "手动确认 (推荐)"),
                ft.dropdown.Option("auto", "全自动直发"),
            ],
            border_radius=10,
            filled=True,
            bgcolor="#1a1a2e",
            text_style=ft.TextStyle(color=ft.Colors.WHITE),
        )

        silent_publish = ft.Switch(
            label="静默发布 (隐藏浏览器, 仅自动模式有效)",
            value=config.get("silent_publish", False),
            active_color=ft.Colors.CYAN_400,
        )
        
        proxy_enabled = ft.Checkbox(
            label="启用代理",
            value=config.get("proxy", {}).get("enabled", False),
            active_color=ft.Colors.CYAN_400,
        )
        
        proxy_field = ft.TextField(
            label="HTTP 代理地址",
            value=config.get("proxy", {}).get("http", ""),
            hint_text="http://127.0.0.1:7890",
            border_radius=10,
            filled=True,
            bgcolor="#1a1a2e",
            text_style=ft.TextStyle(color=ft.Colors.WHITE),
        )
        
        def save_settings(e):
            config.set("api_key", api_key_field.value)
            config.set("model", model_dropdown.value)
            config.set("execution_mode", mode_dropdown.value)
            config.set("silent_publish", silent_publish.value)
            config.set("proxy", {
                "enabled": proxy_enabled.value,
                "http": proxy_field.value,
                "https": proxy_field.value,
            })
            dialog.open = False
            self.page.update()
            self.show_snackbar("设置已保存", ft.Colors.GREEN_400)
            
            # 更新环境变量
            if config.get("proxy", {}).get("enabled"):
                os.environ["HTTP_PROXY"] = proxy_field.value
                os.environ["HTTPS_PROXY"] = proxy_field.value
            else:
                os.environ.pop("HTTP_PROXY", None)
                os.environ.pop("HTTPS_PROXY", None)
        
        dialog = ft.AlertDialog(
            title=ft.Text("设置", color=ft.Colors.WHITE),
            bgcolor="#12121a",
            content=ft.Container(
                content=ft.Column([
                    ft.Text("🔑 API 配置", size=14, color=ft.Colors.CYAN_400),
                    api_key_field,
                    model_dropdown,

                    ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                    ft.Text("⚙️ 运行配置", size=14, color=ft.Colors.CYAN_400),
                    mode_dropdown,
                    silent_publish,
                    ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                    ft.Text("🌐 网络代理", size=14, color=ft.Colors.CYAN_400),
                    proxy_enabled,
                    proxy_field,
                ], spacing=12, tight=True),
                width=350,
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda e: self.close_dialog(dialog)),
                ft.ElevatedButton(
                    "保存",
                    style=ft.ButtonStyle(bgcolor=ft.Colors.CYAN_700, color=ft.Colors.WHITE),
                    on_click=save_settings,
                ),
            ],
        )
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def on_template_change(self, e):
        print(f"DEBUG: On Template Change: {e.control.value}")
        config.set("template", e.control.value)
    
    def on_style_change(self, e):
        config.set("prompt_style", e.control.value)
    
    def log_callback(self, msg):
        """日志回调"""
        self.log_view.controls.append(ft.Text(msg, size=12, color=ft.Colors.WHITE70, font_family="Consolas"))
        self.log_view.scroll_to(offset=-1, duration=200)
        self.page.update()

    def progress_callback(self, value):
        """进度回调"""
        self.progress_bar.value = value / 100.0
        self.page.update()

    def on_generate(self, e):
        """一键生成"""
        url = self.url_input.value.strip()
        if not url:
            self.show_snackbar("请输入文章链接", ft.Colors.RED_400)
            return
        
        if not config.get("api_key"):
            self.show_snackbar("请先在设置中配置 API Key", ft.Colors.ORANGE_400)
            self.open_settings(None)
            return
        
        # UI 状态重置
        self.status_text.value = "🚀 正在初始化..."
        self.status_text.color = ft.Colors.CYAN_400
        self.status_text.color = ft.Colors.CYAN_400
        self.generate_btn.disabled = True
        self.publish_btn.visible = False # 重新生成时隐藏发布按钮
        self.action_area.visible = False
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.log_container.visible = True
        self.log_view.controls.clear()
        self.preview_grid.controls.clear() 
        self.page.update()
        
        # 准备 Pipeline 配置适配器
        class AdapterConfig:
             def get_current_api_key(self): return config.get("api_key")
             def get_current_model(self): return config.get("model")
             def is_silent_mode(self): return True # GUI 默认静默抓取
             def is_auto_publish(self): return False
        
        logger = Logger(callback=self.log_callback)
        self.pipeline = PublishPipeline(config_manager=AdapterConfig(), logger=logger)

        # 强制同步 UI 状态到 pipeline (避免 on_change 未触发)
        ui_template = self.template_dropdown.value
        print(f"DEBUG: UI Dropdown Value: {ui_template}")
        if ui_template:
            self.pipeline.image_template = ui_template
            config.set("template", ui_template)
        else:
            self.pipeline.image_template = config.get("template")

        self.pipeline.set_progress_callback(self.progress_callback)
        # self.pipeline.image_template 已经在上面设置了

        # 获取 Prompt 模板 (硬编码演示，实际应读取文件)
        prompt_style_name = self.style_dropdown.value # 同样从UI读取风格
        if prompt_style_name:
             config.set("prompt_style", prompt_style_name)
        else:
             prompt_style_name = config.get("prompt_style")

        prompt_template = ""
        try:
             import json
             # 尝试在多个位置查找 prompts.json
             paths_to_check = [
                 os.path.join(os.path.dirname(__file__), "core", "prompts.json"), # 新位置
                 os.path.join(os.path.dirname(__file__), "..", "微信推文链接直发小红书笔记脚本20260129", "一键发布工具", "prompts.json") # 旧位置
             ]
             
             for path in paths_to_check:
                 if os.path.exists(path):
                     with open(path, "r", encoding="utf-8") as f:
                         data = json.load(f)
                         for t in data["templates"]:
                             if t["name"] == prompt_style_name:
                                 prompt_template = t["prompt"]
                                 break
                         if prompt_template: break
             
             if not prompt_template and data:
                  prompt_template = data["templates"][0]["prompt"]
                  
        except Exception as e:
            self.log_callback(f"⚠️ 读取 Prompt 失败: {e}")
            prompt_template = """
- Role: Deep Tech Columnist
- Goal: 将提供的素材改写为一篇小红书爆款图文。
- Output Format (JSON Only): {'cover_title': '', 'content_body': '', 'caption_title': ''}
【素材来源】{url}
【素材内容】{full_text}
            """

        if not prompt_template:
            self.show_snackbar("未找到 Prompt 模板", ft.Colors.RED_400)
            self.status_text.value = "❌ 错误: 未找到Prompt模板"
            self.generate_btn.disabled = False
            return

        # 异步运行
        def run_thread():
            asyncio.run(self._run_async_pipeline(url, prompt_template))
        
        threading.Thread(target=run_thread, daemon=True).start()

    async def _run_async_pipeline(self, url, prompt_template):
        try:
            # 1. 抓取
            scrape_data = await self.pipeline.scrape(url, headless=True)
            if not scrape_data: raise Exception("抓取失败")
            
            # 2. AI 生成
            ai_data = self.pipeline.generate_content(prompt_template)
            if not ai_data: raise Exception("AI 生成失败")
            
            # 更新编辑器内容 (回到主线程)
            self.title_editor.value = ai_data.get("cover_title", "")
            self.content_editor.value = ai_data.get("content_body", "")
            self.page.update()

            # 3. 渲染
            img_paths = self.pipeline.render_images()
            if not img_paths: raise Exception("渲染失败")
            
            # 显示预览图
            # 使用 base64 避免文件缓存问题
            base64_images = [self._get_image_base64(p) for p in img_paths]
            
            self.preview_grid.controls.clear()
            for b64 in base64_images:
                self.preview_grid.controls.append(
                   ft.Image(src=f"data:image/png;base64,{b64}", width=150, height=200, fit="contain", border_radius=8)
                )
            
            # 4. 完成
            # 4. 完成
            self.status_text.value = "✅ 生成完成！"
            self.status_text.color = ft.Colors.GREEN_400
            self.progress_bar.value = 1.0

            # 检查运行模式
            mode = config.get("execution_mode", "manual")
            if mode == "auto":
                self.status_text.value = "🚀 正在自动发布..."
                self.page.update()
                # 自动发布
                silent = config.get("silent_publish", False)
                await self._run_async_publish(headless=silent, auto_publish=True)
            else:
                # 手动模式：显示发布按钮
                self.publish_btn.visible = True
                self.action_area.visible = True
                self.publish_btn.disabled = False
                self.page.update()
            
            
        except Exception as e:
            self.status_text.value = f"❌ 错误: {str(e)}"
            self.status_text.color = ft.Colors.RED_400
        finally:
            self.generate_btn.disabled = False
            self.page.update()

    def _get_image_base64(self, path):
        """读取图片并转换为 base64"""
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def on_regenerate(self, e):
        """重新生成 (只重新渲染)"""
        print("DEBUG: on_regenerate triggered")
        if not self.pipeline:
            print("DEBUG: self.pipeline is None")
            self.show_snackbar("Pipeline 未初始化", ft.Colors.RED_400)
            return

        if not self.pipeline.ai_data:
             print("DEBUG: self.pipeline.ai_data is None")
             self.show_snackbar("请先进行一次生成", ft.Colors.ORANGE_400)
             return
        
        print("DEBUG: Updating AI data from editors")
        # 更新 AI 数据
        self.pipeline.ai_data["cover_title"] = self.title_editor.value
        self.pipeline.ai_data["content_body"] = self.content_editor.value
        self.pipeline.image_template = config.get("template")
        print(f"DEBUG: Template set to {self.pipeline.image_template}")

        self.status_text.value = "🎨 正在重新渲染..."
        self.status_text.color = ft.Colors.CYAN_400
        self.page.update()
        
        def run_regenerate():
            print("DEBUG: Thread started")
            try:
                img_paths = self.pipeline.render_images()
                print(f"DEBUG: Render finished, paths: {img_paths}")
                if not img_paths: raise Exception("渲染返回为空")

                # 回到主线程更新UI
                # 使用 base64 避免文件缓存问题
                base64_images = [self._get_image_base64(p) for p in img_paths]
                
                self.preview_grid.controls.clear()
                for b64 in base64_images:
                    self.preview_grid.controls.append(
                        ft.Image(src=f"data:image/png;base64,{b64}", width=150, height=200, fit="contain", border_radius=8)
                    )
                self.status_text.value = "✅ 重新渲染完成"
                self.status_text.color = ft.Colors.GREEN_400
                self.page.update()
                print("DEBUG: UI updated")
            except Exception as ex:
                print(f"DEBUG: Exception in thread: {ex}")
                self.status_text.value = f"❌ 渲染失败: {str(ex)}"
                self.status_text.color = ft.Colors.RED_400
                self.page.update()
        
        threading.Thread(target=run_regenerate, daemon=True).start()
    
    def on_publish(self, e):
        """发布 (手动触发)"""
        # 检查是否开启静默发布
        silent = config.get("silent_publish", False)
        
        if silent:
            # 静默模式下，必须全自动，否则用户无法操作
            self.show_snackbar("🚀 静默发布中...", ft.Colors.CYAN_400)
            self._trigger_publish(headless=True, auto_publish=True)
        else:
            # 普通模式，显示浏览器，用户需手动确认
            self._trigger_publish(headless=False, auto_publish=False)

    def _trigger_publish(self, headless=False, auto_publish=False):
        # 检查模板是否一致，如果不一致则自动重新渲染
        current_template = config.get("template")
        if self.pipeline and self.pipeline.image_template != current_template:
            self.show_snackbar(f"检测到模板变更 ({self.pipeline.image_template} -> {current_template})，正在重新渲染...", ft.Colors.CYAN_400)
            self.page.update()
            try:
                self.pipeline.image_template = current_template
                img_paths = self.pipeline.render_images()
                if not img_paths: raise Exception("重新渲染失败")
                # 更新预览
                base64_images = [self._get_image_base64(p) for p in img_paths]
                self.preview_grid.controls.clear()
                for b64 in base64_images:
                     self.preview_grid.controls.append(
                        ft.Image(src=f"data:image/png;base64,{b64}", width=150, height=200, fit="contain", border_radius=8)
                     )
                self.page.update()
            except Exception as e:
                self.show_snackbar(f"自动渲染失败: {e}", ft.Colors.RED_400)
                return

        if not self.pipeline or not self.pipeline.image_paths:
             self.show_snackbar("没有可发布的内容", ft.Colors.ORANGE_400)
             return
        
        self.status_text.value = "🚀 正在发布..."
        self.generate_btn.disabled = True
        self.publish_btn.disabled = True
        self.page.update()

        def run_publish():
            asyncio.run(self._run_async_publish(headless, auto_publish))
        
        threading.Thread(target=run_publish, daemon=True).start()

    async def _run_async_publish(self, headless=False, auto_publish=False):
        try:
            success = await self.pipeline.publish(headless=headless, auto_publish=auto_publish)
            if success:
                self.status_text.value = "✅ 发布流程已结束"
            else:
                self.status_text.value = "❌ 发布失败"
        finally:
            self.generate_btn.disabled = False
            self.publish_btn.disabled = False
            self.page.update()
    
    def show_snackbar(self, message: str, color=ft.Colors.WHITE):
        """显示提示"""
        snackbar = ft.SnackBar(
            content=ft.Text(message, color=color),
            bgcolor="#2a2a3e",
        )
        self.page.overlay.append(snackbar)
        snackbar.open = True
        self.page.update()


def main(page: ft.Page):
    XHSPublisherApp(page)


if __name__ == "__main__":
    ft.app(target=main)
