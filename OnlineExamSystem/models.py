from flask_login import UserMixin
from database import db


class User(UserMixin, db.Model):
    """用户表: super_admin / admin / teacher / student"""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    role = db.Column(db.String(32), nullable=False, default="student")

    @property
    def role_name(self):
        return {
            "super_admin": "超级管理员",
            "admin": "管理员",
            "teacher": "教师",
            "student": "学生",
        }.get(self.role, self.role)


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    student_no = db.Column(db.String(32), unique=True, nullable=False)
    name = db.Column(db.String(64), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    user = db.relationship("User")


class Teacher(db.Model):
    __tablename__ = "teachers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    user = db.relationship("User")


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)


class Exam(db.Model):
    __tablename__ = "exams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    exam_date = db.Column(db.String(32))
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"))
    subject = db.relationship("Subject")
    # draft / configuring / checking / finished / published
    status = db.Column(db.String(32), default="draft")
    double_check = db.Column(db.Boolean, default=False)
    double_threshold = db.Column(db.Float, default=5.0)

    exam_students = db.relationship("ExamStudent", backref="exam", cascade="all, delete-orphan")
    questions = db.relationship("Question", backref="exam", cascade="all, delete-orphan")
    template = db.relationship("Template", uselist=False, backref="exam", cascade="all, delete-orphan")
    papers = db.relationship("Paper", backref="exam", cascade="all, delete-orphan")
    results = db.relationship("Result", backref="exam", cascade="all, delete-orphan")

    @property
    def status_name(self):
        return {
            "draft": "草稿",
            "configuring": "配置中",
            "checking": "阅卷中",
            "finished": "已结束",
            "published": "已发布",
        }.get(self.status, self.status)

    @property
    def student_list(self):
        return [es.student for es in self.exam_students]


class ExamStudent(db.Model):
    __tablename__ = "exam_students"

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"))
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"))
    student = db.relationship("Student")


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"))
    question_no = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(16), nullable=False)  # single / multi / judge / subjective
    answer = db.Column(db.String(16))
    score = db.Column(db.Float, default=0)
    area = db.Column(db.Text)  # 坐标 JSON {"x1":..,"y1":..,"x2":..,"y2":..}

    @property
    def type_name(self):
        return {
            "single": "单选",
            "multi": "多选",
            "judge": "判断",
            "subjective": "主观题",
        }.get(self.type, self.type)


class Template(db.Model):
    __tablename__ = "templates"

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"))
    image = db.Column(db.String(256))
    back_image = db.Column(db.String(256))
    front_area = db.Column(db.Text)      # 正面区域坐标 JSON
    back_area = db.Column(db.Text)       # 反面区域坐标 JSON（可空）
    barcode_area = db.Column(db.Text)    # 准考证区域坐标 JSON
    objective_area = db.Column(db.Text)  # 客观题每题区域 JSON
    subjective_area = db.Column(db.Text) # 主观题每题区域 JSON


class Paper(db.Model):
    __tablename__ = "papers"

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"))
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"))
    student = db.relationship("Student")
    image = db.Column(db.String(256))
    back_image = db.Column(db.String(256))
    # waiting / checking / finished
    status = db.Column(db.String(32), default="waiting")
    recognized_answer = db.Column(db.Text)  # 客观题识别结果 JSON {qno: [选项...]}


class Score(db.Model):
    __tablename__ = "scores"

    id = db.Column(db.Integer, primary_key=True)
    paper_id = db.Column(db.Integer, db.ForeignKey("papers.id"))
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"))
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    teacher = db.relationship("User")
    score = db.Column(db.Float, default=0)


class Annotation(db.Model):
    __tablename__ = "annotations"

    id = db.Column(db.Integer, primary_key=True)
    paper_id = db.Column(db.Integer, db.ForeignKey("papers.id"))
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"))
    data = db.Column(db.Text)  # SVG / JSON 批注数据


class Result(db.Model):
    __tablename__ = "results"

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"))
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"))
    student = db.relationship("Student")
    score = db.Column(db.Float, default=0)
    objective_score = db.Column(db.Float, default=0)
    subjective_score = db.Column(db.Float, default=0)
