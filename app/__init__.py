from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from app.config import config
from flask import url_for, redirect
import atexit

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
    from app.views.supplier_manage import supplier_bp
    from app.views.inventory_count_manage import inventory_count_bp
    from app.views.report import report_bp
    # 注册蓝图（这会注册所有蓝图中的路由）
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(inbound_bp, url_prefix='/inbound')
    app.register_blueprint(outbound_bp, url_prefix='/outbound')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(product_bp, url_prefix='/product')
    app.register_blueprint(supplier_bp, url_prefix='/supplier')
    app.register_blueprint(report_bp, url_prefix='/report')
    app.register_blueprint(inventory_count_bp, url_prefix='/inventory_count')
    
    # 注册根路由
    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    # 注册index网页
    @app.route('/index')
    def next_page():
        return render_template('base.html')

    # 导入调度器（移到这里避免循环导入）
    from app.utils.scheduler import start_scheduler, stop_scheduler
    
    # 只有当不是在执行 Flask 命令且不是在测试模式时才启动调度器
    # 这样在运行数据库迁移命令或测试时就不会尝试访问不存在的表
    import sys
    if 'flask' not in sys.argv[0] and 'db' not in sys.argv and not app.config.get('TESTING', False):
        # 启动调度器
        with app.app_context():
            start_scheduler()

        # 注册应用关闭时的清理函数
        atexit.register(stop_scheduler)

    return app
