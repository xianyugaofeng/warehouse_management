from flask import Blueprint, request, url_for, redirect, flash, render_template
from flask_login import login_user, logout_user, login_required
from app import db
from app.models.user import User
from app.utils.helpers import generate_inbound_no

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():           #  auth.login视图函数\
    # 这里的代码只有用户访问/auth/login时才会执行
    if request.method == 'POST':
        username = request.form.get('username')         # 获取表单数据
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'

        user = User.query.filter_by(username=username, is_active=True).first()
        if user and user.check_password(password):       # 密码安全(安全地比较哈希密码)
            # 登录成功
            login_user(user,remember=remember)
            next_page = request.args.get('next')       # 获取next的参数值 /login?next=
            # 跳转到next参数指定的页面，如果没有则跳转到默认页面
            return redirect(next_page or url_for('next_page'))    # next_page视图函数对应默认页面
            """next_page端点函数没有定义"""
        else:
            flash('用户名或密码错误,或账号未激活', 'danger' )

    return render_template('auth/login.html')    # GET请求或POST请求失败，渲染登录模板

