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
# flask shell代码
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

from app.models import Product, Inventory, InboundOrder, InboundItem, OutboundOrder, OutboundItem, InventoryCountTask
from app.utils.helpers import generate_inbound_no, generate_outbound_no, update_inventory, generate_inventory_count_task_no

# 创建商品样例
# 原材料
raw_material1 = Product(
    code="RM-001",
    name="不锈钢板材",
    spec="304 1.5mm",
    unit="张",
    category_id=category1.id,
    supplier_id=supplier1.id,
    warning_stock=50
)
raw_material2 = Product(
    code="RM-002",
    name="塑料颗粒",
    spec="PP 颗粒",
    unit="kg",
    category_id=category1.id,
    supplier_id=supplier2.id,
    warning_stock=100
)

# 成品
finished_product1 = Product(
    code="FP-001",
    name="智能手机",
    spec="64GB 黑色",
    unit="台",
    category_id=category2.id,
    supplier_id=supplier2.id,
    warning_stock=20
)
finished_product2 = Product(
    code="FP-002",
    name="笔记本电脑",
    spec="16GB 512GB SSD",
    unit="台",
    category_id=category2.id,
    supplier_id=supplier2.id,
    warning_stock=10
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


# 创建入库单样例
# 第一个入库单
order_no1 = generate_inbound_no()
total_qty1 = 100 + 50  # 100张不锈钢板材 + 50个手机充电器
inbound_order1 = InboundOrder(
    order_no=order_no1,
    supplier_id=supplier1.id,
    operator_id=admin.id,  # 使用管理员用户作为操作员
    inbound_date=datetime.now().date(),
    total_amount=total_qty1,
    status="completed"
)
db.session.add(inbound_order1)
db.session.flush()  # 刷新获取order_id

# 创建入库项并更新库存
inbound_item1 = InboundItem(
    order_id=inbound_order1.id,
    product_id=raw_material1.id,
    location_id=location1.id,
    quantity=100,
    batch_no="RM-20260301"
)
db.session.add(inbound_item1)
update_inventory(raw_material1.id, location1.id, "RM-20260301", 100, is_bound=True)

inbound_item2 = InboundItem(
    order_id=inbound_order1.id,
    product_id=accessory1.id,
    location_id=location3.id,
    quantity=50,
    batch_no="AC-20260301"
)
db.session.add(inbound_item2)
update_inventory(accessory1.id, location3.id, "AC-20260301", 50, is_bound=True)

# 第二个入库单
order_no2 = generate_inbound_no()
total_qty2 = 200 + 20  # 200kg塑料颗粒 + 20台智能手机
inbound_order2 = InboundOrder(
    order_no=order_no2,
    supplier_id=supplier2.id,
    operator_id=admin.id,  # 使用管理员用户作为操作员
    inbound_date=datetime.now().date(),
    total_amount=total_qty2,
    status="completed"
)
db.session.add(inbound_order2)
db.session.flush()  # 刷新获取order_id

# 创建入库项并更新库存
inbound_item3 = InboundItem(
    order_id=inbound_order2.id,
    product_id=raw_material2.id,
    location_id=location1.id,
    quantity=200,
    batch_no="RM-20260302"
)
db.session.add(inbound_item3)
update_inventory(raw_material2.id, location1.id, "RM-20260302", 200, is_bound=True)

inbound_item4 = InboundItem(
    order_id=inbound_order2.id,
    product_id=finished_product1.id,
    location_id=location2.id,
    quantity=20,
    batch_no="FP-20260301"
)
db.session.add(inbound_item4)
update_inventory(finished_product1.id, location2.id, "FP-20260301", 20, is_bound=True)

# 提交入库单和入库项
db.session.commit()

# 创建出库单样例
# 第一个出库单
order_no3 = generate_outbound_no()
total_qty3 = 10 + 100  # 10台智能手机 + 100个手机充电器
outbound_order1 = OutboundOrder(
    order_no=order_no3,
    related_order="SO-20260301-001",
    receiver="张三",
    receive_phone="13800138001",
    operator_id=admin.id,  # 使用管理员用户作为操作员
    outbound_date=datetime.now().date(),
    purpose="销售出库",
    total_amount=total_qty3,
    status="completed",
    remark="客户A订单"
)
db.session.add(outbound_order1)
db.session.flush()  # 刷新获取order_id

# 创建出库项并更新库存
outbound_item1 = OutboundItem(
    order_id=outbound_order1.id,
    product_id=finished_product1.id,
    location_id=location2.id,
    quantity=10,
    batch_no="FP-20260301"
)
db.session.add(outbound_item1)
update_inventory(finished_product1.id, location2.id, "FP-20260301", 10, is_bound=False)

outbound_item2 = OutboundItem(
    order_id=outbound_order1.id,
    product_id=accessory1.id,
    location_id=location3.id,
    quantity=100,
    batch_no="AC-20260301"
)
db.session.add(outbound_item2)
update_inventory(accessory1.id, location3.id, "AC-20260301", 100, is_bound=False)

# 第二个出库单
order_no4 = generate_outbound_no()
total_qty4 = 5  # 5台笔记本电脑
outbound_order2 = OutboundOrder(
    order_no=order_no4,
    related_order="SO-20260302-001",
    receiver="李四",
    receive_phone="13900139001",
    operator_id=admin.id,  # 使用管理员用户作为操作员
    outbound_date=datetime.now().date(),
    purpose="销售出库",
    total_amount=total_qty4,
    status="completed",
    remark="客户B订单"
)
db.session.add(outbound_order2)
db.session.flush()  # 刷新获取order_id

# 创建出库项并更新库存
outbound_item3 = OutboundItem(
    order_id=outbound_order2.id,
    product_id=finished_product2.id,
    location_id=location2.id,
    quantity=5,
    batch_no="FP-20260302"
)
db.session.add(outbound_item3)
update_inventory(finished_product2.id, location2.id, "FP-20260302", 5, is_bound=False)

# 提交出库单和出库项
db.session.commit()

# 创建盘点任务样例
# 第一个盘点任务：时间触发的月度盘点
from datetime import timedelta
task_no1 = generate_inventory_count_task_no()
task1 = InventoryCountTask(
    task_no=task_no1,
    name="月度盘点",
    type="time",
    status="completed",
    area="A区",
    start_time=datetime.now() - timedelta(days=1),
    end_time=datetime.now(),
    operator_id=admin.id,
    cycle_days=30,  # 30天周期
    remark="每月定期盘点"
)
db.session.add(task1)

# 第二个盘点任务：区域触发的B区盘点
task_no2 = generate_inventory_count_task_no()
task2 = InventoryCountTask(
    task_no=task_no2,
    name="B区季度盘点",
    type="area",
    status="pending",
    area="B区",
    cycle_days=90,  # 90天周期
    remark="每季度对B区进行盘点"
)
db.session.add(task2)

# 第三个盘点任务：阈值触发的高价值商品盘点
task_no3 = generate_inventory_count_task_no()
task3 = InventoryCountTask(
    task_no=task_no3,
    name="高价值商品盘点",
    type="threshold",
    status="pending",
    threshold=1000,  # 阈值1000
    remark="当库存价值超过阈值时触发盘点"
)
db.session.add(task3)

# 提交盘点任务
db.session.commit()

print("数据初始化完成！")
print(f"创建了 {Product.query.count()} 个商品")
print(f"创建了 {Inventory.query.count()} 个库存记录")
print(f"创建了 {InboundOrder.query.count()} 个入库单")
print(f"创建了 {OutboundOrder.query.count()} 个出库单")
print(f"创建了 {InventoryCountTask.query.count()} 个盘点任务")