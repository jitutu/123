"""考试管理服务"""
import os
import uuid

from config import Config
from database import db
from models import Exam, ExamStudent, Subject, Template, Question


def allowed_image(filename):
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in Config.ALLOWED_IMAGE_EXTENSIONS


def save_upload(file, folder):
    """保存上传图片, 返回文件名; 不合法返回 None"""
    if not file or not allowed_image(file.filename):
        return None
    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(folder, filename))
    return filename


def create_exam(name, exam_date, subject_id, student_ids):
    exam = Exam(name=name, exam_date=exam_date, subject_id=subject_id, status="configuring")
    db.session.add(exam)
    db.session.flush()
    for sid in student_ids:
        db.session.add(ExamStudent(exam_id=exam.id, student_id=sid))
    db.session.commit()
    return exam


def get_or_create_template(exam):
    if not exam.template:
        tpl = Template(exam_id=exam.id)
        db.session.add(tpl)
        db.session.commit()
        db.session.refresh(exam)
    return exam.template


def sync_questions_from_settings(exam, objective_data, subjective_data):
    """根据阅卷设置同步题目表（答案/分值/坐标）"""
    existing = {q.question_no: q for q in exam.questions}
    used = set()

    for qno, cfg in objective_data.items():
        used.add(int(qno))
        q = existing.get(int(qno))
        if not q:
            q = Question(exam_id=exam.id, question_no=int(qno))
            db.session.add(q)
        q.type = cfg.get("type", "single")
        q.answer = cfg.get("answer", "")
        q.score = float(cfg.get("score", 0))
        q.area = cfg.get("area")

    for qno, cfg in subjective_data.items():
        used.add(int(qno))
        q = existing.get(int(qno))
        if not q:
            q = Question(exam_id=exam.id, question_no=int(qno))
            db.session.add(q)
        q.type = "subjective"
        q.answer = None
        q.score = float(cfg.get("score", 0))
        q.area = cfg.get("area")

    for qno, q in list(existing.items()):
        if qno not in used:
            db.session.delete(q)
    db.session.commit()
