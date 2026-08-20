"""端到端功能测试：登录→建考试→模板→设置→上传→识别→阅卷→成绩"""
import json
import os
import sys
import requests

BASE = "http://127.0.0.1:8000"
ASSETS = os.path.join(os.path.dirname(__file__), "assets")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(("[PASS] " if cond else "[FAIL] ") + name + (f"  {extra}" if extra else ""))


# ---------- 准备数据库中的科目/学生 ----------
from app import app as flask_app
from models import Subject, Student

with flask_app.app_context():
    subj = Subject.query.filter_by(name="数学").first()
    students = [s for s in Student.query.order_by(Student.id).all()]
    subject_id = subj.id
    student_ids = [s.id for s in students]
    print("DB: subject_id=%s students=%s" % (subject_id, student_ids))

s = requests.Session()


def login(username, password):
    r = s.post(BASE + "/login", data={"username": username, "password": password})
    return r


# ---------- 1. 管理员登录 ----------
r = login("admin", "123456")
check("管理员登录", r.status_code == 200 and len(s.cookies) > 0)

r = s.get(BASE + "/admin/")
check("控制台页面", r.status_code == 200 and "控制台" in r.text)
r = s.get(BASE + "/admin/users")
check("用户管理页面", r.status_code == 200 and "用户管理" in r.text)

# ---------- 2. 创建考试 ----------
r = s.post(BASE + "/admin/exams/create", data={
    "name": "测试考试", "exam_date": "2026-08-19",
    "subject_id": str(subject_id),
    "student_ids": [str(x) for x in student_ids],
})
check("创建考试", r.status_code == 200 and "考试创建成功" in r.text)

r = s.get(BASE + "/admin/exams")
check("考试列表", r.status_code == 200 and "测试考试" in r.text)

with flask_app.app_context():
    from models import Exam
    exam = Exam.query.order_by(Exam.id.desc()).first()
    exam_id = exam.id
print("Exam ID:", exam_id)

# ---------- 3. 上传模板 ----------
with open(os.path.join(ASSETS, "template.png"), "rb") as f:
    r = s.post(BASE + f"/admin/exam/{exam_id}/upload_template",
               files={"front_image": ("template.png", f, "image/png")})
check("上传模板图", r.status_code == 200 and "模板图片上传成功" in r.text)

# ---------- 4. 保存模板配置 ----------
digit_areas = []
for i in range(3):
    y1 = 90 + i * 170
    digit_areas.append({"area": {"x1": 60, "y1": y1, "x2": 120, "y2": y1 + 140}})


def opt_area(y, j):
    x1 = 150 + j * 85
    return {"x1": x1, "y1": y, "x2": x1 + 70, "y2": y + 55}


objective_area = {
    "1": {"type": "single", "options": {c: opt_area(730, j) for j, c in enumerate("ABCD")}},
    "2": {"type": "single", "options": {c: opt_area(830, j) for j, c in enumerate("ABCD")}},
    "3": {"type": "judge", "options": {"对": opt_area(930, 0), "错": opt_area(930, 1)}},
}
subjective_area = {
    "4": {"area": {"x1": 150, "y1": 600, "x2": 680, "y2": 700}},
}

tpl_payload = {
    "front_area": {"x1": 0, "y1": 0, "x2": 800, "y2": 1000},
    "back_area": None,
    "barcode_area": {"mode": "digits", "digits": digit_areas},
    "objective_area": objective_area,
    "subjective_area": subjective_area,
}
r = s.post(BASE + f"/admin/exam/{exam_id}/save_template", json=tpl_payload)
check("保存模板配置", r.status_code == 200 and r.json().get("ok"))

# ---------- 5. 保存阅卷设置 ----------
r = s.get(BASE + f"/admin/exam/{exam_id}/settings")
check("阅卷设置页面", r.status_code == 200 and "客观题答案与分值" in r.text)

r = s.post(BASE + f"/admin/exam/{exam_id}/save_settings", data={
    "answer_1": "A", "score_1": "2",
    "answer_2": "C", "score_2": "2",
    "answer_3": "对", "score_3": "3",
    "sub_score_4": "10",
})
check("保存阅卷设置", r.status_code == 200 and "阅卷设置已保存" in r.text)

# ---------- 6. 上传答卷 ----------
with open(os.path.join(ASSETS, "paper1.png"), "rb") as f:
    r = s.post(BASE + f"/admin/exam/{exam_id}/upload_papers",
               files=[("papers", ("paper1.png", f, "image/png"))])
check("上传答卷", r.status_code == 200 and "成功上传 1 张答卷" in r.text)

# ---------- 7. 执行识别 ----------
r = s.post(BASE + f"/admin/exam/{exam_id}/recognize")
check("执行识别", r.status_code == 200 and "识别完成" in r.text)

with flask_app.app_context():
    from models import Paper, Score, Question
    paper = Paper.query.filter_by(exam_id=exam_id).first()
    check("识别匹配学生(001 张三)", paper.student_id == student_ids[0],
          f"student_id={paper.student_id}")
    rec = json.loads(paper.recognized_answer or "{}")
    check("识别客观题 Q1=A", rec.get("1", {}).get("answer") == ["A"], str(rec.get("1")))
    check("识别客观题 Q2=C", rec.get("2", {}).get("answer") == ["C"], str(rec.get("2")))
    check("识别客观题 Q3=对", rec.get("3", {}).get("answer") == ["对"], str(rec.get("3")))
    scores = {sc.question_id: sc.score for sc in Score.query.filter_by(paper_id=paper.id).all()}
    qmap = {q.question_no: q.id for q in Question.query.filter_by(exam_id=exam_id).all()}
    check("客观题自动评分 Q1=2,Q2=2,Q3=3",
          scores.get(qmap.get(1)) == 2 and scores.get(qmap.get(2)) == 2 and scores.get(qmap.get(3)) == 3,
          str(scores))
    paper_id = paper.id
    subjective_qid = qmap.get(4)
print("Paper ID:", paper_id, "subjective_qid:", subjective_qid)

# ---------- 8. 教师阅卷 ----------
s2 = requests.Session()
r = s2.post(BASE + "/login", data={"username": "teacher1", "password": "123456"})
check("教师登录", r.status_code == 200 and len(s2.cookies) > 0)

r = s2.get(BASE + "/teacher/")
check("教师阅卷台", r.status_code == 200 and "在线阅卷" in r.text)
r = s2.get(BASE + f"/teacher/exam/{exam_id}")
check("教师答卷列表", r.status_code == 200 and "去阅卷" in r.text)
r = s2.get(BASE + f"/teacher/mark/{paper_id}")
check("教师阅卷页面", r.status_code == 200 and "第 1 题" in r.text)

r = s2.get(BASE + f"/teacher/subjective/{paper_id}/4")
check("主观题区域图片", r.status_code == 200 and r.headers.get("Content-Type", "").startswith("image/"))

r = s2.post(BASE + "/teacher/save_score", json={
    "paper_id": paper_id, "question_id": subjective_qid, "score": 7,
})
check("保存主观题评分 7 分", r.status_code == 200 and r.json().get("ok"))

r = s2.post(BASE + "/teacher/save_annotation", json={
    "paper_id": paper_id, "question_id": 0,
    "data": json.dumps([{"type": "tick", "x1": 100, "y1": 100, "x2": 200, "y2": 200}]),
})
check("保存批注", r.status_code == 200 and r.json().get("ok"))

# ---------- 9. 结束阅卷并查看成绩 ----------
r = s.post(BASE + f"/admin/exam/{exam_id}/finish")
check("结束阅卷", r.status_code == 200 and "阅卷已结束" in r.text)
r = s.get(BASE + f"/admin/exam/{exam_id}/scores")
check("成绩页面", r.status_code == 200 and "成绩表" in r.text
      and ("张三" in r.text or "李四" in r.text))

with flask_app.app_context():
    from models import Result
    res = Result.query.filter_by(exam_id=exam_id, student_id=student_ids[0]).first()
    check("总分=14 (2+2+3+7)", res and res.score == 14, f"score={res.score if res else None}")

# ---------- 10. 发布并学生查看 ----------
r = s.post(BASE + f"/admin/exam/{exam_id}/publish")
check("发布成绩", r.status_code == 200 and "成绩已发布" in r.text)

s3 = requests.Session()
r = s3.post(BASE + "/login", data={"username": "001", "password": "123456"})
check("学生登录", r.status_code == 200 and len(s3.cookies) > 0)
r = s3.get(BASE + "/student/")
check("学生成绩列表", r.status_code == 200 and "测试考试" in r.text)
r = s3.get(BASE + f"/student/result/{paper_id}")
check("学生查看答题卡详情", r.status_code == 200 and "逐题得分" in r.text)

# ---------- 11. 导出 Excel ----------
r = s.get(BASE + f"/admin/exam/{exam_id}/export")
check("导出 Excel", r.status_code == 200 and
      "spreadsheetml" in r.headers.get("Content-Type", ""))

# ---------- 权限控制 ----------
r = s3.get(BASE + "/admin/")
check("学生访问管理员页面被拒", r.status_code == 403)
r = s3.get(BASE + "/teacher/")
check("学生访问教师页面被拒", r.status_code == 403)

# ---------- 汇总 ----------
passed = sum(1 for _, ok in results if ok)
print("\n===== 测试结果: %d/%d 通过 =====" % (passed, len(results)))
if passed != len(results):
    for name, ok in results:
        if not ok:
            print("  FAILED:", name)
    sys.exit(1)
