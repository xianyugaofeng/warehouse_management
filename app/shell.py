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

from app.models import WarehouseLocation, Supplier, Category
category1 = Category(
    name="原材料",  # 分类名称
    desc="生产用基础原材料"  # 备注（可选）
)
category2 = Category(
    name="成品",
    desc="已完工可销售的成品"
)
category3 = Category(
    name="配件",
    desc="设备/产品配套配件"
)

db.session.add_all([category1, category2, category3])
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

location1 = WarehouseLocation(
    name="A区-原材料库",
    code="A-001",
    area="原材料库",
    status=True,
    remark="存放金属/塑料原材料"
)
location2 = WarehouseLocation(
    name="B区-成品库",
    code="B-001",
    area="成品库",
    status=True,
    remark="存放完工成品，靠近发货区"
)
location3 = WarehouseLocation(
    name="C区-配件库",
    code="C-001",
    area="配件库",
    status=True,
    remark="存放各类配套配件"
)

db.session.add_all([location1, location2, location3])
db.session.commit()