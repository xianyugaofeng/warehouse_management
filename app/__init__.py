from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from app.config import config
from flask import url_for, redirect

# 初始化扩展
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'  # 登录跳转视图
migrate = Migrate()

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # 绑定扩展
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    from app.views.user_manage import user_bp
    from app.views.auth import auth as auth_bp
    from app.views.inbound_manage import inbound_bp
    from app.views.outbound_manage import outbound_bp
    from app.views.inventory_manage import inventory_bp
    from app.views.product_manage import product_bp
    from app.views.report import report_bp

    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(inbound_bp, url_prefix='/inbound')
    app.register_blueprint(outbound_bp, url_prefix='/outbound')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(product_bp, url_prefix='/product')
    app.register_blueprint(report_bp, url_prefix='/report')

    # 注册根路由
    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))
    return app
