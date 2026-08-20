"""OCR 数字识别（可选依赖 PaddleOCR，缺失时降级返回 None）"""
import logging

logger = logging.getLogger(__name__)

_ocr = None


def _get_ocr():
    global _ocr
    if _ocr is None:
        from paddleocr import PaddleOCR
        _ocr = PaddleOCR(use_angle_cls=False, show_log=False)
    return _ocr


def read_digits(image_path, area=None):
    """识别图片/区域中的数字串, 失败返回 None"""
    try:
        ocr = _get_ocr()
        import cv2
        img = cv2.imread(image_path)
        if img is None:
            return None
        if area:
            a = {k: int(v) for k, v in area.items()}
            h, w = img.shape[:2]
            img = img[max(0, a["y1"]):min(a["y2"], h), max(0, a["x1"]):min(a["x2"], w)]
        result = ocr.ocr(img, cls=False)
        text = ""
        for line in (result[0] or []):
            text += line[1][0]
        digits = "".join(ch for ch in text if ch.isdigit())
        return digits or None
    except ImportError:
        logger.warning("paddleocr 未安装，OCR 识别不可用")
        return None
    except Exception as e:
        logger.warning("OCR 识别失败: %s", e)
        return None
