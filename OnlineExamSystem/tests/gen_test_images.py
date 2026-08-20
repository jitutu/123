"""生成测试答题卡图片：模板图 + 答卷图（模拟涂卡）"""
import os

import cv2
import numpy as np

BASE = os.path.join(os.path.dirname(__file__), "assets")
os.makedirs(BASE, exist_ok=True)

TEMPLATE_PATH = os.path.join(BASE, "template.png")
PAPER_PATH = os.path.join(BASE, "paper1.png")

W, H = 800, 1000
WHITE = 255


def make_base():
    return np.full((H, W, 3), WHITE, dtype=np.uint8)


def draw_option_boxes(img, y, labels=("A", "B", "C", "D")):
    """绘制一组选项框, 返回 {label: area}"""
    areas = {}
    for i, lab in enumerate(labels):
        x1 = 150 + i * 85
        x2 = x1 + 70
        y2 = y + 55
        cv2.rectangle(img, (x1, y), (x2, y2), (0, 0, 0), 2)
        cv2.putText(img, lab, (x1 + 25, y + 38), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
        areas[lab] = {"x1": x1, "y1": y, "x2": x2, "y2": y2}
    return areas


def draw_digit_marks(img, y, width=60, height=140, x=60):
    """绘制一个数字涂卡位（0-9 从上到下）"""
    cv2.rectangle(img, (x, y), (x + width, y + height), (0, 0, 0), 2)
    row_h = height // 10
    for i in range(10):
        ly = y + i * row_h
        cv2.putText(img, str(i), (x + width + 6, ly + row_h - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    return {"x1": x, "y1": y, "x2": x + width, "y2": y + height}


def fill_option(img, area):
    x1, y1, x2, y2 = area["x1"], area["y1"], area["x2"], area["y2"]
    cv2.rectangle(img, (x1 + 3, y1 + 3), (x2 - 3, y2 - 3), (0, 0, 0), -1)


def fill_digit(img, area, digit):
    x1, y1, x2, y2 = area["x1"], area["y1"], area["x2"], area["y2"]
    row_h = (y2 - y1) // 10
    y = y1 + digit * row_h
    cv2.rectangle(img, (x1 + 3, y + 3), (x2 - 3, y + row_h - 3), (0, 0, 0), -1)


# ---------------- 模板图 ----------------
tpl = make_base()
cv2.putText(tpl, "ANSWER SHEET TEMPLATE", (200, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
cv2.putText(tpl, "ID:", (30, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

digit_areas = []
for i in range(3):
    d = draw_digit_marks(tpl, 90 + i * 170)
    digit_areas.append(d)

sub_area = {"x1": 150, "y1": 600, "x2": 680, "y2": 700}
cv2.rectangle(tpl, (150, 600), (680, 700), (0, 0, 0), 2)
cv2.putText(tpl, "SUBJECTIVE AREA", (230, 650), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

q1 = draw_option_boxes(tpl, 730)
q2 = draw_option_boxes(tpl, 830)
q3 = draw_option_boxes(tpl, 930, labels=("对", "错"))

cv2.imwrite(TEMPLATE_PATH, tpl)
print("template saved:", TEMPLATE_PATH)

# ---------------- 答卷图（学生 001：涂 A / C / 对） ----------------
paper = make_base()
cv2.putText(paper, "ANSWER SHEET", (250, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)

for i, digit in enumerate([0, 0, 1]):
    fill_digit(paper, digit_areas[i], digit)

fill_option(paper, q1["A"])
fill_option(paper, q2["C"])
fill_option(paper, q3["对"])

cv2.rectangle(paper, (150, 600), (680, 700), (0, 0, 0), 2)
cv2.line(paper, (180, 620), (620, 640), (80, 80, 80), 3)
cv2.line(paper, (200, 650), (500, 630), (80, 80, 80), 3)

cv2.imwrite(PAPER_PATH, paper)
print("paper saved:", PAPER_PATH)
