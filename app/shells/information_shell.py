"""
pip install -r requirements.txt

# 数据库初始化
flask db init

flask db migrate -m "initial migration"

flask db upgrade

flask shell

"""

"""
# 重置数据库
drop database warehouse_db;
create database warehouse_db;
use warehouse_db;
"""

"""
# 查看表信息
select * from permissions;
select * from roles;
select * from suppliers;
select * from categories;
"""
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
信息初始化脚本
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app import create_app, db
from app.models.product import Category, Supplier, ProductParamKey, CategoryParam, Customer
from app.models.inventory import WarehouseLocation
from app.models.user import User, Role, Permission


def init_categories():
    """初始化商品分类"""
    categories = [
        {'name': '电脑', 'desc': '计算机设备'},  # 1
        {'name': '手机', 'desc': '移动通讯设备'},  # 2
        {'name': '平板', 'desc': '平板电脑设备'},  # 3
        {'name': '配件', 'desc': '电脑手机配件'},  # 4
    ]
    
    for item in categories:
        category = Category.query.filter_by(name=item['name']).first()
        if not category:
            category = Category(name=item['name'], desc=item['desc'])
            db.session.add(category)
    db.session.commit()
    print('商品分类初始化完成')


def init_product_params():
    """初始化商品参数"""
    # 定义参数
    param_keys = [
        {'name': '存储容量', 'desc': '商品的存储容量'},  # 1
        {'name': '屏幕尺寸', 'desc': '商品的屏幕尺寸'},  # 2
        {'name': '品牌', 'desc': '商品的品牌'},  # 3
        {'name': '显卡型号', 'desc': '商品的显卡型号'},  # 4
        {'name': '处理器型号', 'desc': '商品的处理器型号'},  # 5
        {'name': '机型名称', 'desc': '商品的机型名称'},  # 6
    ]
    
    # 保存参数
    for item in param_keys:
        param_key = ProductParamKey.query.filter_by(name=item['name']).first()
        if not param_key:
            param_key = ProductParamKey(name=item['name'], desc=item['desc'])
            db.session.add(param_key)
    db.session.commit()
    
    # 定义分类参数关联
    category_params = {
        '电脑': ['存储容量', '屏幕尺寸', '品牌', '显卡型号', '处理器型号'],
        '手机': ['品牌', '屏幕尺寸', '存储容量', '机型名称', '处理器型号'],
    }
    
    # 保存分类参数关联
    for category_name, param_names in category_params.items():
        category = Category.query.filter_by(name=category_name).first()
        if category:
            for sort_order, param_name in enumerate(param_names):
                param_key = ProductParamKey.query.filter_by(name=param_name).first()
                if param_key:
                    # 检查是否已存在关联
                    existing = CategoryParam.query.filter_by(
                        category_id=category.id,
                        param_key_id=param_key.id
                    ).first()
                    if not existing:
                        category_param = CategoryParam(
                            category_id=category.id,
                            param_key_id=param_key.id,
                            sort_order=sort_order
                        )
                        db.session.add(category_param)
    db.session.commit()
    print('商品参数初始化完成')


def init_suppliers():
    """初始化供应商"""
    suppliers = [
        {'name': '京东科技', 'contact_person': '张三', 'phone': '13800138001', 'address': '北京市朝阳区', 'email': 'zhangsan@jd.com'},
        {'name': '苏宁电器', 'contact_person': '李四', 'phone': '13900139001', 'address': '南京市玄武区', 'email': 'lisi@suning.com'},
        {'name': '国美电器', 'contact_person': '王五', 'phone': '13700137001', 'address': '北京市朝阳区', 'email': 'wangwu@gome.com'},
    ]
    
    for item in suppliers:
        supplier = Supplier.query.filter_by(name=item['name']).first()
        if not supplier:
            supplier = Supplier(
                name=item['name'],
                contact_person=item['contact_person'],
                phone=item['phone'],
                address=item['address'],
                email=item['email']
            )
            db.session.add(supplier)
    db.session.commit()
    print('供应商初始化完成')


def init_warehouse_locations():
    """初始化库位"""
    locations = [
        {'code': 'A-01-01', 'name': 'A区-01通道-01层', 'status': True},
        {'code': 'A-01-02', 'name': 'A区-01通道-02层', 'status': True},
        {'code': 'A-02-01', 'name': 'A区-02通道-01层', 'status': True},
        {'code': 'A-02-02', 'name': 'A区-02通道-02层', 'status': True},
        {'code': 'B-01-01', 'name': 'B区-01通道-01层', 'status': True},
        {'code': 'B-01-02', 'name': 'B区-01通道-02层', 'status': True},
        {'code': 'B-02-01', 'name': 'B区-02通道-01层', 'status': True},
        {'code': 'B-02-02', 'name': 'B区-02通道-02层', 'status': True},
    ]
    
    for item in locations:
        location = WarehouseLocation.query.filter_by(code=item['code']).first()
        if not location:
            location = WarehouseLocation(
                code=item['code'],
                name=item['name'],
                status=item['status']
            )
            db.session.add(location)
    db.session.commit()
    print('库位初始化完成')


def init_customers():
    """初始化客户"""
    customers = [
        {'name': '北京京东世纪贸易有限公司', 'contact_person': '刘强东', 'phone': '13812345678', 'address': '北京市朝阳区', 'email': 'liuqiangdong@jd.com'},
        {'name': '上海苏宁易购销售有限公司', 'contact_person': '张近东', 'phone': '13912345678', 'address': '上海市浦东新区', 'email': 'zhangjindong@suning.com'},
        {'name': '国美电器有限公司', 'contact_person': '黄光裕', 'phone': '13712345678', 'address': '北京市朝阳区', 'email': 'huangguangyu@gome.com'},
        {'name': '小米科技有限责任公司', 'contact_person': '雷军', 'phone': '13612345678', 'address': '北京市海淀区', 'email': 'leijun@xiaomi.com'},
        {'name': '华为技术有限公司', 'contact_person': '任正非', 'phone': '13512345678', 'address': '广东省深圳市', 'email': 'renzhenfei@huawei.com'},
    ]
    
    for item in customers:
        customer = Customer.query.filter_by(name=item['name']).first()
        if not customer:
            customer = Customer(
                name=item['name'],
                contact_person=item['contact_person'],
                phone=item['phone'],
                address=item['address'],
                email=item['email']
            )
            db.session.add(customer)
    db.session.commit()
    print('客户初始化完成')


def init_roles():
    """初始化角色权限"""
    # 定义角色权限
    roles = {
        '管理员': ['product_manage', 'inventory_manage', 'inbound_manage',
                  'outbound_manage', 'supplier_manage', 'customer_manage',
                  'user_manage', 'report_view'],
        '仓库管理员': ['product_manage', 'inventory_manage', 'inbound_manage', 'outbound_manage'],
        '职员' : ['product_manage', 'inventory_manage', 'supplier_manage', 'customer_manage', 'user_manage']
    }
    
    for role_name, permissions in roles.items():
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name)
            db.session.add(role)
        
        # 清空现有权限
        role.permissions = []
        
        # 添加新权限
        for perm_name in permissions:
            permission = Permission.query.filter_by(name=perm_name).first()
            if not permission:
                from app.models.user import PERMISSIONS
                perm_desc = PERMISSIONS.get(perm_name)
                permission = Permission(name=perm_name, desc=perm_desc)
                db.session.add(permission)
            role.permissions.append(permission)
    db.session.commit()
    print('角色权限初始化完成')


def init_admin():
    """初始化管理员账号"""
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            real_name='管理员',
            email='admin@example.com'
        )
        # 设置密码
        admin.set_password('123456')
        # 分配管理员角色
        admin_role = Role.query.filter_by(name='管理员').first()
        if admin_role:
            admin.roles.append(admin_role)
        db.session.add(admin)
        db.session.commit()
        print('管理员账号初始化完成')


def main():
    """主函数"""
    app = create_app()
    with app.app_context():
        init_categories()
        init_product_params()
        init_suppliers()
        init_customers()
        init_warehouse_locations()
        init_roles()
        init_admin()
        print('所有信息初始化完成')


if __name__ == '__main__':
    main()