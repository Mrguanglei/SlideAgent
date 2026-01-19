"""
PPTX 生成器测试脚本

测试新的 HTML 解析 + python-pptx 方案是否能正确生成可编辑的 PPTX 文件。
"""

import asyncio
import os
import sys

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 直接导入模块，避免 services/__init__.py 的依赖问题
import importlib.util

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

# 加载 html_parser
html_parser = load_module('services.html_parser', os.path.join(os.path.dirname(__file__), 'services', 'html_parser.py'))
sys.modules['services.html_parser'] = html_parser

# 加载 pptx_generator
pptx_generator = load_module('services.pptx_generator', os.path.join(os.path.dirname(__file__), 'services', 'pptx_generator.py'))
generate_pptx = pptx_generator.generate_pptx


# 测试用的 HTML 幻灯片
TEST_SLIDES = [
    # 封面页
    '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                width: 1280px;
                height: 720px;
                background: linear-gradient(135deg, #17a7b8 0%, #0d6e7a 100%);
                font-family: 'Microsoft YaHei', sans-serif;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                color: white;
            }
            h1 {
                font-size: 48px;
                font-weight: bold;
                margin-bottom: 20px;
                text-align: center;
            }
            p {
                font-size: 24px;
                opacity: 0.9;
            }
        </style>
    </head>
    <body>
        <h1>PPTAgent 演示文稿</h1>
        <p>使用 Python + python-pptx 生成</p>
    </body>
    </html>
    ''',
    
    # 内容页
    '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                width: 1280px;
                height: 720px;
                background: #ffffff;
                font-family: 'Microsoft YaHei', sans-serif;
                padding: 40px;
            }
            h2 {
                font-size: 36px;
                color: #17a7b8;
                margin-bottom: 30px;
            }
            .content {
                display: flex;
                gap: 40px;
            }
            .card {
                flex: 1;
                background: #f5f5f5;
                border-radius: 12px;
                padding: 24px;
            }
            .card h3 {
                font-size: 24px;
                color: #333;
                margin-bottom: 16px;
            }
            .card p {
                font-size: 16px;
                color: #666;
                line-height: 1.6;
            }
        </style>
    </head>
    <body>
        <h2>技术特点</h2>
        <div class="content">
            <div class="card">
                <h3>可编辑文本</h3>
                <p>生成的 PPTX 中的文本可以直接在 PowerPoint 中编辑，无需重新生成。</p>
            </div>
            <div class="card">
                <h3>保持布局</h3>
                <p>通过精确的位置计算，确保 PPTX 中的元素位置与 HTML 预览一致。</p>
            </div>
            <div class="card">
                <h3>支持图片</h3>
                <p>自动下载并嵌入网络图片，支持 PNG、JPG、GIF 等格式。</p>
            </div>
        </div>
    </body>
    </html>
    ''',
    
    # 结束页
    '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                width: 1280px;
                height: 720px;
                background: #333;
                font-family: 'Microsoft YaHei', sans-serif;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                color: white;
            }
            h1 {
                font-size: 48px;
                font-weight: bold;
                margin-bottom: 20px;
            }
            p {
                font-size: 20px;
                color: #17a7b8;
            }
        </style>
    </head>
    <body>
        <h1>谢谢观看</h1>
        <p>PPTAgent - 智能 PPT 生成助手</p>
    </body>
    </html>
    '''
]


async def main():
    """测试 PPTX 生成"""
    print("=" * 60)
    print("PPTX 生成器测试")
    print("=" * 60)
    
    output_path = "/tmp/test_pptx_output.pptx"
    
    try:
        print(f"\n正在生成 PPTX 文件...")
        print(f"  - 幻灯片数量: {len(TEST_SLIDES)}")
        print(f"  - 输出路径: {output_path}")
        
        result = await generate_pptx(
            slides_html=TEST_SLIDES,
            output_path=output_path,
            title="PPTAgent 测试演示"
        )
        
        # 检查文件
        if os.path.exists(result):
            file_size = os.path.getsize(result)
            print(f"\n✅ PPTX 生成成功!")
            print(f"  - 文件路径: {result}")
            print(f"  - 文件大小: {file_size:,} 字节")
            
            # 验证文件是否是有效的 ZIP（PPTX 本质是 ZIP）
            import zipfile
            if zipfile.is_zipfile(result):
                print(f"  - 文件格式: 有效的 PPTX (ZIP)")
                
                # 列出 PPTX 内容
                with zipfile.ZipFile(result, 'r') as zf:
                    files = zf.namelist()
                    slide_files = [f for f in files if f.startswith('ppt/slides/slide')]
                    print(f"  - 幻灯片数量: {len(slide_files)}")
            else:
                print(f"  - ❌ 文件格式无效!")
                return False
            
            return True
        else:
            print(f"\n❌ PPTX 文件未生成!")
            return False
            
    except Exception as e:
        print(f"\n❌ 生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    print("\n" + "=" * 60)
    if success:
        print("测试通过 ✅")
    else:
        print("测试失败 ❌")
    print("=" * 60)
    sys.exit(0 if success else 1)
