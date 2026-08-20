"""成绩计算、发布与 Excel 导出服务"""
import io
import os
from collections import defaultdict

from flask import send_file

from config import Config
from database import db
from models import Question, Result, Score


def compute_paper_score(paper):
    """计算单卷成绩, 返回 (总分, {question_id: 得分}, 客观分, 主观分)"""
    exam = paper.exam
    questions = {q.id: q for q in exam.questions}
    rows = Score.query.filter_by(paper_id=paper.id).order_by(Score.id).all()
    groups = defaultdict(list)
    for s in rows:
        groups[s.question_id].append(s)

    total, obj, sub = 0.0, 0.0, 0.0
    per_question = {}
    for qid, arr in groups.items():
        q = questions.get(qid)
        if q is None:
            continue
        if exam.double_check and q.type == "subjective" and len(arr) >= 2:
            a, b = arr[-2], arr[-1]
            if abs(a.score - b.score) <= exam.double_threshold:
                v = (a.score + b.score) / 2
            else:
                v = b.score
        else:
            v = arr[-1].score
        per_question[qid] = v
        total += v
        if q.type == "subjective":
            sub += v
        else:
            obj += v
    return round(total, 2), per_question, round(obj, 2), round(sub, 2)


def calculate_exam_results(exam):
    """汇总考试所有答卷成绩写入 results"""
    questions = {q.id: q for q in exam.questions}
    for paper in exam.papers:
        if not paper.student_id:
            continue
        total, per_q, obj, sub = compute_paper_score(paper)
        result = Result.query.filter_by(exam_id=exam.id, student_id=paper.student_id).first()
        if not result:
            db.session.add(Result(exam_id=exam.id, student_id=paper.student_id,
                                  score=total, objective_score=obj, subjective_score=sub))
        else:
            result.score, result.objective_score, result.subjective_score = total, obj, sub
    db.session.commit()


def export_exam_excel(exam):
    """导出成绩 Excel, 返回 send_file 响应"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment

    calculate_exam_results(exam)
    results = {r.student_id: r for r in Result.query.filter_by(exam_id=exam.id).all()}
    students = {}
    for es in exam.exam_students:
        students[es.student_id] = es.student

    wb = Workbook()
    ws = wb.active
    ws.title = "成绩表"
    headers = ["学号", "姓名", "客观题", "主观题", "总分"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    scores = []
    for sid, st in students.items():
        r = results.get(sid)
        total = r.score if r else 0
        obj = r.objective_score if r else 0
        sub = r.subjective_score if r else 0
        ws.append([st.student_no, st.name, obj, sub, total])
        scores.append(total)

    avg_row = ["平均分", "", "", ""]
    avg_row.append(round(sum(scores) / len(scores), 2) if scores else 0)
    ws.append(avg_row)

    for col in ("A", "B", "C", "D", "E"):
        ws.column_dimensions[col].width = 14

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    filename = f"{exam.name}-成绩.xlsx"
    from urllib.parse import quote
    return send_file(buffer, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
