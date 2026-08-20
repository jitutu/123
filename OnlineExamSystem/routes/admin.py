import json
import os

from flask import (Blueprint, abort, flash, jsonify, redirect,
                   render_template, request, send_from_directory, url_for)
from flask_login import current_user, login_required
from models import (Exam, ExamStudent, Paper, Question, Result, Score,
                    Student, Subject, Teacher, Template, User, db)
from permission import role_required
from services.exam_service import (create_exam, get_or_create_template,
                                   save_upload, sync_questions_from_settings)
from services.recognize import recognize_paper
from services.score_service import calculate_exam_results, export_exam_excel
from config import Config

admin_bp = Blueprint("admin", __name__)


def _tpl(exam):
    return get_or_create_template(exam)


# ---------------- 图片访问 ----------------
@admin_bp.route("/paper_image/<int:paper_id>/<side>")
@login_required
def paper_image(paper_id, side):
    paper = Paper.query.get_or_404(paper_id)
    fn = paper.image if side == "front" else paper.back_image
    if not fn:
        abort(404)
    return send_from_directory(Config.PAPERS_FOLDER, fn)


@admin_bp.route("/template_image/<int:exam_id>/<side>")
@login_required
def template_image(exam_id, side):
    tpl = Exam.query.get_or_404(exam_id).template
    if not tpl:
        abort(404)
    fn = tpl.image if side == "front" else tpl.back_image
    if not fn:
        abort(404)
    return send_from_directory(Config.TEMPLATE_FOLDER, fn)


# ---------------- 首页 ----------------
@admin_bp.route("/")
@login_required
@role_required("super_admin", "admin")
def dashboard():
    exams = Exam.query.order_by(Exam.id.desc()).all()
    stats = {
        "exams": len(exams),
        "teachers": Teacher.query.count(),
        "students": Student.query.count(),
    }
    return render_template("admin/dashboard.html", exams=exams, stats=stats)


# ---------------- 用户管理 ----------------
@admin_bp.route("/users")
@login_required
@role_required("super_admin", "admin")
def users():
    admins = User.query.filter_by(role="admin").all()
    teachers = User.query.filter_by(role="teacher").all()
    students = User.query.filter_by(role="student").all()
    return render_template("admin/users.html", admins=admins,
                           teachers=teachers, students=students)


@admin_bp.route("/create_teacher", methods=["POST"])
@login_required
@role_required("super_admin", "admin")
def create_teacher():
    username = request.form.get("username", "").strip()
    name = request.form.get("name", "").strip()
    if not username or not name:
        flash("账号和姓名不能为空", "danger")
        return redirect(url_for("admin.users"))
    if User.query.filter_by(username=username).first():
        flash("账号已存在", "danger")
        return redirect(url_for("admin.users"))
    from models import Teacher as TeacherModel
    u = User(username=username, password="123456", name=name, role="teacher")
    db.session.add(u)
    db.session.flush()
    db.session.add(TeacherModel(name=name, user_id=u.id))
    db.session.commit()
    flash(f"教师 {name} 创建成功，默认密码 123456", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/create_student", methods=["POST"])
@login_required
@role_required("super_admin", "admin")
def create_student():
    student_no = request.form.get("student_no", "").strip()
    name = request.form.get("name", "").strip()
    if not student_no or not name:
        flash("学号和姓名不能为空", "danger")
        return redirect(url_for("admin.users"))
    if User.query.filter_by(username=student_no).first() or Student.query.filter_by(student_no=student_no).first():
        flash("学号已存在", "danger")
        return redirect(url_for("admin.users"))
    u = User(username=student_no, password="123456", name=name, role="student")
    db.session.add(u)
    db.session.flush()
    db.session.add(Student(student_no=student_no, name=name, user_id=u.id))
    db.session.commit()
    flash(f"学生 {name} 创建成功，账号=学号，默认密码 123456", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/create_admin", methods=["POST"])
@login_required
@role_required("super_admin")
def create_admin():
    username = request.form.get("username", "").strip()
    name = request.form.get("name", "").strip()
    if not username or not name:
        flash("账号和姓名不能为空", "danger")
        return redirect(url_for("admin.users"))
    if User.query.filter_by(username=username).first():
        flash("账号已存在", "danger")
        return redirect(url_for("admin.users"))
    db.session.add(User(username=username, password="123456", name=name, role="admin"))
    db.session.commit()
    flash(f"管理员 {name} 创建成功，默认密码 123456", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/delete_user/<int:user_id>", methods=["POST"])
@login_required
@role_required("super_admin", "admin")
def delete_user(user_id):
    u = User.query.get_or_404(user_id)
    if u.id == current_user.id:
        flash("不能删除当前登录账号", "danger")
        return redirect(url_for("admin.users"))
    if current_user.role == "admin" and u.role in ("super_admin", "admin"):
        flash("无权限删除该用户", "danger")
        return redirect(url_for("admin.users"))
    if u.role == "teacher":
        Teacher.query.filter_by(user_id=u.id).delete()
    if u.role == "student":
        Student.query.filter_by(user_id=u.id).delete()
    db.session.delete(u)
    db.session.commit()
    flash("用户已删除", "success")
    return redirect(url_for("admin.users"))


# ---------------- 考试管理 ----------------
@admin_bp.route("/exams")
@login_required
@role_required("super_admin", "admin")
def exams():
    exam_list = Exam.query.order_by(Exam.id.desc()).all()
    subjects = Subject.query.all()
    students = Student.query.order_by(Student.student_no).all()
    return render_template("admin/exams.html", exams=exam_list,
                           subjects=subjects, students=students)


@admin_bp.route("/exams/create", methods=["POST"])
@login_required
@role_required("super_admin", "admin")
def create_exam_route():
    name = request.form.get("name", "").strip()
    exam_date = request.form.get("exam_date", "")
    subject_id = request.form.get("subject_id", type=int)
    student_ids = request.form.getlist("student_ids", type=int)
    if not name or not subject_id or not student_ids:
        flash("考试名称、科目和参考学生不能为空", "danger")
        return redirect(url_for("admin.exams"))
    create_exam(name, exam_date, subject_id, student_ids)
    flash("考试创建成功", "success")
    return redirect(url_for("admin.exams"))


@admin_bp.route("/exam/<int:exam_id>")
@login_required
@role_required("super_admin", "admin")
def exam_detail(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    return render_template("admin/exam_detail.html", exam=exam)


# ---------------- 答题卡模板 ----------------
@admin_bp.route("/exam/<int:exam_id>/upload_template", methods=["POST"])
@login_required
@role_required("super_admin", "admin")
def upload_template(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    tpl = _tpl(exam)
    front = request.files.get("front_image")
    back = request.files.get("back_image")
    if front and front.filename:
        fn = save_upload(front, Config.TEMPLATE_FOLDER)
        if fn:
            tpl.image = fn
    if back and back.filename:
        fn = save_upload(back, Config.TEMPLATE_FOLDER)
        if fn:
            tpl.back_image = fn
    if exam.status == "draft":
        exam.status = "configuring"
    db.session.commit()
    flash("模板图片上传成功，请进行区域框选配置", "success")
    return redirect(url_for("admin.template_config", exam_id=exam_id))


@admin_bp.route("/exam/<int:exam_id>/template")
@login_required
@role_required("super_admin", "admin")
def template_config(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    tpl = _tpl(exam)
    return render_template("admin/template_config.html", exam=exam, tpl=tpl)


@admin_bp.route("/exam/<int:exam_id>/save_template", methods=["POST"])
@login_required
@role_required("super_admin", "admin")
def save_template(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    tpl = _tpl(exam)
    data = request.get_json()
    tpl.front_area = json.dumps(data.get("front_area"), ensure_ascii=False)
    tpl.back_area = json.dumps(data.get("back_area"), ensure_ascii=False)
    tpl.barcode_area = json.dumps(data.get("barcode_area"), ensure_ascii=False)
    tpl.objective_area = json.dumps(data.get("objective_area"), ensure_ascii=False)
    tpl.subjective_area = json.dumps(data.get("subjective_area"), ensure_ascii=False)
    if exam.status == "configuring":
        exam.status = "configuring"
    db.session.commit()
    return jsonify(ok=True)


# ---------------- 阅卷设置 ----------------
@admin_bp.route("/exam/<int:exam_id>/settings")
@login_required
@role_required("super_admin", "admin")
def settings(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    tpl = _tpl(exam)
    objective_area = json.loads(tpl.objective_area or "{}")
    subjective_area = json.loads(tpl.subjective_area or "{}")
    qmap = {q.question_no: q for q in exam.questions}
    objectives = []
    for qno, cfg in sorted(objective_area.items(), key=lambda x: int(x[0])):
        q = qmap.get(int(qno))
        objectives.append({
            "qno": qno,
            "type": cfg.get("type", "single"),
            "answer": q.answer if q else "",
            "score": q.score if q else 0,
        })
    subjectives = []
    for qno, cfg in sorted(subjective_area.items(), key=lambda x: int(x[0])):
        q = qmap.get(int(qno))
        subjectives.append({
            "qno": qno,
            "score": q.score if q else (cfg.get("score", 0) if isinstance(cfg, dict) else 0),
        })
    return render_template("admin/settings.html", exam=exam,
                           objectives=objectives, subjectives=subjectives,
                           double_check=exam.double_check,
                           double_threshold=exam.double_threshold)


@admin_bp.route("/exam/<int:exam_id>/save_settings", methods=["POST"])
@login_required
@role_required("super_admin", "admin")
def save_settings(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    tpl = _tpl(exam)
    objective_area = json.loads(tpl.objective_area or "{}")
    subjective_area = json.loads(tpl.subjective_area or "{}")

    objective_data = {}
    for qno, cfg in objective_area.items():
        answer = request.form.get(f"answer_{qno}", "").strip()
        score = request.form.get(f"score_{qno}", type=float, default=0)
        if not answer and request.form.get(f"score_{qno}") is None:
            continue
        objective_data[qno] = {
            "type": cfg.get("type", "single"),
            "answer": answer,
            "score": score or 0,
            "area": json.dumps(cfg, ensure_ascii=False),
        }

    subjective_data = {}
    for qno, cfg in subjective_area.items():
        score = request.form.get(f"sub_score_{qno}", type=float, default=0)
        subjective_data[qno] = {
            "score": score or 0,
            "area": json.dumps(cfg, ensure_ascii=False),
        }

    sync_questions_from_settings(exam, objective_data, subjective_data)

    double = request.form.get("double_check") == "on"
    threshold = request.form.get("double_threshold", type=float, default=5)
    exam.double_check = double
    exam.double_threshold = threshold if threshold else 5
    if exam.status == "configuring":
        exam.status = "checking"
    db.session.commit()
    flash("阅卷设置已保存", "success")
    return redirect(url_for("admin.exam_detail", exam_id=exam_id))


# ---------------- 上传答卷与识别 ----------------
@admin_bp.route("/exam/<int:exam_id>/upload_papers", methods=["POST"])
@login_required
@role_required("super_admin", "admin")
def upload_papers(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    files = request.files.getlist("papers")
    count = 0
    for f in files:
        if not f or not f.filename:
            continue
        fn = save_upload(f, Config.PAPERS_FOLDER)
        if fn:
            db.session.add(Paper(exam_id=exam.id, image=fn, status="waiting"))
            count += 1
    db.session.commit()
    flash(f"成功上传 {count} 张答卷", "success")
    return redirect(url_for("admin.exam_detail", exam_id=exam_id))


@admin_bp.route("/exam/<int:exam_id>/recognize", methods=["POST"])
@login_required
@role_required("super_admin", "admin")
def recognize(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    papers = [p for p in exam.papers if not p.student_id or p.status == "waiting"]
    matched, failed, objective_done = 0, 0, 0
    errors = []
    for p in papers:
        try:
            result = recognize_paper(exam, p, operator_id=current_user.id)
            if result.get("student_no"):
                matched += 1
            else:
                failed += 1
            if result.get("objective"):
                objective_done += 1
        except Exception as e:
            failed += 1
            errors.append(str(e))
    flash(f"识别完成：匹配学生 {matched} 份，未识别 {failed} 份，客观题识别 {objective_done} 份", "success")
    if errors:
        flash("; ".join(errors[:3]), "warning")
    return redirect(url_for("admin.exam_detail", exam_id=exam_id))


@admin_bp.route("/exam/<int:exam_id>/paper/<int:paper_id>/assign", methods=["POST"])
@login_required
@role_required("super_admin", "admin")
def assign_student(exam_id, paper_id):
    paper = Paper.query.get_or_404(paper_id)
    student_id = request.form.get("student_id", type=int)
    if student_id:
        paper.student_id = student_id
        db.session.commit()
        flash("已为学生关联答卷", "success")
    return redirect(url_for("admin.exam_detail", exam_id=exam_id))


# ---------------- 成绩管理 ----------------
@admin_bp.route("/exam/<int:exam_id>/scores")
@login_required
@role_required("super_admin", "admin")
def scores(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    calculate_exam_results(exam)
    results = Result.query.filter_by(exam_id=exam_id).order_by(Result.score.desc()).all()
    students = {es.student_id: es.student for es in exam.exam_students}
    return render_template("admin/scores.html", exam=exam, results=results, students=students)


@admin_bp.route("/exam/<int:exam_id>/finish", methods=["POST"])
@login_required
@role_required("super_admin", "admin")
def finish_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    calculate_exam_results(exam)
    if exam.status in ("configuring", "checking"):
        exam.status = "finished"
    db.session.commit()
    flash("阅卷已结束，成绩已计算", "success")
    return redirect(url_for("admin.scores", exam_id=exam_id))


@admin_bp.route("/exam/<int:exam_id>/publish", methods=["POST"])
@login_required
@role_required("super_admin", "admin")
def publish_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    calculate_exam_results(exam)
    exam.status = "published"
    db.session.commit()
    flash("成绩已发布，学生可查看", "success")
    return redirect(url_for("admin.scores", exam_id=exam_id))


@admin_bp.route("/exam/<int:exam_id>/export")
@login_required
@role_required("super_admin", "admin")
def export_scores(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    return export_exam_excel(exam)
