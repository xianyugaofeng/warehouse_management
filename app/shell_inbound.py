# ==================== 入库流程测试样例 ====================
from app.utils.helpers import generate_purchase_no, generate_inspection_no, generate_inbound_no, generate_return_no, update_inventory, recommend_location
from datetime import datetime, timedelta

# 创建采购单样例
purchase_order1 = PurchaseOrder(
    order_no=generate_purchase_no(),
    supplier_id=supplier1.id,
    product_id=raw_material1.id,
    operator_id=admin.id,
    expected_date=datetime.now().date() + timedelta(days=7),  # 预计到货日期
    actual_date=datetime.now().date(),  # 实际到货日期
    quantity=50,
    unit_price=100.0,
    subtotal=5000.0,
    status='completed',
    remark='采购原材料'
)
db.session.add(purchase_order1)
db.session.flush()

# 由于PurchaseOrder模型已经包含了商品信息，不需要单独创建PurchaseItem
db.session.commit()

# 创建检验单样例
inspection_order1 = InspectionOrder(
    order_no=generate_inspection_no(),
    purchase_order_id=purchase_order1.id,
    supplier_id=supplier1.id,
    delivery_order_no=purchase_order1.order_no,  # 送货单号即采购单号
    operator_id=admin.id,
    inspection_date=datetime.now().date(),
    total_quantity=50,
    qualified_quantity=48,
    unqualified_quantity=2,
    status='completed',
    signature='仓库管理员',
    remark='检验合格'
)
db.session.add(inspection_order1)
db.session.flush()

# 添加检验明细
inspection_item1 = InspectionItem(
    inspection_id=inspection_order1.id,
    product_id=raw_material1.id,
    quantity=50,
    qualified_quantity=48,
    unqualified_quantity=2,
    quality_status='passed',
    remark='合格'
)
db.session.add(inspection_item1)

# 创建不合格商品库存记录
defective_inventory = Inventory(
    product_id=raw_material1.id,
    location_id=location4.id,
    batch_no=f'B{datetime.now().strftime("%Y%m%d")}3',
    quantity=2,
    defect_reason='表面划痕',
    inspection_order_id=inspection_order1.id,
    remark='检验不合格'
)
db.session.add(defective_inventory)
db.session.commit()
print("不合格商品库存记录创建完成")

# ==================== 入库流程（按照入库模块逻辑） ====================
print("\n开始入库流程...")

# 查找等待区库位和待处理区库位（已在前面创建）
waiting_location = WarehouseLocation.query.filter_by(status=True, location_type='waiting').first()
pending_location = WarehouseLocation.query.filter_by(status=True, location_type='pending').first()

print(f"等待区库位: {waiting_location.code if waiting_location else '未设置'}")
print(f"待处理区库位: {pending_location.code if pending_location else '未设置'}")

# 创建待处理区库存（模拟检验合格后的库存）
pending_inventory = Inventory(
    product_id=raw_material1.id,
    location_id=pending_location.id,
    batch_no=f'B{datetime.now().strftime("%Y%m%d")}1',
    quantity=48,
    inspection_order_id=inspection_order1.id,
    remark='检验合格待入库'
)
db.session.add(pending_inventory)
db.session.commit()
print(f"待处理区库存创建完成: {pending_inventory.quantity} 件")

# 创建入库单（状态为pending）
inbound_order1 = InboundOrder(
    order_no=generate_inbound_no(),
    supplier_id=supplier1.id,
    related_order=purchase_order1.order_no,
    delivery_order_no=purchase_order1.order_no,
    inspection_cert_no=inspection_order1.order_no,
    purchase_order_id=purchase_order1.id,
    inspection_order_id=inspection_order1.id,
    operator_id=admin.id,
    inbound_date=datetime.now().date(),
    total_amount=48,
    status='pending',
    remark='原材料入库'
)
db.session.add(inbound_order1)
db.session.flush()

# 将库存从待处理区转移到等待区
pending_inventory.location_id = waiting_location.id
pending_inventory.remark = '入库待上架'
print(f"库存从待处理区转移到等待区")

# 创建库存变更日志（从待处理区转移到等待区）
transfer_log = InventoryChangeLog(
    inventory_id=pending_inventory.id,
    change_type='transfer',
    quantity_before=pending_inventory.quantity,
    quantity_after=pending_inventory.quantity,
    locked_quantity_before=pending_inventory.locked_quantity,
    locked_quantity_after=pending_inventory.locked_quantity,
    frozen_quantity_before=pending_inventory.frozen_quantity,
    frozen_quantity_after=pending_inventory.frozen_quantity,
    operator=admin.username,
    reason='从待处理区转移到等待区',
    reference_id=inbound_order1.id,
    reference_type='inbound_order'
)
db.session.add(transfer_log)

# 创建入库明细
inbound_item1 = InboundItem(
    order_id=inbound_order1.id,
    product_id=raw_material1.id,
    location_id=waiting_location.id,
    quantity=48,
    batch_no=pending_inventory.batch_no,
    unit_price=100.0,
    subtotal=4800.0
)
db.session.add(inbound_item1)
db.session.commit()
print(f"入库单创建完成: {inbound_order1.order_no}")

# ==================== 上架流程（按照上架模块逻辑） ====================
print("\n开始上架流程...")

# 获取所有正常库位
normal_locations = WarehouseLocation.query.filter_by(status=True, location_type='normal').all()
print(f"正常库位数量: {len(normal_locations)}")
for loc in normal_locations:
    print(f"  - {loc.code} ({loc.name})")

# 为每个入库明细分配库位并更新库存
for item in inbound_order1.items:
    print(f"\n处理入库明细: 商品={item.product.code}, 数量={item.quantity}")
    
    # 推荐最佳库位
    recommended_location = recommend_location(item.product_id, normal_locations)
    print(f"推荐库位: {recommended_location.code if recommended_location else 'None'}")
    
    if recommended_location:
        item.location_id = recommended_location.id
        item.signature = '仓库管理员'
        
        # 查找等待区的库存记录并转移到正常库位
        waiting_inventory = Inventory.query.filter_by(
            product_id=item.product_id,
            location_id=waiting_location.id,
            batch_no=item.batch_no
        ).first()
        print(f"  等待区库存查询: {'找到' if waiting_inventory else '未找到'}")
        if waiting_inventory:
            print(f"  等待区库存数量: {waiting_inventory.quantity}")
        
        if waiting_inventory:
            # 创建库存变更日志（从等待区转移到正常库位）
            putaway_log = InventoryChangeLog(
                inventory_id=waiting_inventory.id,
                change_type='transfer',
                quantity_before=waiting_inventory.quantity,
                quantity_after=waiting_inventory.quantity,
                locked_quantity_before=waiting_inventory.locked_quantity,
                locked_quantity_after=waiting_inventory.locked_quantity,
                frozen_quantity_before=waiting_inventory.frozen_quantity,
                frozen_quantity_after=waiting_inventory.frozen_quantity,
                operator=admin.username,
                reason='上架操作，从等待区转移到正常库位',
                reference_id=inbound_order1.id,
                reference_type='inbound_order'
            )
            db.session.add(putaway_log)
            
            waiting_inventory.location_id = recommended_location.id
            waiting_inventory.remark = '已上架'
            print(f"  商品 {item.product.code} 从等待区转移到库位 {recommended_location.code}")
        else:
            # 如果等待区没有库存记录，直接创建库存
            update_inventory(item.product_id, recommended_location.id, item.batch_no, item.quantity, is_bound=True)
            print(f"  商品 {item.product.code} 创建库存记录，库位 {recommended_location.code}")

# 更新入库单状态为已完成
inbound_order1.status = 'completed'
db.session.commit()
print("上架完成，入库单状态更新为已完成")

# 创建退货单样例
return_order1 = ReturnOrder(
    order_no=generate_return_no(),
    return_date=datetime.now().date(),
    return_reason='质量问题',
    operator_id=admin.id,
    status='completed',
    remark='不合格商品退货'
)
db.session.add(return_order1)
db.session.flush()

# 添加退货明细
return_item1 = ReturnItem(
    return_order_id=return_order1.id,
    product_id=defective_inventory.product_id,
    location_id=defective_inventory.location_id,
    batch_no=defective_inventory.batch_no,
    quantity=2,
    unit_price=100.0,
    amount=200.0,
    defect_reason='质量问题'
)
db.session.add(return_item1)
db.session.commit()

# 更新不合格商品库存
defective_inventory.quantity -= 2
db.session.commit()

print("数据生成完成！")
print(f"采购单: {purchase_order1.order_no}")
print(f"检验单: {inspection_order1.order_no}")
print(f"入库单: {inbound_order1.order_no}")
print(f"退货单: {return_order1.order_no}")
print(f"上架完成，库存已更新")