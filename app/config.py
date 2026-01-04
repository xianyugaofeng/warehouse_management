import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'
    DEBUG = False


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'default': Config,
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    # 配置安全会话
    'SESSION_COOKIE_SECURE': True,  # 仅HTTPS
    'SESSION_COOKIE_HTTPONLY': True,  # 防止JavaScript访问
    'SESSION_COOKIE_SAMESITE': 'Lax'  # CSRF防护
}