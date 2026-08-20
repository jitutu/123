"""答题卡识别服务：准考证识别 + 客观题识别 + 自动评分"""
import json
import logging
import os

from database import db
from models import Paper, Score
from recognition import omr
from recognition.barcode import read_barcode
from recognition.ocr import read_digits

logger = logging.getLogger(__name__)

DEFAULT_PASSWORD = "123456"


def _tpl_image(template):
    """模板图路径（正面）"""
    if not template or not template.image:
        return None
    from config import Config
    return os.path.join(Config.TEMPLATE_FOLDER, template.image)


def _paper_image(paper):
    from config import Config
    return os.path.join(Config.PAPERS_FOLDER, paper.image)


def recognize_paper(exam, paper, operator_id=None):
    """完整识别流程: 识别准考证 -> 匹配学生 -> 识别客观题 -> 自动评分"""
    tpl = exam.template
    tpl_path = _tpl_image(tpl)
    if not tpl_path or not os.path.exists(tpl_path):
        raise RuntimeError("该考试尚未配置答题卡模板")
    paper_path = _paper_image(paper)
    if not os.path.exists(paper_path):
        raise RuntimeError("答卷图片不存在")

    recognized = None
    if omr.CV_OK:
        recognized = omr.recognize_objective(paper_path, tpl_path, _load_json(tpl.objective_area) or {})
        if recognized:
            paper.recognized_answer = json.dumps(recognized, ensure_ascii=False)

    # 准考证识别
    student = _match_student(exam, paper, tpl)
    if student:
        paper.student_id = student.id

    db.session.commit()

    # 客观题自动评分
    if recognized:
        auto_score_objective(exam, paper, operator_id, recognized)
    return {
        "student_no": student.student_no if student else None,
        "student_name": student.name if student else None,
        "objective": recognized,
    }


def _match_student(exam, paper, tpl):
    """根据准考证号识别并匹配学生"""
    barcode_area = _load_json(tpl.barcode_area) if tpl else None
    student_no = None

    if barcode_area:
        mode = barcode_area.get("mode", "barcode")
        if mode == "barcode" and barcode_area.get("area"):
            student_no = read_barcode(_paper_image(paper))
        elif mode == "digits":
            digits = barcode_area.get("digits", [])
            if digits:
                from config import Config
                student_no = omr.recognize_digit_marks(
                    _paper_image(paper),
                    os.path.join(Config.TEMPLATE_FOLDER, tpl.image),
                    [d.get("area") for d in digits],
                )
        elif mode == "ocr" and barcode_area.get("area"):
            student_no = read_digits(_paper_image(paper), barcode_area.get("area"))

    if not student_no:
        return None

    def norm_no(s):
        s = str(s).strip()
        return s.lstrip("0") or "0"

    target = norm_no(student_no)
    for es in exam.exam_students:
        if norm_no(es.student.student_no) == target:
            return es.student
    return None


def auto_score_objective(exam, paper, operator_id, recognized):
    """根据识别结果与标准答案计算客观题得分"""
    questions = {str(q.question_no): q for q in exam.questions if q.type != "subjective"}
    for qno, qconf in recognized.items():
        q = questions.get(str(qno))
        if not q:
            continue
        marks = qconf.get("answer", [])
        if _check_answer(q, marks):
            pts = q.score
        else:
            pts = 0
        s = Score.query.filter_by(paper_id=paper.id, question_id=q.id, teacher_id=operator_id).first()
        if s:
            s.score = pts
        else:
            db.session.add(Score(paper_id=paper.id, question_id=q.id, teacher_id=operator_id, score=pts))
    db.session.commit()


def _check_answer(q, marks):
    if q.type == "single":
        return marks == [q.answer]
    if q.type == "judge":
        return marks == [q.answer]
    if q.type == "multi":
        return set(marks) == set(q.answer)
    return False


def _load_json(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None
