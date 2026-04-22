"""
验证码求解器 - AI滑块识别与人工回退

功能：
1. AI滑块位置识别（ONNX模型）
2. OpenCV图像预处理和边缘检测（备用方案）
3. 浏览器拖拽执行（Playwright）
4. 人工回退机制（3次失败后）
"""

import asyncio
import io
import random
import threading
import time
from pathlib import Path
from typing import Optional, Tuple, List

import numpy as np

from glm_coding_bot.utils.logger import get_logger

logger = get_logger(__name__)


class CaptchaSolver:
    """
    验证码求解器

    使用AI模型（如果有）或OpenCV图像处理来识别滑块位置，
    然后执行浏览器拖拽操作。AI失败3次后转人工处理。

    Attributes:
        model_path: ONNX模型路径
        max_retries: 最大重试次数
        retry_delay: 重试间隔（秒）
        confidence_threshold: AI识别置信度阈值
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 0.1,
        confidence_threshold: float = 0.8,
    ):
        self.model_path = Path(model_path) if model_path else None
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.confidence_threshold = confidence_threshold

        self.session = None
        self._load_model()

    def _load_model(self):
        """加载ONNX模型"""
        if self.model_path and self.model_path.exists():
            try:
                import onnxruntime as ort

                self.session = ort.InferenceSession(
                    str(self.model_path),
                    providers=["CPUExecutionProvider"],
                )
                logger.info(f"✓ ONNX模型已加载: {self.model_path}")
            except ImportError:
                logger.warning("onnxruntime未安装，将使用备用检测方法")
            except Exception as e:
                logger.warning(f"加载ONNX模型失败: {e}，将使用备用检测方法")
        else:
            if self.model_path:
                logger.warning(f"模型文件不存在: {self.model_path}，将使用备用检测方法")
            else:
                logger.info("未提供模型路径，将使用备用检测方法")

    async def solve_slider(
        self,
        page,
        timeout: float = 15.0,
        manual_fallback: bool = True,
    ) -> bool:
        """
        解决滑块验证码

        流程：
        1. 截取滑块区域图片
        2. 使用AI模型预测滑块位置（如果有）
        3. 否则使用OpenCV边缘检测作为备用
        4. 执行拖拽操作
        5. 验证是否成功
        6. 失败重试（最多3次）
        7. 3次失败后转人工（如果manual_fallback为True）

        Args:
            page: Playwright页面对象
            timeout: 人工处理超时时间
            manual_fallback: 失败时是否转人工

        Returns:
            bool: 是否成功解决验证码
        """
        logger.info(f"开始解决滑块验证码 (最大尝试{self.max_retries}次)...")

        for attempt in range(self.max_retries):
            try:
                logger.info(f"尝试 {attempt + 1}/{self.max_retries}...")

                # 1. 获取滑块图片
                slider_img = await self._get_slider_image(page)
                if slider_img is None:
                    logger.warning("无法获取滑块图片，可能页面结构已改变")
                    await asyncio.sleep(self.retry_delay)
                    continue

                # 2. AI预测位置（如果有模型）
                position, confidence = await self._predict_position(slider_img)

                if position is None:
                    logger.warning("无法预测滑块位置")
                    await asyncio.sleep(self.retry_delay)
                    continue

                logger.info(f"预测滑块位置: {position}px (置信度: {confidence:.2f})")

                # 3. 执行拖拽
                success = await self._drag_slider(page, position)

                if success:
                    # 4. 验证是否成功
                    await asyncio.sleep(0.5)  # 等待验证结果

                    # 检查是否还有验证码
                    captcha_exists = await self._check_captcha_exists(page)

                    if not captcha_exists:
                        logger.info("✓ 验证码解决成功！")
                        return True
                    else:
                        logger.warning("验证码仍在，可能识别位置不准确")
                else:
                    logger.warning("拖拽执行失败")

            except Exception as e:
                logger.error(f"滑块识别失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")

            # 等待后重试
            if attempt < self.max_retries - 1:
                logger.info(f"{self.retry_delay}秒后重试...")
                await asyncio.sleep(self.retry_delay)

        # 所有尝试失败
        logger.error(f"滑块验证码解决失败（重试{self.max_retries}次）")

        # 转人工处理
        if manual_fallback:
            return await self._manual_solve(page, timeout)

        return False

    async def _get_slider_image(self, page) -> Optional[np.ndarray]:
        """
        获取滑块区域图片

        尝试多种常见的滑块验证码选择器。
        """
        import cv2

        # 常见的滑块验证码选择器
        captcha_selectors = [
            ".slider-captcha",
            ".captcha-slider",
            ".verify-slider",
            "[class*='slider']",
            "[class*='captcha']",
            "[id*='slider']",
            "[id*='captcha']",
            ".geetest_slider",
            ".nc-slider",
        ]

        for selector in captcha_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    # 获取元素边界
                    bbox = await element.bounding_box()
                    if bbox and bbox["width"] > 0 and bbox["height"] > 0:
                        # 截取元素区域
                        screenshot = await page.screenshot(clip=bbox)
                        # 转换为OpenCV格式
                        nparr = np.frombuffer(screenshot, np.uint8)
                        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                        if img is not None and img.size > 0:
                            logger.debug(f"成功获取滑块图片: {selector} ({img.shape})")
                            return img

            except Exception as e:
                logger.debug(f"选择器 {selector} 失败: {e}")
                continue

        logger.warning("无法找到滑块验证码元素")
        return None

    async def _predict_position(
        self,
        image: np.ndarray
    ) -> Tuple[Optional[int], float]:
        """
        预测滑块位置

        优先使用AI模型，否则使用OpenCV边缘检测。

        Returns:
            Tuple[位置, 置信度]
        """
        if self.session and image is not None:
            try:
                # AI模型推理
                position, confidence = await self._ai_predict(image)
                if position is not None and confidence >= self.confidence_threshold:
                    return position, confidence
            except Exception as e:
                logger.warning(f"AI预测失败: {e}")

        # 备用：OpenCV边缘检测
        return await self._opencv_predict(image)

    async def _ai_predict(self, image: np.ndarray) -> Tuple[Optional[int], float]:
        """使用ONNX模型预测滑块位置"""
        try:
            # 预处理图片
            input_tensor = self._preprocess_image(image)

            # 运行推理
            outputs = self.session.run(None, {"input": input_tensor})

            # 解析结果
            # 假设输出是 [x_position, confidence]
            position = int(outputs[0][0][0])
            confidence = float(outputs[0][0][1]) if len(outputs[0][0]) > 1 else 0.5

            return position, confidence

        except Exception as e:
            logger.error(f"AI预测错误: {e}")
            return None, 0.0

    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """预处理图片用于模型输入"""
        import cv2

        # 调整大小为标准输入尺寸（例如224x224）
        resized = cv2.resize(image, (224, 224))

        # 归一化到 [0, 1]
        normalized = resized.astype(np.float32) / 255.0

        # 调整维度为 [batch, channels, height, width]
        transposed = np.transpose(normalized, (2, 0, 1))
        batched = np.expand_dims(transposed, axis=0)

        return batched

    async def _opencv_predict(
        self,
        image: np.ndarray
    ) -> Tuple[Optional[int], float]:
        """
        使用OpenCV边缘检测预测滑块位置

        通过检测缺口特征来确定滑块目标位置。
        """
        import cv2

        if image is None:
            return None, 0.0

        try:
            # 转换为灰度图
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # 边缘检测
            edges = cv2.Canny(gray, 50, 150)

            # 膨胀边缘以连接断开的部分
            kernel = np.ones((5, 5), np.uint8)
            dilated = cv2.dilate(edges, kernel, iterations=1)

            # 查找轮廓
            contours, _ = cv2.findContours(
                dilated,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )

            if not contours:
                return None, 0.0

            # 找到最大的轮廓（通常是滑块缺口）
            largest_contour = max(contours, key=cv2.contourArea)

            # 计算轮廓的中心x坐标
            M = cv2.moments(largest_contour)
            if M["m00"] == 0:
                return None, 0.0

            center_x = int(M["m10"] / M["m00"])

            # 置信度基于轮廓大小（越大越可能是正确位置）
            area = cv2.contourArea(largest_contour)
            confidence = min(area / 1000, 0.9)  # 归一化到0-0.9

            logger.debug(f"OpenCV预测位置: {center_x}px (置信度: {confidence:.2f})")

            return center_x, confidence

        except Exception as e:
            logger.error(f"OpenCV预测错误: {e}")
            return None, 0.0

    async def _drag_slider(self, page, position: int) -> bool:
        """
        执行滑块拖拽

        模拟人类拖拽行为，带随机抖动和变速。
        """
        try:
            # 常见的滑块按钮选择器
            slider_selectors = [
                ".slider-button",
                ".captcha-slider-btn",
                ".verify-slider-btn",
                "[class*='slider-button']",
                "[class*='slider-btn']",
                ".geetest_slider_button",
                ".nc_iconfont.btn_slide",
            ]

            slider = None
            for selector in slider_selectors:
                try:
                    slider = await page.query_selector(selector)
                    if slider:
                        logger.debug(f"找到滑块按钮: {selector}")
                        break
                except Exception:
                    continue

            if not slider:
                logger.warning("未找到滑块按钮")
                return False

            # 获取滑块当前位置
            bbox = await slider.bounding_box()
            if not bbox:
                logger.warning("无法获取滑块位置")
                return False

            start_x = bbox["x"] + bbox["width"] / 2
            start_y = bbox["y"] + bbox["height"] / 2

            # 获取拖拽轨道长度
            track_selectors = [
                ".slider-track",
                ".captcha-track",
                ".verify-track",
                "[class*='slider-track']",
                ".geetest_track",
            ]

            track_width = 300  # 默认轨道宽度
            for selector in track_selectors:
                try:
                    track = await page.query_selector(selector)
                    if track:
                        track_bbox = await track.bounding_box()
                        if track_bbox:
                            track_width = track_bbox["width"] - bbox["width"]
                            break
                except Exception:
                    continue

            # 限制目标位置在有效范围内
            target_x = min(max(position, start_x + 10), start_x + track_width - 10)
            target_y = start_y

            logger.debug(f"拖拽滑块: ({start_x:.1f}, {start_y:.1f}) -> ({target_x:.1f}, {target_y:.1f})")

            # 执行拖拽 - 模拟人类行为
            await page.mouse.move(start_x, start_y)
            await page.mouse.down()

            # 分步拖拽，模拟人类行为
            steps = random.randint(15, 25)  # 随机步数
            current_x = start_x
            current_y = start_y

            for i in range(steps):
                progress = (i + 1) / steps

                # 计算当前目标位置
                # 添加缓动效果 - 先快后慢
                ease_progress = 1 - (1 - progress) ** 2

                next_x = start_x + (target_x - start_x) * ease_progress
                next_y = start_y + (target_y - start_y) * ease_progress

                # 添加随机抖动（模拟人类手抖）
                jitter_x = random.gauss(0, 2)  # 正态分布，标准差2像素
                jitter_y = random.gauss(0, 1)

                current_x = next_x + jitter_x
                current_y = next_y + jitter_y

                # 移动鼠标
                await page.mouse.move(current_x, current_y)

                # 随机延迟（模拟人类反应时间）
                delay = random.uniform(0.008, 0.02)  # 8-20ms
                await asyncio.sleep(delay)

            # 最后微调到位
            await page.mouse.move(target_x, target_y)
            await asyncio.sleep(0.05)  # 短暂停顿

            # 释放鼠标
            await page.mouse.up()

            logger.debug("滑块拖拽完成")
            return True

        except Exception as e:
            logger.error(f"拖拽滑块失败: {e}")
            return False

    async def _check_captcha_exists(self, page) -> bool:
        """检查页面是否存在验证码"""
        captcha_selectors = [
            ".slider-captcha",
            ".captcha-slider",
            ".verify-slider",
            "[class*='slider-captcha']",
            "[class*='captcha-slider']",
            ".geetest_slider",
            ".nc-container",
        ]

        for selector in captcha_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    is_visible = await element.is_visible()
                    if is_visible:
                        return True
            except Exception:
                continue

        return False

    async def _manual_solve(self, page, timeout: float) -> bool:
        """
        人工介入解决验证码

        当AI失败3次后，提示用户手动完成。
        """
        logger.info("\n" + "=" * 60)
        logger.info("🔔 AI验证码识别失败，需要人工介入")
        logger.info("=" * 60)
        logger.info(f"⏱️  你有 {timeout:.0f} 秒时间完成滑块验证...")
        logger.info("📝 请手动拖动滑块完成验证")
        logger.info("✅ 完成后按 Enter 键继续...")
        logger.info("=" * 60 + "\n")

        result = {"confirmed": False}

        def wait_for_input():
            try:
                input()
                result["confirmed"] = True
            except (EOFError, KeyboardInterrupt):
                pass

        thread = threading.Thread(target=wait_for_input)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout)

        if result["confirmed"]:
            logger.info("✓ 人工验证完成")
            return True
        else:
            logger.warning("✗ 人工验证超时")
            return False