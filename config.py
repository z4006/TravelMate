"""TravelMate 应用配置。"""

import os
from pathlib import Path
from datetime import timedelta


PROJECT_ROOT = Path(__file__).resolve().parent


class BaseConfig:
    """所有环境共享的基础配置。"""

    DATABASE = os.getenv(
        "TRAVELMATE_DATABASE",
        str(PROJECT_ROOT / "database" / "travelmate.db"),
    )
    SECRET_KEY = os.getenv("TRAVELMATE_SECRET_KEY")
    SESSION_COOKIE_NAME = "travelmate_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_REFRESH_EACH_REQUEST = True


class DevelopmentConfig(BaseConfig):
    """本地开发配置。"""

    DEBUG = True
    SECRET_KEY = BaseConfig.SECRET_KEY or "travelmate-development-key"


class TestingConfig(BaseConfig):
    """自动化测试配置。"""

    TESTING = True
    SECRET_KEY = BaseConfig.SECRET_KEY or "travelmate-testing-key"
    DATABASE = ":memory:"


class ProductionConfig(BaseConfig):
    """正式环境配置。正式环境必须显式提供密钥。"""

    DEBUG = False
    # 默认要求 HTTPS；仅在没有证书的临时演示环境才设 TRAVELMATE_COOKIE_SECURE=0
    SESSION_COOKIE_SECURE = os.getenv("TRAVELMATE_COOKIE_SECURE", "1") != "0"

    @classmethod
    def validate(cls) -> None:
        if not cls.SECRET_KEY:
            raise RuntimeError(
                "正式环境必须设置 TRAVELMATE_SECRET_KEY 环境变量。"
            )


CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}