from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager

PERMISSIONS = {
    'user_manage': '用户管理',
    'product_manage': '商品管理',
    'inbound_manage': '入库管理',
    'outbound_manage': '出库管理',
    'report_view': '报表查看'
}

# 角色-权限 多对多关联表
role_permission = db.Table(
    'role_permission',
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id'), primary_key=True)
)

# 用户—角色 多对多关联表
user_role = db.Table(
    'user_role',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True)
)


# 权限表
class Permission(db.Model):
    __tablename__ = 'permissions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)  # 权限标识(product_manage)
    desc = db.Column(db.String(64))  # 权限描述
    roles = db.relationship('Role', secondary=role_permission, backref=db.backref('permissions', lazy='dynamic'))
    # 通过role.permissions获取该角色拥有的所有权限(动态加载)
    # 通过permission.roles获取拥有该权限的所有角色(立即加载)
    PERMISSIONS = PERMISSIONS

    def __repr__(self):
        return f'<Permission {self.name}>'


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key= True)
    name = db.Column(db.String(32), unique=True, nullable=False)  # 角色名称（管理员/普通员工/仓库管理员)
    desc = db.Column(db.String(64))  # 角色描述
    users = db.relationship('User', secondary=user_role, backref=db.backref('roles', lazy='dynamic'))
    # 通过user.roles获取该用户的所有角色（动态加载）
    # 通过role.users获取作为该角色的所有用户（立即加载）

    def __repr__(self):
        return f'<Role {self.name}>'

    # 检查角色是否有某个权限
    def has_permission(self, permission_name):
        return self.permissions.filter_by(name=permission_name).first() is not None


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False)  # 用户名
    password_hash = db.Column(db.String(256), nullable=False)  # 密码哈希
    real_name = db.Column(db.String(32))  # 真实姓名
    phone = db.Column(db.String(16))  # 手机号
    email = db.Column(db.String(64))  # 邮箱
    is_active = db.Column(db.Boolean, default=True)  # 是否激活
    create_time = db.Column(db.DateTime, default=datetime.utcnow)  # 创建时间

    def __repr__(self):
        return f'<User{self.username}>'

    # 设置密码（加密）
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    # 验证密码
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # 检查用户是否有某个权限
    def has_permission(self, permission_name):
        for role in self.roles:   # self.roles是一个角色对象列表
            if role.has_permission(permission_name):
                return True
        return False


# Flask-Login 回调：通过用户ID加载用户
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))  # 查询并返回对应session中存储的用户ID
