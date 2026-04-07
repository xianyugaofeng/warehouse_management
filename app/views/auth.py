import pymysql
from flask import Blueprint, request, url_for, redirect, flash, render_template
from flask_login import login_user, logout_user, login_required
from app import db
from app.models.user import User
from app.utils.helpers import generate_inbound_no

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():           #  auth/login绑定auth.login视图函数
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
            return redirect(next_page or url_for('index'))    # index视图函数对应默认页面
        else:
            flash('用户名或密码错误,或账号未激活', 'danger' )

    return render_template('auth/login.html')    # GET请求或POST请求失败，渲染登录模板


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已成功退出登录', 'success')
    return redirect(url_for('auth.login'))

@auth.route('/register', methods=['GET', 'POST'])
def register():
    # 仅管理员可访问
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        real_name = request.form.get('real_name')
        phone = request.form.get('phone')
        email = request.form.get('email')

        # 检查用户名是否已存在
        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'danger')

        # 创建新用户
        user = User(
            username=username,
            real_name=real_name,
            phone=phone,
            email=email
        )
        try:
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
        except pymysql.err.IntegrityError:
            flash('账号已存在', 'danger')
        flash('注册成功,请联系管理员分配角色', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')   # GET请求
