import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    LOW_STOCK_ALERT_EMAILS = [
        email.strip()
        for email in os.environ.get("LOW_STOCK_ALERT_EMAILS", "").split(",")
        if email.strip()
    ]


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-only-secret-key"
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL")
