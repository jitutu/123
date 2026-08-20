import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "exam_system")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "database", "exam.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    TEMPLATE_FOLDER = os.path.join(BASE_DIR, "uploads", "templates")
    PAPERS_FOLDER = os.path.join(BASE_DIR, "uploads", "papers")
    BACKUP_FOLDER = os.path.join(BASE_DIR, "uploads", "backup")

    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png"}
