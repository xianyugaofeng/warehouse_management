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


# 生成采购单号（PO+日期+3位随机数）
def generate_purchase_no():
    date_str = datetime.now().strftime('%Y%m%d')
    random_str = str(random.randint(100, 999))
    return f'PO{date_str}{random_str}'


# 生成检验单号（QO+日期+3位随机数）
def generate_inspection_no():
    date_str = datetime.now().strftime('%Y%m%d')
    random_str = str(random.randint(100, 999))
    return f'QO{date_str}{random_str}'


# 生成退货单号（RT+日期+3位随机数）
def generate_return_no():
    date_str = datetime.now().strftime('%Y%m%d')
    random_str = str(random.randint(100, 999))
    return f'RT{date_str}{random_str}'


def recommend_location(product_id, locations):
    """
    根据库位状态（是否空闲、是否同品）自动推荐一个最佳库位
    优先级: 1. 同品且有库存的库位 2. 空闲库位 3. 任意正常库位
    """
    from app.models.inventory import Inventory
    
    if not locations:
        return None
    
    # 查找同品且有库存的库位
    same_product_locations = []
    for location in locations:
        inventory = Inventory.query.filter_by(product_id=product_id, location_id=location.id).first()
        if inventory and inventory.quantity > 0:
            same_product_locations.append(location)
    if same_product_locations:
        return same_product_locations[0]

    # 查找空闲库位（无库存的库位）
    free_locations = []
    for location in locations:
        inventory = Inventory.query.filter_by(location_id=location.id).first()
        if not inventory or inventory.quantity == 0:
            free_locations.append(location)
    if free_locations:
        return free_locations[0]

    # 返回任意正常库位
    return locations[0]
    
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




