# ==================== 盘点流程测试样例 ====================
print("\n" + "="*50)
print("开始盘点流程测试...")
print("="*50)

# 查看当前库存状态
print("\n当前库存状态:")
all_inventories = Inventory.query.all()
for inv in all_inventories:
    print(f"  {inv.product.code} - {inv.location.code}: 物理库存={inv.quantity}, 锁定={inv.locked_quantity}, 冻结={inv.frozen_quantity}, 可用={inv.available_quantity}")

# 1. 创建盘点单（明盘，全部库存）
print("\n1. 创建盘点单...")
count_order = InventoryCount(
    count_no=generate_count_no(),
    count_type='open_count',  # 明盘
    scope_type='all',  # 全部库存
    scope_filter=json.dumps({}),
    plan_date=datetime.now().date(),
    operator_id=admin.id,
    status='draft',
    remark='测试盘点单'
)
db.session.add(count_order)
db.session.flush()

# 创建快照
from app.views.count_manage import _create_snapshot
_create_snapshot(count_order, 'all', {})
db.session.commit()
print(f"   盘点单创建成功: {count_order.count_no}")
print(f"   盘点明细数量: {count_order.total_items}")

# 2. 录入实盘数量（模拟盘盈和盘亏）
print("\n2. 录入实盘数量...")
details = count_order.details.all()
for i, detail in enumerate(details):
    # 获取当前库存的可用数量
    available = detail.inventory.available_quantity if detail.inventory else 0
    
    if i == 0:
        # 第一个商品：盘盈 +5
        detail.counted_quantity = detail.snapshot_quantity + 5
        detail.variance_reason = '发现多出商品'
    elif i == 1 and available >= 3:
        # 第二个商品：盘亏 -3（只有可用库存足够时才盘亏）
        detail.counted_quantity = detail.snapshot_quantity - 3
        detail.variance_reason = '商品损坏'
    else:
        # 其他商品：无差异
        detail.counted_quantity = detail.snapshot_quantity
    detail.counted_time = datetime.utcnow()
    detail.calculate_variance()
    print(f"   {detail.product.code}: 快照={detail.snapshot_quantity}, 实盘={detail.counted_quantity}, 差异={detail.variance_quantity or 0}, 可用={available}")

db.session.commit()

# 3. 查看差异预览
print("\n3. 差异统计:")
gains = [d for d in details if d.variance_type == 'gain']
losses = [d for d in details if d.variance_type == 'loss']
no_variance = [d for d in details if d.variance_type == 'none']
print(f"   盘盈: {len(gains)} 项")
print(f"   盘亏: {len(losses)} 项")
print(f"   无差异: {len(no_variance)} 项")

# 4. 生成差异单
print("\n4. 生成差异单...")
from app.views.count_manage import _create_variance_document

try:
    if gains:
        _create_variance_document(count_order, 'gain', gains)
        print(f"   盘盈单已创建")

    if losses:
        _create_variance_document(count_order, 'loss', losses)
        print(f"   盘亏单已创建")

    count_order.status = 'completed'
    db.session.commit()
except Exception as e:
    print(f"   生成差异单失败: {str(e)}")
    db.session.rollback()

# 5. 查看冻结记录
print("\n5. 冻结记录:")
freeze_records = InventoryFreezeRecord.query.filter_by(count_id=count_order.id).all()
for fr in freeze_records:
    print(f"   商品: {fr.product.code}, 冻结数量: {fr.freeze_qty}, 类型: {fr.freeze_type}, 状态: {fr.status}")

# 6. 查看库存冻结状态
print("\n6. 冻结后库存状态:")
for inv in all_inventories:
    print(f"  {inv.product.code} - {inv.location.code}: 物理库存={inv.quantity}, 锁定={inv.locked_quantity}, 冻结={inv.frozen_quantity}, 可用={inv.available_quantity}")

# 7. 审核差异单
print("\n7. 审核差异单...")
from app.views.count_manage import _approve_variance_internal

variance_docs = VarianceDocument.query.filter_by(count_id=count_order.id).all()
for variance in variance_docs:
    print(f"   审核: {variance.variance_no} ({variance.variance_type})")
    try:
        _approve_variance_internal(variance, force=False, approver_id=admin.id)
        print(f"   审核通过")
    except ValueError as e:
        print(f"   审核失败（尝试强制通过）: {str(e)}")
        try:
            variance.status = 'pending'  # 重置状态
            _approve_variance_internal(variance, force=True, approver_id=admin.id)
            print(f"   强制审核通过")
        except Exception as e2:
            print(f"   强制审核也失败: {str(e2)}")

db.session.commit()

# 8. 查看库存变更日志
print("\n8. 库存变更日志:")
change_logs = InventoryChangeLog.query.filter(
    InventoryChangeLog.reason.like(f'%{count_order.count_no}%')
).all()
for log in change_logs:
    print(f"   库存ID: {log.inventory_id}")
    print(f"   变更: 物理库存 {log.quantity_before} -> {log.quantity_after}")
    print(f"         冻结 {log.frozen_quantity_before} -> {log.frozen_quantity_after}")
    print(f"   原因: {log.reason}")

# 9. 最终库存状态
print("\n9. 最终库存状态:")
for inv in all_inventories:
    print(f"  {inv.product.code} - {inv.location.code}: 物理库存={inv.quantity}, 锁定={inv.locked_quantity}, 冻结={inv.frozen_quantity}, 可用={inv.available_quantity}")

print("\n" + "="*50)
print("盘点流程测试完成！")
print(f"盘点单号: {count_order.count_no}")
print(f"差异单号: {[v.variance_no for v in variance_docs]}")
print("="*50)