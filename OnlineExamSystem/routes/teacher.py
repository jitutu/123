import io
import json
import os

from flask import (Blueprint, abort, flash, jsonify, redirect, render_template,
                   request, send_file, url_for)
from flask_login import current_user, login_required
from models import Annotation, Exam, Paper, Question, Score, db
from permission import role_required
from services.score_service import compute_paper_score

teacher_bp = Blueprint("teacher", __name__)


@teacher_bp.route("/")
@login_required
@role_required("teacher")
def dashboard():
    exams = Exam.query.filter(Exam.status.in_(["configuring", "checking", "finished"])).order_by(Exam.id.desc()).all()
    return render_template("teacher/dashboard.html", exams=exams)


@teacher_bp.route("/exam/<int:exam_id>")
@login_required
@role_required("teacher")
def exam_papers(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    papers = sorted(exam.papers, key=lambda p: (p.status != "waiting", p.id))
    return render_template("teacher/exam_papers.html", exam=exam, papers=papers)


@teacher_bp.route("/mark/<int:paper_id>")
@login_required
@role_required("teacher")
def mark(paper_id):
    paper = Paper.query.get_or_404(paper_id)
    exam = paper.exam
    if paper.status == "waiting":
        paper.status = "checking"
        db.session.commit()

    questions = sorted(exam.questions, key=lambda q: q.question_no)
    scores = Score.query.filter_by(paper_id=paper.id).all()
    score_map = {}
    for s in scores:
        score_map.setdefault(s.question_id, []).append({
            "id": s.id, "teacher": s.teacher.name if s.teacher else "系统",
            "score": s.score,
        })

    my_scores = {s.question_id: s.score for s in scores if s.teacher_id == current_user.id}

    recognized = {}
    if paper.recognized_answer:
        try:
            recognized = json.loads(paper.recognized_answer) or {}
        except Exception:
            recognized = {}

    ann = Annotation.query.filter_by(paper_id=paper.id, question_id=0).first()
    annotation_data = ann.data if ann and ann.data else "[]"
    return render_template("teacher/mark.html", paper=paper, exam=exam,
                           questions=questions, score_map=score_map,
                           my_scores=my_scores, current_teacher=current_user,
                           recognized=json.dumps(recognized, ensure_ascii=False),
                           annotation_data=annotation_data)


@teacher_bp.route("/save_score", methods=["POST"])
@login_required
@role_required("teacher")
def save_score():
    data = request.get_json()
    paper_id = int(data["paper_id"])
    question_id = int(data["question_id"])
    score = float(data["score"])

    s = Score.query.filter_by(paper_id=paper_id, question_id=question_id,
                              teacher_id=current_user.id).first()
    if s:
        s.score = score
    else:
        db.session.add(Score(paper_id=paper_id, question_id=question_id,
                             teacher_id=current_user.id, score=score))
    db.session.commit()

    paper = Paper.query.get(paper_id)
    if paper and paper.status == "checking":
        _update_paper_status(paper)
    return jsonify(ok=True)


def _update_paper_status(paper):
    """所有主观题都有评分则标记完成"""
    questions = [q for q in paper.exam.questions if q.type == "subjective"]
    if not questions:
        paper.status = "finished"
        db.session.commit()
        return
    scored = set()
    for q in questions:
        if Score.query.filter_by(paper_id=paper.id, question_id=q.id).first():
            scored.add(q.id)
    if all(q.id in scored for q in questions):
        paper.status = "finished"
        db.session.commit()


@teacher_bp.route("/save_annotation", methods=["POST"])
@login_required
@role_required("teacher")
def save_annotation():
    data = request.get_json()
    paper_id = int(data["paper_id"])
    question_id = int(data["question_id"])
    payload = data.get("data", "")

    ann = Annotation.query.filter_by(paper_id=paper_id, question_id=question_id).first()
    if ann:
        ann.data = payload
    else:
        db.session.add(Annotation(paper_id=paper_id, question_id=question_id, data=payload))
    db.session.commit()
    return jsonify(ok=True)


@teacher_bp.route("/subjective/<int:paper_id>/<int:qno>")
@login_required
@role_required("teacher")
def subjective_image(paper_id, qno):
    """返回主观题答题区域切割图片"""
    from config import Config
    from recognition import omr

    paper = Paper.query.get_or_404(paper_id)
    tpl = paper.exam.template
    if not tpl or not tpl.image:
        abort(404)
    sub_area = json.loads(tpl.subjective_area or "{}")
    cfg = sub_area.get(str(qno))
    if not cfg or not cfg.get("area"):
        abort(404)

    paper_path = os.path.join(Config.PAPERS_FOLDER, paper.image) if paper.image else None
    tpl_path = os.path.join(Config.TEMPLATE_FOLDER, tpl.image)
    if not paper_path or not os.path.exists(paper_path) or not os.path.exists(tpl_path):
        abort(404)

    try:
        img = omr.load_image(paper_path)
        tpl_img = omr.load_image(tpl_path)
    except Exception:
        abort(404)

    sw = img.shape[1] / tpl_img.shape[1]
    sh = img.shape[0] / tpl_img.shape[0]
    scaled = omr.scale_area(cfg["area"], sw, sh)
    crop = omr.crop(img, scaled)
    if crop is None:
        abort(404)

    import cv2
    ok, buf = cv2.imencode(".png", crop)
    if not ok:
        abort(404)
    return send_file(io.BytesIO(buf.tobytes()), mimetype="image/png")
