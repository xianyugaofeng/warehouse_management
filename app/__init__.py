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
    from app.views.report import report_bp
    from app.views.inspection_manage import inspection_bp
    from app.views.purchase_manage import purchase_bp
    from app.views.putaway_manage import putaway_bp
    from app.views.return_manage import return_bp
    from app.views.stock_move_manage import stock_move_bp
    # 注册蓝图（这会注册所有蓝图中的路由）
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(inbound_bp, url_prefix='/inbound')
    app.register_blueprint(outbound_bp, url_prefix='/outbound')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(product_bp, url_prefix='/product')
    app.register_blueprint(supplier_bp, url_prefix='/supplier')
    app.register_blueprint(report_bp, url_prefix='/report')
    app.register_blueprint(inspection_bp, url_prefix='/inspection')
    app.register_blueprint(purchase_bp, url_prefix='/purchase')
    app.register_blueprint(putaway_bp, url_prefix='/putaway')
    app.register_blueprint(return_bp, url_prefix='/return')
    app.register_blueprint(stock_move_bp, url_prefix='/stock_move')
    
    # 注册根路由
    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    # 注册index网页
    @app.route('/index')
    def next_page():
        return render_template('base.html')



    return app
