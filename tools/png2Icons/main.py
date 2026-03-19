#!/usr/bin/env python3
"""
PNG to ICNS + ICO 图标生成脚本
用法: python png2icons.py <input.png>
依赖:
    - Python 3.6+
    - Pillow 库 (用于生成 ICO)
    - macOS 系统 (用于生成 ICNS, 需要 sips 和 iconutil)
输出:
    在与输入文件相同的目录下生成 <同名>.icns 和 <同名>.ico
"""

import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path

# 检查 Pillow 是否安装
try:
    from PIL import Image
except ImportError:
    print("错误: 需要 Pillow 库。请安装: pip install Pillow")
    sys.exit(1)

def check_macos_tools():
    """检查 macOS 所需工具是否存在"""
    sips_path = shutil.which("sips")
    iconutil_path = shutil.which("iconutil")
    if not sips_path or not iconutil_path:
        print("错误: 需要 macOS 自带的 'sips' 和 'iconutil' 命令。")
        print("请确保您在 macOS 系统上运行此脚本。")
        return False
    return True

def generate_ico(png_path, ico_path):
    """
    使用 Pillow 生成包含多种尺寸的 ICO 文件
    ICO 标准尺寸: 16, 24, 32, 48, 64, 128, 256
    """
    img = Image.open(png_path)
    # 确保图片是正方形，如果不是，填充透明背景居中
    if img.width != img.height:
        size = max(img.width, img.height)
        square_img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        offset = ((size - img.width) // 2, (size - img.height) // 2)
        square_img.paste(img, offset)
        img = square_img
        print("提示: 源图片不是正方形，已自动填充为正方形。")

    # 定义要包含的图标尺寸
    icon_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    # 生成每个尺寸的副本
    img_versions = []
    for size in icon_sizes:
        resized = img.resize(size, Image.Resampling.LANCZOS)
        img_versions.append(resized)
    # 保存为 ICO，包含所有尺寸
    img_versions[0].save(
        ico_path,
        format='ICO',
        sizes=icon_sizes,
        append_images=img_versions[1:]
    )
    print(f"ICO 生成成功: {ico_path}")

def generate_icns(png_path, icns_path):
    """
    使用 macOS 的 sips 和 iconutil 生成 ICNS
    步骤:
        1. 创建临时 .iconset 文件夹
        2. 用 sips 生成所有所需尺寸的 PNG
        3. 用 iconutil 打包成 .icns
    """
    # 创建临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        iconset_dir = Path(tmpdir) / "MyIcon.iconset"
        iconset_dir.mkdir()

        # 定义需要生成的尺寸 (参考 Apple 官方要求)
        sizes = [
            (16, 16, "icon_16x16.png"),
            (32, 32, "icon_16x16@2x.png"),   # 相当于 32x32
            (32, 32, "icon_32x32.png"),
            (64, 64, "icon_32x32@2x.png"),   # 相当于 64x64
            (128, 128, "icon_128x128.png"),
            (256, 256, "icon_128x128@2x.png"), # 相当于 256x256
            (256, 256, "icon_256x256.png"),
            (512, 512, "icon_256x256@2x.png"), # 相当于 512x512
            (512, 512, "icon_512x512.png"),
            (1024, 1024, "icon_512x512@2x.png") # 相当于 1024x1024
        ]

        # 使用 sips 生成每个尺寸的文件
        for w, h, filename in sizes:
            out_file = iconset_dir / filename
            # 如果源 PNG 尺寸小于目标，sips 会放大，但质量可能不佳
            cmd = ["sips", "-z", str(h), str(w), png_path, "--out", str(out_file)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"sips 执行失败: {result.stderr}")
                sys.exit(1)

        # 使用 iconutil 打包
        cmd = ["iconutil", "-c", "icns", str(iconset_dir), "-o", icns_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"iconutil 执行失败: {result.stderr}")
            sys.exit(1)

    print(f"ICNS 生成成功: {icns_path}")

def main():
    if len(sys.argv) != 2:
        print("用法: python png2icons.py <input.png>")
        sys.exit(1)

    png_file = Path(sys.argv[1])
    if not png_file.is_file():
        print(f"错误: 文件不存在 {png_file}")
        sys.exit(1)

    # 检查后缀是否为 PNG
    if png_file.suffix.lower() != '.png':
        print("警告: 输入文件不是 PNG 格式，但脚本仍会尝试处理。")

    # 生成输出文件名
    base_name = png_file.stem
    output_dir = png_file.parent
    icns_path = output_dir / f"{base_name}.icns"
    ico_path = output_dir / f"{base_name}.ico"

    # 生成 ICO (始终尝试)
    try:
        generate_ico(str(png_file), str(ico_path))
    except Exception as e:
        print(f"生成 ICO 失败: {e}")
        sys.exit(1)

    # 生成 ICNS (仅限 macOS)
    if sys.platform == 'darwin':
        if check_macos_tools():
            try:
                generate_icns(str(png_file), str(icns_path))
            except Exception as e:
                print(f"生成 ICNS 失败: {e}")
                sys.exit(1)
        else:
            print("跳过 ICNS 生成：缺少 macOS 必要工具。")
    else:
        print("跳过 ICNS 生成：当前系统不是 macOS。")

    print("\n所有操作完成！")

if __name__ == "__main__":
    main()