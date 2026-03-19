
# ==================== 移库流程测试样例 ====================
from app.models.inventory import StockMoveOrder, StockMoveItem
from app.utils.helpers import generate_stock_move_no
from datetime import datetime

print("\n" + "="*50)
print("开始移库流程测试...")
print("="*50)

# 查看当前库存状态
print("\n当前库存状态:")
all_inventories = Inventory.query.filter(Inventory.quantity > 0).all()
for inv in all_inventories:
    print(f"  {inv.product.code} - {inv.location.code}: 物理库存={inv.quantity}, 可用={inv.available_quantity}")

# 1. 创建移库单
print("\n1. 创建移库单...")

# 找一个有库存的商品和两个同类型的库位
source_inv = Inventory.query.filter(Inventory.quantity > 0).first()
if source_inv:
    print(f"   找到库存: 商品={source_inv.product.code}, 库位={source_inv.location.code}, 库位类型={source_inv.location.location_type}")
    
    # 找一个同类型的其他库位
    same_type_locations = WarehouseLocation.query.filter(
        WarehouseLocation.location_type == source_inv.location.location_type,
        WarehouseLocation.id != source_inv.location_id,
        WarehouseLocation.status == True
    ).all()
    print(f"   同类型库位数量: {len(same_type_locations)}")
    for loc in same_type_locations:
        print(f"      - {loc.code} ({loc.name})")
    
    target_location = same_type_locations[0] if same_type_locations else None
    
    if target_location:
        stock_move_order = StockMoveOrder(
            order_no=generate_stock_move_no(),
            operator_id=admin.id,
            move_date=datetime.now().date(),
            total_quantity=10,
            status='pending',
            reason='库位优化调整',
            remark='测试移库单'
        )
        db.session.add(stock_move_order)
        db.session.flush()
        
        # 创建移库明细
        move_item = StockMoveItem(
            order_id=stock_move_order.id,
            product_id=source_inv.product_id,
            source_location_id=source_inv.location_id,
            target_location_id=target_location.id,
            quantity=10,
            move_batch_no=source_inv.batch_no
        )
        db.session.add(move_item)
        db.session.commit()
        
        print(f"   移库单创建成功: {stock_move_order.order_no}")
        print(f"   商品: {source_inv.product.code}")
        print(f"   源库位: {source_inv.location.code} -> 目标库位: {target_location.code}")
        print(f"   移库数量: 10")
        
        # 2. 确认移库
        print("\n2. 确认移库...")
        
        # 检查源库位库存是否充足
        if source_inv.quantity >= 10:
            # 查找目标库位库存
            target_inv = Inventory.query.filter_by(
                product_id=source_inv.product_id,
                location_id=target_location.id
            ).first()
            
            # 记录变更前的数量
            source_qty_before = source_inv.quantity
            target_qty_before = target_inv.quantity if target_inv else 0
            
            # 更新源库位库存
            source_inv.quantity -= 10
            
            # 更新或创建目标库位库存
            if target_inv:
                target_inv.quantity += 10
            else:
                target_inv = Inventory(
                    product_id=source_inv.product_id,
                    location_id=target_location.id,
                    quantity=10,
                    batch_no=source_inv.batch_no,
                    remark='移库创建'
                )
                db.session.add(target_inv)
            
            # 更新移库单状态
            stock_move_order.status = 'completed'
            
            # 创建库存变更日志
            source_log = InventoryChangeLog(
                inventory_id=source_inv.id,
                change_type='move_out',
                quantity_before=source_qty_before,
                quantity_after=source_inv.quantity,
                locked_quantity_before=source_inv.locked_quantity,
                locked_quantity_after=source_inv.locked_quantity,
                frozen_quantity_before=source_inv.frozen_quantity,
                frozen_quantity_after=source_inv.frozen_quantity,
                operator=admin.username,
                reason=f'移库出库：{stock_move_order.reason}',
                reference_id=stock_move_order.id,
                reference_type='stock_move_order'
            )
            db.session.add(source_log)
            
            target_log = InventoryChangeLog(
                inventory_id=target_inv.id,
                change_type='move_in',
                quantity_before=target_qty_before,
                quantity_after=target_inv.quantity,
                locked_quantity_before=0,
                locked_quantity_after=0,
                frozen_quantity_before=0,
                frozen_quantity_after=0,
                operator=admin.username,
                reason=f'移库入库：{stock_move_order.reason}',
                reference_id=stock_move_order.id,
                reference_type='stock_move_order'
            )
            db.session.add(target_log)
            
            db.session.commit()
            print("   移库确认成功")
            
            # 3. 查看移库后的库存状态
            print("\n3. 移库后库存状态:")
            print(f"   源库位 {source_inv.location.code}: {source_qty_before} -> {source_inv.quantity}")
            print(f"   目标库位 {target_location.code}: {target_qty_before} -> {target_inv.quantity}")
            
            # 4. 查看库存变更日志
            print("\n4. 移库变更日志:")
            move_logs = InventoryChangeLog.query.filter_by(reference_id=stock_move_order.id).all()
            for log in move_logs:
                print(f"   类型: {log.change_type}, 数量: {log.quantity_before} -> {log.quantity_after}")
                print(f"   原因: {log.reason}")
        else:
            print(f"   源库位库存不足，无法移库（当前: {source_inv.quantity}）")
    else:
        print("   未找到同类型的目标库位，跳过移库测试")
else:
    print("   没有可用的库存进行移库测试")

print("\n" + "="*50)
print("移库流程测试完成！")
print("="*50)

# ==================== 最终汇总 ====================
print("\n" + "="*50)
print("所有测试样例执行完成！")
print("="*50)
if 'count_order' in dir():
    print(f"盘点单: {count_order.count_no}")
if 'variance_docs' in dir():
    print(f"差异单: {[v.variance_no for v in variance_docs]}")
if 'stock_move_order' in dir():
    print(f"移库单: {stock_move_order.order_no}")
print("="*50)