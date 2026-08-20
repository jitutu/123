"""条码识别（可选依赖 pyzbar，缺失时降级返回 None）"""
import logging

logger = logging.getLogger(__name__)

try:
    from pyzbar import pyzbar
    import cv2
    ZBAR_OK = True
except Exception:
    ZBAR_OK = False


def read_barcode(image_path):
    """读取答题卡条码, 返回解码字符串, 失败返回 None"""
    if not ZBAR_OK:
        logger.warning("pyzbar 未安装，条码识别不可用")
        return None
    try:
        img = cv2.imread(image_path)
        if img is None:
            return None
        results = pyzbar.decode(img)
        if not results:
            return None
        return results[0].data.decode("utf-8", errors="ignore").strip()
    except Exception as e:
        logger.warning("条码识别失败: %s", e)
        return None
