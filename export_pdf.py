#!/usr/bin/env python
"""
PDF导出脚本
"""
import json
import os
import sys
from pathlib import Path

# 动态获取项目根目录，避免硬编码绝对路径
PROJECT_ROOT = Path(__file__).resolve().parent

# 添加项目路径到sys.path
sys.path.insert(0, str(PROJECT_ROOT))

def export_pdf(ir_file_path):
    """导出PDF"""
    try:
        # 读取IR文件
        print(f"正在读取报告文件: {ir_file_path}")
        with open(ir_file_path, 'r', encoding='utf-8') as f:
            document_ir = json.load(f)

        # 导入PDF渲染器
        from ReportEngine.renderers.pdf_renderer import PDFRenderer

        # 创建PDF渲染器
        print("正在初始化PDF渲染器...")
        renderer = PDFRenderer()

        # 生成PDF
        print("正在生成PDF...")
        pdf_bytes = renderer.render_to_bytes(document_ir, optimize_layout=True)

        # 确定输出文件名：清洗 topic，并确保最终路径仍落在导出目录内
        from ReportEngine.utils.filenames import report_export_filename

        output_dir = (PROJECT_ROOT / 'final_reports' / 'pdf').resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        pdf_filename = report_export_filename(document_ir, 'pdf')
        output_path = (output_dir / pdf_filename).resolve()
        if not output_path.is_relative_to(output_dir):
            raise ValueError('Refusing to write PDF outside the export directory')

        # 保存PDF文件
        print(f"正在保存PDF到: {output_path}")
        with open(output_path, 'wb') as f:
            f.write(pdf_bytes)

        print(f"✅ PDF导出成功！")
        print(f"文件位置: {output_path}")
        print(f"文件大小: {len(pdf_bytes) / 1024 / 1024:.2f} MB")

        return str(output_path)

    except Exception as e:
        print(f"❌ PDF导出失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # 在 final_reports/ir 目录中查找最新的报告文件
    ir_dir = PROJECT_ROOT / 'final_reports' / 'ir'

    if ir_dir.exists():
        ir_files = sorted(ir_dir.glob('*.json'), key=os.path.getmtime, reverse=True)
        if ir_files:
            latest_report = str(ir_files[0])
            print("="*50)
            print("开始导出PDF")
            print("="*50)
            result = export_pdf(latest_report)
            if result:
                print(f"\n📄 PDF文件已生成: {result}")
        else:
            print(f"❌ 在 {ir_dir} 中未找到报告文件")
    else:
        print(f"❌ 报告目录不存在: {ir_dir}")