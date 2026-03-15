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
    DEFAULT_WARNING_STOCK = 100

    # 盘点任务
    INVENTORY_COUNT_CHECK_INTERVAL = 1
    
    # 盘点容差设置（循环盘点容差，差异在此范围内自动过账）
    INVENTORY_COUNT_TOLERANCE = 5  # ±5件
    
    # 调拨损耗容差设置（合理损耗数量）
    TRANSFER_LOSS_TOLERANCE = 0.02  # 2%的损耗率

class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False

class TestingConfig(Config):
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:123456@localhost/warehouse_db_test'
    # 使用测试数据库

config = {
    'default': Config,
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,  # 添加测试配置
    # 配置安全会话
    'SESSION_COOKIE_SECURE': True,  # 仅HTTPS
    'SESSION_COOKIE_HTTPONLY': True,  # 防止JavaScript访问
    'SESSION_COOKIE_SAMESITE': 'Lax'  # CSRF防护
}