from functools import wraps
from flask import redirect, url_for, abort, request    # 返回HTTP错误
from flask_login import current_user          # 当前登录对象


# 权限检查装饰器
def permission_required(permission_name):          # 接收权限名称
    def decorator(f):  # 装饰原函数,接收被装饰函数,可以有多个函数
        @wraps(f)   # 保留原函数的元数据
        def decorated_function(*args, **kwargs):   # 内层实际执行的包装函数
            if not current_user.is_authenticated:
                # 未登录，跳转登录页
                return redirect(url_for('auth.login', next='request.url'))
            if not current_user.has_permission(permission_name):
                # 无权限 返回403
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# 管理员权限装饰器
def admin_required(f):
    return permission_required('user_manage')(f)

