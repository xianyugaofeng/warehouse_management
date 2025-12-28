from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db,login_manager

PERMISSIONS = {
    'user_manage':'用户管理',
    'product_manage':'商品管理',
    'inbound_manage':'入库管理',
    'outbound_manage':'出库管理',
    'report_view':'报表查看'
}

# 角色-权限 多对多关联表
role_permission = db.Table(
    'role_permission',
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeginKey('permissions.id'), primary_key=True)
)

# 用户—角色 多对多关联表
user_role = db.Table(
    'user_role',
    db.Column('user_id', db.Integer, db.ForeginKey('users.id'), primary_key=True),
    db.Column('role_id', db.Interger, db.ForeginKey('roles.id'), primary_key=True)
)

# 权限表
class Permission(db.Model):
    __tablename__ = 'permissions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False) # 权限标识(product_manage)
    desc = db.Column(db.String(64)) # 权限描述
    roles = db.relationship('Role', secondary=role_permission, backref=db.backref('permissions', lazy='dynamic'))

    def __repr__(self):
        return f'<Permission {self.name}>'