"""
测试新的 PPTX 导出功能

验证基于 suna 项目的 HTML 渲染 + 元素截图 + python-pptx 重构方案
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.html_to_pptx_converter import convert_html_to_pptx


# 测试用的 HTML 幻灯片（包含复杂样式）
TEST_SLIDES = [
    # 封面页 - 渐变背景
    '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            width: 1920px;
            height: 1080px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            font-family: 'Microsoft YaHei', sans-serif;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            color: white;
        }
        h1 {
            font-size: 72px;
            font-weight: bold;
            margin-bottom: 30px;
            text-align: center;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        p {
            font-size: 36px;
            opacity: 0.9;
        }
    </style>
</head>
<body>
    <h1>PPTAgent 新导出方案测试</h1>
    <p>HTML 渲染 + 元素截图 + python-pptx</p>
</body>
</html>''',
    
    # 内容页 - 卡片布局
    '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            width: 1920px;
            height: 1080px;
            background: #f5f7fa;
            font-family: 'Microsoft YaHei', sans-serif;
            padding: 80px;
        }
        h2 {
            font-size: 54px;
            color: #667eea;
            margin-bottom: 50px;
            font-weight: bold;
        }
        .content {
            display: flex;
            gap: 60px;
        }
        .card {
            flex: 1;
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        .card h3 {
            font-size: 36px;
            color: #333;
            margin-bottom: 24px;
            font-weight: 600;
        }
        .card p {
            font-size: 24px;
            color: #666;
            line-height: 1.8;
        }
    </style>
</head>
<body>
    <h2>技术特点</h2>
    <div class="content">
        <div class="card">
            <h3>🎨 样式保真</h3>
            <p>通过截图方式保留所有复杂样式，包括渐变、阴影、圆角等视觉效果。</p>
        </div>
        <div class="card">
            <h3>✏️ 文本可编辑</h3>
            <p>文本内容以可编辑文本框形式存在，用户可在 PowerPoint 中直接修改。</p>
        </div>
        <div class="card">
            <h3>📊 图表支持</h3>
            <p>自动处理 Canvas 图表，转换为高清图片嵌入到 PPTX 中。</p>
        </div>
    </div>
</body>
</html>''',
    
    # 结束页 - 深色背景
    '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            width: 1920px;
            height: 1080px;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            font-family: 'Microsoft YaHei', sans-serif;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            color: white;
        }
        h1 {
            font-size: 72px;
            font-weight: bold;
            margin-bottom: 30px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        p {
            font-size: 30px;
            color: #a8d8ff;
        }
    </style>
</head>
<body>
    <h1>谢谢观看</h1>
    <p>PPTAgent - 智能 PPT 生成助手</p>
</body>
</html>'''
]


async def main():
    """测试新的 PPTX 导出功能"""
    print("=" * 80)
    print("新 PPTX 导出方案测试")
    print("=" * 80)
    
    output_path = "/tmp/test_new_export.pptx"
    
    try:
        print(f"\n正在生成 PPTX 文件...")
        print(f"  - 幻灯片数量: {len(TEST_SLIDES)}")
        print(f"  - 输出路径: {output_path}")
        print(f"  - 方案: HTML 渲染 + 元素截图 + python-pptx")
        
        result = await convert_html_to_pptx(
            slides_html=TEST_SLIDES,
            output_path=output_path,
            title="PPTAgent 新导出方案测试"
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
                    
                    # 检查是否包含图片（背景截图）
                    media_files = [f for f in files if f.startswith('ppt/media/')]
                    print(f"  - 媒体文件数量: {len(media_files)}")
            else:
                print(f"  - ❌ 文件格式无效!")
                return False
            
            print(f"\n📝 请用 PowerPoint 打开文件验证：")
            print(f"   1. 样式是否保留（渐变背景、阴影、圆角等）")
            print(f"   2. 文本是否可编辑")
            print(f"   3. 布局是否正确")
            
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
    print("\n" + "=" * 80)
    if success:
        print("测试通过 ✅")
    else:
        print("测试失败 ❌")
    print("=" * 80)
    sys.exit(0 if success else 1)
