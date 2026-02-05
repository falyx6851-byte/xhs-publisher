import sys
import asyncio
import os
import argparse
import json
from core.pipeline import PublishPipeline, Logger

# 模拟配置管理器 (优先从环境变量读取)
class EnvConfig:
    def __init__(self, args):
        self.args = args

    def get(self, key, default=None):
        # 优先读环境变量 (GitHub Secrets)
        if key == 'api_key': 
            return os.environ.get('GEMINI_API_KEY') or default
        if key == 'xhs_cookie': 
            return os.environ.get('XHS_COOKIE') or default
        if key == 'model':
            return self.args.model
        
        # 其次读命令行参数
        if key == 'template':
            return self.args.template
        if key == 'prompt_style':
            return "深度科技主笔" # 默认值
            
        # 默认回退
        return default

    def set(self, key, value):
        pass # 环境变量只读，不需要保存
    
    def is_silent_mode(self):
        """GitHub Actions 强制使用静默模式"""
        return True
    
    def is_auto_publish(self):
        """GitHub Actions 强制自动发布"""
        return True

async def main():
    # 1. 解析命令行参数
    parser = argparse.ArgumentParser(description='Xiaohongshu Publisher CLI Runner')
    parser.add_argument("url", help="WeChat Article URL")
    parser.add_argument("--template", default="breath", help="Cover template name (e.g., tech_card, breath)")
    parser.add_argument("--model", default="gemini-2.5-flash", help="AI Model name")
    args = parser.parse_args()

    print(f"🚀 [GitHub Runner] Starting Pipeline...")
    print(f"🔗 URL: {args.url}")
    print(f"🎨 Template: {args.template}")

    # 2. 检查关键环境变量
    if not os.environ.get('GEMINI_API_KEY'):
        print("❌ Error: GEMINI_API_KEY environment variable is missing.")
        sys.exit(1)
    
    if not os.environ.get('XHS_COOKIE'):
        print("⚠️ Warning: XHS_COOKIE is missing. Publishing might require login (not supported in headless).")

    # 3. 初始化管道
    # 定义简单的日志回调，直接输出到控制台
    logger = Logger(callback=lambda msg: print(f"[PIPELINE] {msg}"))
    
    # 创建环境变量配置
    env_config = EnvConfig(args)
    
    # 用正确的参数初始化 Pipeline
    pipeline = PublishPipeline(config_manager=env_config, logger=logger)
    pipeline.image_template = args.template
    
    # 4. 执行流程
    print("Step 1: Processing URL and Generating Content...")
    try:
        # 使用正确的方法名 run_full_pipeline
        success = await pipeline.run_full_pipeline(
            url=args.url, 
            prompt_template=None  # 使用默认提示词
        )
        
        if success:
            print("✅ [GitHub Runner] Workflow Completed Successfully!")
            sys.exit(0)
        else:
            print("❌ [GitHub Runner] Workflow Failed.")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ [GitHub Runner] Exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
