import os
from dotenv import load_dotenv

load_dotenv()

# 基础配置
class Config:
    # Flask安全密钥（使用随机生成更安全）
    SECRET_KEY = os.environ.get("SECRET_KEY") or "lkrq43E<S-@"

    # 数据库配置
    BASEDIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(
        BASEDIR, "database/babycare.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # OPENAI Compatible API配置
    OPENAI_API_ENDPOINT = os.getenv("OPENAI_API_ENDPOINT", "https://api.openai.com/v1")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    # 定时任务配置
    SCHEDULER_API_ENABLED = True
    JOBS = [
        {
            "id": "daily_report",
            "func": "app:generate_daily_report",
            "trigger": "cron",
            "hour": 20,
            "minute": 0,
        }
    ]

    # 时区设置（根据实际需求调整）
    TIMEZONE = "United Kingdom/London"

    # 调试模式配置（生产环境应设为False）
    DEBUG = True


# 不同环境配置继承
class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}


class DevelopmentConfig(Config):
    pass
