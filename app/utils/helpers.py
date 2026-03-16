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

# 生成盘点任务单号(COUNT+日期+3位随机数)
def generate_inventory_count_task_no():
    date_str = datetime.now().strftime('%Y%m%d')
    random_str = str(random.randint(100, 999))
    return f'COUNT{date_str}{random_str}'

# 生成库存调整单号(ADJ+日期+3位随机数)
def generate_inventory_adjustment_no():
    date_str = datetime.now().strftime('%Y%m%d')
    random_str = str(random.randint(100, 999))
    return f'ADJ{date_str}{random_str}'
    
# 库存更新函数(入库时增加在途库存, 出库时增加已分配库存)
def update_inventory(product_id, location_id, batch_no, quantity, is_bound=True):
    from app import db
    from app.models.inventory import Inventory
    
    # 查询是否存在该商品-库位-批次的库存记录
    inventory = Inventory.query.filter_by(
        product_id=product_id,
        location_id=location_id,
        batch_no=batch_no
    ).first()   # 返回一个inventory对象
    
    # 入库操作：增加在途库存
    if is_bound:
        # 入库时不再直接更新实物库存，而是通过盘点任务同步
        # 只创建库存记录（如果不存在），但数量保持为0
        if not inventory:
            inventory = Inventory(
                product_id=product_id,
                location_id=location_id,
                batch_no=batch_no,
                quantity=0  # 初始数量为0
            )
            db.session.add(inventory)
        # 增加系统账面库存的在途库存
        inventory.quantity += quantity;
    else:
        # 出库操作：增加已分配库存
        if not inventory:
            raise ValueError(f'<库存不足:商品ID{product_id},  库位ID{location_id}, 批次{batch_no}')
        
        if not inventory:
            raise ValueError(f'<系统账面库存不存在:商品ID{product_id},  库位ID{location_id}, 批次{batch_no}')
        
        if inventory.quantity < quantity:
            raise ValueError(f'<库存不足:商品ID{product_id},  库位ID{location_id}, 批次{batch_no}')
        
        inventory.quantity -= quantity

    db.session.commit()
    return inventory


def sync_book_inventory(product_id, location_id, batch_no):
    """
    同步系统账面库存与实物库存
    确保系统账面库存的账面数量部分与实物库存表保持一致
    """
    from app import db
    from app.models.inventory import Inventory
    from app.models.inventory_count import BookInventory
    
    # 获取实物库存
    inventory = Inventory.query.filter_by(
        product_id=product_id,
        location_id=location_id,
        batch_no=batch_no
    ).first()
    
    # 获取或创建系统账面库存
    book_inventory = BookInventory.query.filter_by(
        product_id=product_id,
        location_id=location_id,
        batch_no=batch_no
    ).first()
    
    if not book_inventory:
        book_inventory = BookInventory(
            product_id=product_id,
            location_id=location_id,
            batch_no=batch_no,
            book_quantity=inventory.quantity if inventory else 0,
            in_transit_quantity=0,
            allocated_quantity=0
        )
        db.session.add(book_inventory)
    else:
        # 更新系统账面库存的账面数量部分
        inventory.quantity = (book_inventory.book_quantity + 
                              book_inventory.in_transit_quantity -
                              book_inventory.allocated_quantity)
        book_inventory.book_quantity = inventory.quantity
        book_inventory.in_transit_quantity = 0
        book_inventory.allocated_quantity = 0
                              
        
    db.session.commit()
    return book_inventory


def update_book_inventory(product_id, location_id, batch_no, book_change=0, in_transit_change=0, allocated_change=0):
    """
    更新系统账面库存
    参数:
        book_change: 账面数量变化量（正数增加，负数减少）
        in_transit_change: 在途数量变化量（正数增加，负数减少）
        allocated_change: 已分配数量变化量（正数增加，负数减少）
    """
    from app import db
    from app.models.inventory_count import BookInventory
    
    # 获取或创建系统账面库存
    book_inventory = BookInventory.query.filter_by(
        product_id=product_id,
        location_id=location_id,
        batch_no=batch_no
    ).first()
    
    if not book_inventory:
        book_inventory = BookInventory(
            product_id=product_id,
            location_id=location_id,
            batch_no=batch_no,
            book_quantity=0,
            in_transit_quantity=0,
            allocated_quantity=0
        )
        db.session.add(book_inventory)
    
    # 更新各部分库存
    book_inventory.book_quantity += book_change
    book_inventory.in_transit_quantity += in_transit_change
    book_inventory.allocated_quantity += allocated_change
    
    # 验证系统账面库存
    if not book_inventory.is_available_quantity_valid:
        raise ValueError(f'系统账面库存计算错误: 商品ID{product_id}, 库位ID{location_id}, 批次{batch_no}')
    
    db.session.commit()
    return book_inventory


def validate_book_inventory(book_inventory, tolerance=0):
    """
    验证系统账面库存是否有效
    参数:
        book_inventory: 系统账面库存对象
        tolerance: 允许的误差范围
    返回:
        (is_valid, message) 验证结果和消息
    """
    if not book_inventory:
        return False, '系统账面库存不存在'
    
    # 验证各部分库存不能为负数
    if book_inventory.book_quantity < 0:
        return False, f'账面数量不能为负数: {book_inventory.book_quantity}'
    
    if book_inventory.in_transit_quantity < 0:
        return False, f'在途数量不能为负数: {book_inventory.in_transit_quantity}'
    
    if book_inventory.allocated_quantity < 0:
        return False, f'已分配数量不能为负数: {book_inventory.allocated_quantity}'
    
    # 验证系统账面库存计算
    calculated_available = (book_inventory.book_quantity + 
                           book_inventory.in_transit_quantity - 
                           book_inventory.allocated_quantity)
    
    if abs(calculated_available - book_inventory.available_quantity) > tolerance:
        return False, f'可用库存计算错误: 计算值{calculated_available}, 当前值{book_inventory.available_quantity}'
    
    return True, '验证通过'

