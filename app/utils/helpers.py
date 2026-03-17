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
    
# 库存更新函数(入库时增加库存, 出库时增加库存)
def update_inventory(product_id, location_id, batch_no, quantity, is_bound=True):
    from app import db
    from app.models.inventory import Inventory
    
    # 查询是否存在该商品-库位-批次的库存记录
    inventory = Inventory.query.filter_by(
        product_id=product_id,
        location_id=location_id,
        batch_no=batch_no
    ).first()   # 返回一个inventory对象
    
    # 入库操作
    if is_bound:
        # 只创建库存记录（如果不存在），但数量保持为0
        if not inventory:
            inventory = Inventory(
                product_id=product_id,
                location_id=location_id,
                batch_no=batch_no,
                quantity=0  # 初始数量为0
            )
            db.session.add(inventory)
        inventory.quantity += quantity
    else:
        # 出库操作
        if not inventory:
            raise ValueError(f'<库存不足:商品ID{product_id},  库位ID{location_id}, 批次{batch_no}')
        
        if not inventory.quantity:
            raise ValueError(f'<系统账面库存不存在:商品ID{product_id},  库位ID{location_id}, 批次{batch_no}')
        
        if inventory.quantity < quantity:
            raise ValueError(f'<库存不足:商品ID{product_id},  库位ID{location_id}, 批次{batch_no}')
        
        inventory.quantity -= quantity

    db.session.commit()
    return inventory




