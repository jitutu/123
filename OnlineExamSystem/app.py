import os
from flask import Flask, redirect, url_for
from flask_login import current_user
from config import Config
from database import db, login_manager
from models import User, Subject, Student, Teacher


def seed_data():
    """初始化默认账号与科目"""
    if User.query.count() == 0:
        db.session.add_all([
            User(username="admin", password="123456", name="系统管理员", role="super_admin"),
            User(username="manager", password="123456", name="考务管理员", role="admin"),
        ])
    if Subject.query.count() == 0:
        db.session.add_all([Subject(name=n) for n in ("数学", "英语", "语文")])
    if Teacher.query.count() == 0 and not User.query.filter_by(username="teacher1").first():
        u = User(username="teacher1", password="123456", name="王老师", role="teacher")
        db.session.add(u)
        db.session.flush()
        db.session.add(Teacher(name=u.name, user_id=u.id))
    if Student.query.count() == 0:
        for no, nm in (("001", "张三"), ("002", "李四")):
            u = User(username=no, password="123456", name=nm, role="student")
            db.session.add(u)
            db.session.flush()
            db.session.add(Student(student_no=no, name=nm, user_id=u.id))
    db.session.commit()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    for folder in (Config.TEMPLATE_FOLDER, Config.PAPERS_FOLDER, Config.BACKUP_FOLDER):
        os.makedirs(folder, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.teacher import teacher_bp
    from routes.student import student_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(teacher_bp, url_prefix="/teacher")
    app.register_blueprint(student_bp, url_prefix="/student")

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        db.create_all()
        seed_data()

    def _home(role):
        return {
            "super_admin": "admin.dashboard",
            "admin": "admin.dashboard",
            "teacher": "teacher.dashboard",
            "student": "student.results",
        }.get(role, "auth.login")

    @app.route("/")
    def index():
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        return redirect(url_for(_home(current_user.role)))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
