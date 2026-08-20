from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from models import Exam, Paper, Result, Student, Teacher, User, db
from permission import role_required
from services.score_service import calculate_exam_results, compute_paper_score, export_exam_excel
from services.exam_service import save_upload
from config import Config

student_bp = Blueprint("student", __name__)


@student_bp.route("/")
@login_required
@role_required("student")
def results():
    me = Student.query.filter_by(user_id=current_user.id).first()
    if not me:
        flash("当前账号未关联学生信息", "danger")
        return render_template("student/results.html", items=[])

    items = []
    results = Result.query.filter_by(student_id=me.id).all()
    for r in results:
        exam = Exam.query.get(r.exam_id)
        if not exam:
            continue
        paper = Paper.query.filter_by(exam_id=exam.id, student_id=me.id).first()
        items.append({
            "exam": exam,
            "result": r,
            "paper": paper,
        })
    return render_template("student/results.html", me=me, items=items)


@student_bp.route("/result/<int:paper_id>")
@login_required
@role_required("student")
def result_detail(paper_id):
    me = Student.query.filter_by(user_id=current_user.id).first()
    paper = Paper.query.get_or_404(paper_id)
    if not me or paper.student_id != me.id:
        abort(403)

    exam = paper.exam
    total, per_q, obj, sub = compute_paper_score(paper)
    detail = []
    for q in sorted(exam.questions, key=lambda x: x.question_no):
        detail.append({
            "question": q,
            "score": round(per_q.get(q.id, 0), 2),
        })

    from models import Annotation
    ann = Annotation.query.filter_by(paper_id=paper.id, question_id=0).first()
    annotation_data = ann.data if ann and ann.data else "[]"
    recognized = {}
    if paper.recognized_answer:
        import json
        try:
            recognized = json.loads(paper.recognized_answer) or {}
        except Exception:
            recognized = {}
    return render_template("student/detail.html", paper=paper, exam=exam,
                           total=total, obj=obj, sub=sub, detail=detail,
                           annotation_data=annotation_data,
                           recognized=recognized)
