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
