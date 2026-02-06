# tests/test_templates.py
# 小红书发布工具单元测试

import os
import sys
import pytest
import json

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "core"))

from core.xhs_core import XHSGenerator, STYLES, find_font, FONT_PATH_REGULAR


class TestTemplates:
    """测试模板配置"""
    
    def test_all_templates_exist(self):
        """测试所有模板都有配置"""
        required_templates = ['breath', 'tech_card', 'cyber', 'magazine', 'notion', 'sticky', 'ticket']
        for template in required_templates:
            assert template in STYLES, f"模板 {template} 不存在于 STYLES 中"
    
    def test_template_has_required_fields(self):
        """测试每个模板都有必需字段"""
        required_fields = ['BG_COLOR', 'CARD_COLOR', 'TEXT_MAIN', 'ACCENT_COLOR', 'type']
        for name, style in STYLES.items():
            for field in required_fields:
                assert field in style, f"模板 {name} 缺少字段 {field}"
    
    def test_color_format(self):
        """测试颜色格式正确 (HEX)"""
        import re
        hex_pattern = re.compile(r'^#[0-9A-Fa-f]{6}$')
        for name, style in STYLES.items():
            for key in ['BG_COLOR', 'CARD_COLOR', 'TEXT_MAIN', 'ACCENT_COLOR']:
                color = style.get(key)
                if color:  # 有些可能是 None
                    assert hex_pattern.match(color), f"模板 {name} 的 {key} 颜色格式错误: {color}"


class TestFonts:
    """测试字体加载"""
    
    def test_font_path_found(self):
        """测试能找到中文字体"""
        assert FONT_PATH_REGULAR is not None, "找不到任何中文字体文件"
    
    def test_font_file_exists(self):
        """测试字体文件存在"""
        if FONT_PATH_REGULAR:
            assert os.path.exists(FONT_PATH_REGULAR), f"字体文件不存在: {FONT_PATH_REGULAR}"


class TestRendering:
    """测试图片渲染"""
    
    @pytest.fixture
    def generator(self, tmp_path):
        """创建测试用生成器"""
        return XHSGenerator(
            template_name="breath",
            header_text="测试头部",
            footer_text="测试尾部",
            output_dir=str(tmp_path)
        )
    
    def test_cover_generation(self, generator, tmp_path):
        """测试封面生成"""
        cover_path = generator.generate_cover("标题测试\n第二行")
        assert cover_path is not None
        assert os.path.exists(cover_path)
        assert cover_path.endswith('.png')
    
    def test_body_generation(self, generator, tmp_path):
        """测试正文页生成"""
        body_content = """## 测试标题
        
这是一段测试正文内容。用于验证渲染功能是否正常工作。

## 第二个标题

更多内容在这里。带有一些 emoji 🎉 和中文标点符号。
"""
        pages = generator.generate_body(body_content)
        assert pages is not None
        assert len(pages) >= 1
        for page in pages:
            assert os.path.exists(page)
    
    def test_all_templates_render(self, tmp_path):
        """测试所有模板都能渲染"""
        for template_name in ['breath', 'tech_card', 'notion']:
            gen = XHSGenerator(
                template_name=template_name,
                header_text="测试",
                footer_text="测试",
                output_dir=str(tmp_path / template_name)
            )
            cover = gen.generate_cover("模板测试")
            assert cover is not None, f"模板 {template_name} 封面渲染失败"


class TestPrompts:
    """测试提示词配置"""
    
    @pytest.fixture
    def prompts_path(self):
        return os.path.join(PROJECT_ROOT, "core", "prompts.json")
    
    def test_prompts_file_exists(self, prompts_path):
        """测试提示词文件存在"""
        assert os.path.exists(prompts_path), "prompts.json 不存在"
    
    def test_prompts_valid_json(self, prompts_path):
        """测试提示词是有效 JSON"""
        with open(prompts_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert "templates" in data, "prompts.json 缺少 templates 字段"
    
    def test_prompts_have_required_fields(self, prompts_path):
        """测试每个提示词模板都有必需字段"""
        with open(prompts_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for template in data["templates"]:
            assert "name" in template, "提示词模板缺少 name"
            assert "prompt" in template, "提示词模板缺少 prompt"
    
    def test_prompts_contain_placeholders(self, prompts_path):
        """测试提示词包含必要占位符"""
        with open(prompts_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for template in data["templates"]:
            prompt = template["prompt"]
            assert "{url}" in prompt, f"提示词 {template['name']} 缺少 {{url}} 占位符"
            assert "{full_text}" in prompt, f"提示词 {template['name']} 缺少 {{full_text}} 占位符"


class TestConfig:
    """测试配置管理"""
    
    def test_available_models(self):
        """测试可用模型列表"""
        from config import AVAILABLE_MODELS
        assert "gemini-3-flash-preview" in AVAILABLE_MODELS
        assert len(AVAILABLE_MODELS) >= 3
    
    def test_available_templates(self):
        """测试可用模板列表"""
        from config import AVAILABLE_TEMPLATES
        template_names = [t[0] for t in AVAILABLE_TEMPLATES]
        assert "breath" in template_names
        assert "tech_card" in template_names


class TestPipelineIntegration:
    """测试发布流水线集成"""
    
    def test_pipeline_init(self):
        """测试流水线初始化"""
        from core.pipeline import PublishPipeline, Logger
        from core.config_manager import ConfigManager
        
        config = ConfigManager()
        logger = Logger()
        pipeline = PublishPipeline(config_manager=config, logger=logger)
        
        assert pipeline is not None
        assert pipeline.scraped_data is None
        assert pipeline.ai_data is None
    
    def test_logger_works(self, tmp_path):
        """测试日志记录"""
        from core.pipeline import Logger
        
        messages = []
        logger = Logger(callback=lambda msg: messages.append(msg))
        logger.log("测试消息")
        
        assert len(messages) == 1
        assert "测试消息" in messages[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
