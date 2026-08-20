"""OMR 客观题识别核心模块"""
import logging

logger = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np
    CV_OK = True
except Exception:
    CV_OK = False

FILL_THRESHOLD = 0.12


def _norm_area(area):
    return {
        "x1": int(area.get("x1", 0)),
        "y1": int(area.get("y1", 0)),
        "x2": int(area.get("x2", 0)),
        "y2": int(area.get("y2", 0)),
    }


def load_image(path):
    if not CV_OK:
        raise RuntimeError("OpenCV 未安装，无法进行图像识别")
    img = cv2.imread(path)
    if img is None:
        raise RuntimeError(f"无法读取图片: {path}")
    return img


def crop(img, area):
    a = _norm_area(area)
    h, w = img.shape[:2]
    x1 = max(0, min(a["x1"], w))
    y1 = max(0, min(a["y1"], h))
    x2 = max(0, min(a["x2"], w))
    y2 = max(0, min(a["y2"], h))
    if x2 <= x1 or y2 <= y1:
        return None
    return img[y1:y2, x1:x2]


def fill_ratio(img):
    """计算区域内黑色像素比例（涂卡填充度）"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
    total = th.size
    if total == 0:
        return 0.0
    black = cv2.countNonZero(th)
    return black / total


def scale_area(area, sw, sh):
    return {
        "x1": int(area["x1"] * sw),
        "y1": int(area["y1"] * sh),
        "x2": int(area["x2"] * sw),
        "y2": int(area["y2"] * sh),
    }


def recognize_options(img, options):
    """对每个选项框计算填充比例, 返回 {label: ratio}"""
    result = {}
    for label, area in options.items():
        c = crop(img, area)
        result[label] = round(fill_ratio(c), 3) if c is not None else 0.0
    return result


def recognize_objective(image_path, template_image_path, objective_area):
    """识别客观题区域, 返回 {qno: {type, answer:[...], ratios:{...}}}"""
    if not CV_OK:
        return None
    img = load_image(image_path)
    tpl = load_image(template_image_path)
    tw, th = tpl.shape[1], tpl.shape[0]
    iw, ih = img.shape[1], img.shape[0]
    sw, sh = iw / tw, ih / th

    result = {}
    for qno, qconf in objective_area.items():
        type_ = qconf.get("type", "single")
        options = qconf.get("options", {})
        scaled = {lab: scale_area(ar, sw, sh) for lab, ar in options.items()}
        ratios = recognize_options(img, scaled)
        marks = [lab for lab, r in ratios.items() if r >= FILL_THRESHOLD]
        if type_ in ("single", "judge"):
            if marks:
                best = max(ratios, key=ratios.get)
                answer = [best] if ratios[best] >= FILL_THRESHOLD else []
            else:
                answer = []
        else:
            answer = marks
        result[qno] = {
            "type": type_,
            "answer": answer,
            "ratios": ratios,
        }
    return result


def recognize_digit_marks(image_path, template_image_path, digit_areas):
    """数字涂卡准考证识别: 每位数字一个区域, 区域内按行等分 0-9 判断"""
    if not CV_OK:
        return None
    img = load_image(image_path)
    tpl = load_image(template_image_path)
    tw, th = tpl.shape[1], tpl.shape[0]
    iw, ih = img.shape[1], img.shape[0]
    sw, sh = iw / tw, ih / th

    digits = []
    for area in digit_areas:
        scaled = scale_area(area, sw, sh)
        c = crop(img, scaled)
        if c is None:
            digits.append("")
            continue
        h = c.shape[0]
        row_h = max(1, h // 10)
        ratios = []
        for i in range(10):
            row = c[i * row_h: (i + 1) * row_h, :]
            ratios.append(fill_ratio(row) if row.size else 0.0)
        if max(ratios) < FILL_THRESHOLD:
            digits.append("")
        else:
            digits.append(str(ratios.index(max(ratios))))
    return "".join(digits)
