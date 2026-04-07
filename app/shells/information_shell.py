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
from app import db
from app.models import Role, Permission

# 创建权限
for name, desc in Permission.PERMISSIONS.items():
     p = Permission(name=name, desc=desc)
     db.session.add(p)

# 创建角色（管理员/仓库管理员/普通员工）
admin_role = Role(name='管理员', desc='拥有所有权限')
warehouse_role = Role(name='仓库管理员', desc='拥有商品、出入库、库存管理权限')
staff_role = Role(name='普通员工', desc='拥有库存查询、报表查看权限')

# 分配权限
admin_role.permissions = Permission.query.all()
warehouse_role.permissions = Permission.query.filter(Permission.name.in_(['product_manage', 'inbound_manage', 'outbound_manage', 'inventory_manage'])).all()
staff_role.permissions = Permission.query.filter(Permission.name.in_(['inventory_manage', 'report_view'])).all()
db.session.add_all([admin_role, warehouse_role, staff_role])

# 创建管理员用户
from app.models import User
admin = User(username='admin', real_name='系统管理员')
admin.set_password('123456')
admin.roles.append(admin_role)
db.session.add(admin)
db.session.commit()

from app.models import WarehouseLocation, Supplier, Category, Customer
category1 = Category(
    name="电脑",
    desc="台式机、笔记本等电脑设备"
)
category2 = Category(
    name="办公",
    desc="办公用品及设备"
)
category3 = Category(
    name="文具用品",
    desc="各类文具及办公用品"
)
category4 = Category(
    name="手机",
    desc="各类手机及配件"
)
category5 = Category(
    name="数码",
    desc="数码产品及配件"
)

db.session.add_all([category1, category2, category3, category4, category5])
db.session.commit()

supplier1 = Supplier(
    name="北京XX商贸有限公司",
    contact_person="张三",
    phone="13800138000",
    email="zhangsan@example.com",
    address="北京市朝阳区XX路XX号",
)
supplier2 = Supplier(
    name="上海XX科技有限公司",
    contact_person="李四",
    phone="13900139000",
    email="lisi@example.com",
    address="上海市浦东新区XX路XX号",
)

# 添加并提交
db.session.add_all([supplier1, supplier2])
db.session.commit()

# 按照分类和供应商创建对应库位
location1 = WarehouseLocation(
    name="A区-电脑产品库",
    code="A-001",
    area="电脑区",
    status=True,
    remark="存放北京XX商贸有限公司提供的电脑设备"
)
location2 = WarehouseLocation(
    name="B区-办公文具库",
    code="B-001",
    area="办公区",
    status=True,
    remark="存放上海XX科技有限公司提供的办公用品及文具"
)
location3 = WarehouseLocation(
    name="C区-手机数码库",
    code="C-001",
    area="数码区",
    status=True,
    remark="存放各类手机及数码产品"
)

# 添加并提交库位数据
db.session.add_all([location1, location2, location3])
db.session.commit()

# 添加客户数据样例
customer1 = Customer(
    name="北京XX科技有限公司",
    contact_person="王五",
    phone="13700137000",
    email="wangwu@example.com",
    address="北京市海淀区XX路XX号",
)
customer2 = Customer(
    name="上海XX贸易有限公司",
    contact_person="赵六",
    phone="13600136000",
    email="zhaoliu@example.com",
    address="上海市徐汇区XX路XX号",
)
customer3 = Customer(
    name="广州XX电子有限公司",
    contact_person="孙七",
    phone="13500135000",
    email="sunqi@example.com",
    address="广州市天河区XX路XX号",
)

# 添加并提交客户数据
db.session.add_all([customer1, customer2, customer3])
db.session.commit()