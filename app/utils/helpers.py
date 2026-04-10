from datetime import datetime
import random


# 生成入库单号（IN+日期+3位随机数）
def generate_inbound_no():
    date_str = datetime.now().strftime('%Y%m%d')
    random_str = str(random.randint(100, 999))
    return f'IN{date_str}{random_str}'


# 生成出库单号（OUT+日期+3位随机数）
def generate_outbound_no():
    date_str = datetime.now().strftime('%Y%m%d')
    random_str = str(random.randint(100, 999))
    return f'OUT{date_str}{random_str}'


# 生成调拨单号（TF+日期+3位随机数）
def generate_transfer_no():
    date_str = datetime.now().strftime('%Y%m%d')
    random_str = str(random.randint(100, 999))
    return f'TF{date_str}{random_str}'


def generate_check_no():
    date_str = datetime.now().strftime('%Y%m%d')
    random_str = str(random.randint(100, 999))
    return f'CK{date_str}{random_str}'


# 库存更新函数(入库时增加, 出库时减少)
def update_inventory(product_id, location_id, batch_no, quantity, is_bound=True):
    from app import db
    from app.models.inventory import Inventory

    # 查询是否存在该商品-库位-批次的库存记录
    inventory = Inventory.query.filter_by(
        product_id=product_id,
        location_id=location_id,
        batch_no=batch_no
    ).first()   # 返回一个inventory对象

    if is_bound:
        # 入库时检查库位是否已有其他商品
        conflict_product = Inventory.check_location_product_conflict(
            location_id, product_id, exclude_batch_no=batch_no if inventory else None
        )
        if conflict_product:
            raise ValueError(f'该库位已存放其他商品（{conflict_product}），一个库位只能存放一种商品')
        
        if inventory:
            inventory.quantity += quantity
        else:
            inventory = Inventory(
                product_id=product_id,
                location_id=location_id,
                batch_no=batch_no,
                quantity=quantity,
                stock_status='normal'
            )
            db.session.add(inventory)
    else:
        if not inventory:
            raise ValueError(f'库存不存在: 商品ID{product_id}, 库位ID{location_id}, 批次{batch_no}')
        
        # 检查库存状态
        if inventory.stock_status == 'frozen':
            raise ValueError(f'库存不可用（已冻结）: 商品ID{product_id}, 库位ID{location_id}, 批次{batch_no}')
        
        # 检查库存数量
        if inventory.quantity < quantity:
            raise ValueError(f'库存不足: 商品ID{product_id}, 库位ID{location_id}, 批次{batch_no}')
        
        inventory.quantity -= quantity
        # 库存为0时是否删除记录
        if inventory.quantity == 0:
            db.session.delete(inventory)

    db.session.commit()
    return inventory


# 执行调拨函数（扣减原库位库存，增加目标库位库存）
# 注意：此函数不提交事务，需要在调用处统一提交，以保证事务完整性
def execute_transfer(product_id, source_location_id, target_location_id, quantity):
    from app import db
    from app.models.inventory import Inventory

    # 检查目标库位是否已有其他商品
    conflict_product = Inventory.check_location_product_conflict(target_location_id, product_id)
    if conflict_product:
        raise ValueError(f'目标库位已存放其他商品（{conflict_product}），一个库位只能存放一种商品')

    # 查询原库位的库存（该商品在该库位的所有批次库存，按生产日期排序）
    source_inventories = Inventory.query.filter_by(
        product_id=product_id,
        location_id=source_location_id
    ).filter(Inventory.quantity > 0).order_by(Inventory.production_date.asc()).all()

    # 检查库存是否充足
    total_available = sum(inv.quantity for inv in source_inventories)
    if total_available < quantity:
        raise ValueError(f'原库位库存不足: 商品ID{product_id}, 库位ID{source_location_id}, 需要数量{quantity}, 可用数量{total_available}')

    # 检查是否有冻结库存
    frozen_inventories = [inv for inv in source_inventories if inv.stock_status == 'frozen']
    if frozen_inventories:
        available_inventories = [inv for inv in source_inventories if inv.stock_status != 'frozen']
        available_qty = sum(inv.quantity for inv in available_inventories)
        if available_qty < quantity:
            raise ValueError(f'原库位可用库存不足（部分库存已冻结）: 商品ID{product_id}, 库位ID{source_location_id}')
        source_inventories = available_inventories

    # 按先进先出原则扣减原库位库存
    remaining_qty = quantity
    transfer_records = []  # 记录转移的批次和数量

    for source_inv in source_inventories:
        if remaining_qty <= 0:
            break

        if source_inv.quantity <= remaining_qty:
            # 该批次库存全部转移
            transfer_qty = source_inv.quantity
            batch_no = source_inv.batch_no
            production_date = source_inv.production_date
            expire_date = source_inv.expire_date

            # 删除原库位库存记录
            db.session.delete(source_inv)
            remaining_qty -= transfer_qty
        else:
            # 部分转移
            transfer_qty = remaining_qty
            batch_no = source_inv.batch_no
            production_date = source_inv.production_date
            expire_date = source_inv.expire_date

            # 扣减原库位库存
            source_inv.quantity -= transfer_qty
            remaining_qty = 0

        # 记录转移信息
        transfer_records.append({
            'batch_no': batch_no,
            'quantity': transfer_qty,
            'production_date': production_date,
            'expire_date': expire_date
        })

    # 增加目标库位库存（按批次分别处理）
    for record in transfer_records:
        target_inv = Inventory.query.filter_by(
            product_id=product_id,
            location_id=target_location_id,
            batch_no=record['batch_no']
        ).first()

        if target_inv:
            # 目标库位已有该批次库存，增加数量
            target_inv.quantity += record['quantity']
        else:
            # 目标库位没有该批次库存，创建新记录
            target_inv = Inventory(
                product_id=product_id,
                location_id=target_location_id,
                batch_no=record['batch_no'],
                quantity=record['quantity'],
                production_date=record['production_date'],
                expire_date=record['expire_date'],
                stock_status='normal'
            )
            db.session.add(target_inv)

    return True
