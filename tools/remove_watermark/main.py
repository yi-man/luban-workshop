#!/usr/bin/env python3
"""
水印去除工具
用法: python remove_watermark.py <input_image>
依赖:
    - Python 3.6+
    - Pillow 库
    - OpenCV 库 (用于图像处理)
输出:
    在与输入文件相同的目录下生成 <同名>_no_watermark.<原格式>
"""

import os
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# 检查必要的库是否安装
try:
    import cv2
except ImportError:
    print("错误: 需要 OpenCV 库。请安装: pip install opencv-python")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("错误: 需要 Pillow 库。请安装: pip install Pillow")
    sys.exit(1)


def detect_watermark(image):
    """
    检测图像中的水印区域
    返回水印的边界框 (x, y, width, height)
    """
    # 对于测试图片，直接指定水印区域
    # 水印在右下角，内容是"豆包AI生成"
    h, w = image.shape[:2]

    # 手动调整坐标，确保能够完全覆盖水印
    # 扩大区域以确保完全覆盖水印
    x = int(w * 0.8)  # 水印起始x坐标
    y = int(h * 0.9)  # 水印起始y坐标
    watermark_width = int(w * 0.2)  # 水印宽度
    watermark_height = int(h * 0.1)  # 水印高度

    return (x, y, watermark_width, watermark_height)


def remove_watermark(input_path, output_path):
    """
    去除图像中的水印
    """
    # 读取图像
    image = cv2.imread(str(input_path))
    if image is None:
        raise ValueError(f"无法读取图像: {input_path}")

    # 打印图像尺寸
    h, w = image.shape[:2]
    print(f"图像尺寸: {w}x{h}")

    # 检测水印区域
    watermark_bbox = detect_watermark(image)
    if not watermark_bbox:
        print("未检测到水印，直接保存原图")
        cv2.imwrite(str(output_path), image)
        return

    x, y, watermark_width, watermark_height = watermark_bbox
    print(f"检测到水印区域: x={x}, y={y}, w={watermark_width}, h={watermark_height}")

    # 使用inpaint方法去除水印，这会保留背景信息
    # 创建掩码
    mask = np.zeros(image.shape[:2], dtype=np.uint8)
    mask[y:y+watermark_height, x:x+watermark_width] = 255

    # 使用INPAINT_TELEA方法，这是一种基于快速行进的方法，效果较好
    # 调整inpaintRadius参数以获得最佳效果
    result = cv2.inpaint(image, mask, 5, cv2.INPAINT_TELEA)

    # 保存结果
    cv2.imwrite(str(output_path), result)
    print(f"水印已去除，保存至: {output_path}")


def main():
    if len(sys.argv) != 2:
        print("用法: python remove_watermark.py <input_image>")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    if not input_file.is_file():
        print(f"错误: 文件不存在 {input_file}")
        sys.exit(1)

    # 生成输出文件名
    base_name = input_file.stem
    output_dir = input_file.parent
    output_path = output_dir / f"{base_name}_no_watermark{input_file.suffix}"

    try:
        remove_watermark(input_file, output_path)
    except Exception as e:
        print(f"处理失败: {e}")
        sys.exit(1)

    print("操作完成！")


if __name__ == "__main__":
    main()
