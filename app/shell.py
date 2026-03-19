"""
pip install -r requirements.txt

# 数据库初始化
flask db init

flask db migrate -m "initial migration"

flask db upgrade

flask shell

# 统一运行所有测试
exec(open('app/shell.py', encoding='utf-8').read())
exec(open('app/shell_inbound.py', encoding='utf-8').read())
exec(open('app/shell_stock_move.py', encoding='utf-8').read())
exec(open('app/shell_count.py', encoding='utf-8').read())
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
# flask shell代码
import json
from app import db
from app.models import Role, Permission, User, WarehouseLocation, Supplier, Category, Product, Inventory, InboundOrder, InboundItem, OutboundOrder, OutboundItem, PurchaseOrder, InspectionOrder, InspectionItem, ReturnOrder, ReturnItem, InventoryCount, InventoryCountDetail, VarianceDocument, VarianceDetail, InventoryFreezeRecord, InventoryChangeLog
from app.utils.helpers import generate_inbound_no, generate_outbound_no, generate_purchase_no, generate_inspection_no, generate_return_no, generate_count_no, generate_variance_no, update_inventory, recommend_location
from datetime import datetime, timedelta

# 创建权限
for name, desc in Permission.PERMISSIONS.items():
        p = Permission(name=name, desc=desc)
        db.session.add(p)

# 创建角色（管理员/仓库管理员/普通员工）
admin_role = Role(name='管理员', desc='拥有所有权限')
warehouse_role = Role(name='仓库管理员', desc='拥有商品、出入库、库存管理权限')
staff_role = Role(name='普通员工', desc='拥有库存查询、报表查看权限')
db.session.add_all([admin_role, warehouse_role, staff_role])
db.session.flush()

# 分配权限
admin_role.permissions = Permission.query.all()
warehouse_role.permissions = Permission.query.filter(Permission.name.in_(['inbound_manage', 'outbound_manage', 'inventory_manage'])).all()
staff_role.permissions = Permission.query.filter(Permission.name.in_(['inventory_manage', 'report_view'])).all()

# 创建管理员用户
admin = User(username='admin', real_name='系统管理员')
admin.set_password('123456')
admin.roles.append(admin_role)
db.session.add(admin)
db.session.commit()

# 创建分类
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

# 创建供应商
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

# 创建库位
# 正常库位
location1 = WarehouseLocation(
    name="A区-原材料库",
    code="A-001",
    area="原材料库",
    location_type='normal',
    status=True,
    remark="存放金属/塑料原材料"
)
location2 = WarehouseLocation(
    name="B区-成品库",
    code="B-001",
    area="成品库",
    location_type='normal',
    status=True,
    remark="存放完工成品，靠近发货区"
)
location3 = WarehouseLocation(
    name="C区-配件库",
    code="C-001",
    area="配件库",
    location_type='normal',
    status=True,
    remark="存放各类配套配件"
)
# 不合格品库位
location4 = WarehouseLocation(
    name="D区-不合格品库",
    code="D-001",
    area="不合格品库",
    location_type='reject',
    status=True,
    remark="存放不合格商品"
)
# 待检库位
location5 = WarehouseLocation(
    name="E区-待检库",
    code="E-001",
    area="待检库",
    location_type='inspection',
    status=True,
    remark="存放待检验商品"
)
# 等待区库位（入库待上架）
location6 = WarehouseLocation(
    name="F区-等待区",
    code="F-001",
    area="等待区",
    location_type='waiting',
    status=True,
    remark="入库待上架区域"
)
# 待处理区库位（检验待处理）
location7 = WarehouseLocation(
    name="G区-待处理区",
    code="G-001",
    area="待处理区",
    location_type='pending',
    status=True,
    remark="检验待处理区域"
)

db.session.add_all([location1, location2, location3, location4, location5, location6, location7])
db.session.commit()
print("库位创建/检查完成")

# 创建商品样例
# 原材料
raw_material1 = Product(
    code="RM-001",
    name="不锈钢板材",
    spec="304 1.5mm",
    unit="张",
    category_id=category1.id,
    supplier_id=supplier1.id,
    warning_stock=10
)
raw_material2 = Product(
    code="RM-002",
    name="塑料颗粒",
    spec="ABS 标准级",
    unit="kg",
    category_id=category1.id,
    supplier_id=supplier2.id,
    warning_stock=100
)

# 成品
finished_product1 = Product(
    code="FP-001",
    name="不锈钢制品A",
    spec="标准规格",
    unit="件",
    category_id=category2.id,
    supplier_id=supplier1.id,
    warning_stock=20
)
finished_product2 = Product(
    code="FP-002",
    name="塑料制品B",
    spec="大型",
    unit="套",
    category_id=category2.id,
    supplier_id=supplier2.id,
    warning_stock=15
)

# 配件
accessory1 = Product(
    code="AC-001",
    name="手机充电器",
    spec="20W USB-C",
    unit="个",
    category_id=category3.id,
    supplier_id=supplier1.id,
    warning_stock=50
)
accessory2 = Product(
    code="AC-002",
    name="笔记本电池",
    spec="6芯 48Wh",
    unit="块",
    category_id=category3.id,
    supplier_id=supplier2.id,
    warning_stock=30
)

# 添加商品
db.session.add_all([raw_material1, raw_material2, finished_product1, finished_product2, accessory1, accessory2])
db.session.commit()
print("商品创建完成")