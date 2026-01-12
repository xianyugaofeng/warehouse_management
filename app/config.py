import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'
    DEBUG = False
    # 数据库配置(MYSQL)
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:123456@localhost/warehouse_db'
    # 设置 Flask-SQLAlchemy 扩展连接数据库的连接字符串（URI）
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # 配置 Flask-SQLAlchemy 是否追踪对象的修改并发出信号

    # 分页配置
    PER_PAGE = 10

    # 库存预警阈值
    DEFAULT_WARNING_STOCK = 10

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