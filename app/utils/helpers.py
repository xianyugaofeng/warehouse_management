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
                quantity=quantity
            )
            db.session.add(inventory)
    else:
        if not inventory or inventory.quantity < quantity:
            raise ValueError(f'<库存不足:商品ID{product_id},  库位ID{location_id}, 批次{batch_no}')
        inventory.quantity -= quantity
        # 库存为0时是否删除记录
        if inventory.quantity == 0:
            db.session.delete(inventory)

    db.session.commit()
    return inventory


def sync_virtual_inventory(product_id, location_id, batch_no):
    """同步虚拟库存与实物库存
    确保虚拟库存的实物库存部分与实物库存表保持一致
    """
    from app import db
    from app.models.inventory import Inventory
    from app.models.inventory_count import VirtualInventory
    
    # 获取实物库存
    inventory = Inventory.query.filter_by(
        product_id=product_id,
        location_id=location_id,
        batch_no=batch_no
    ).first()
    
    # 获取虚拟库存
    virtual_inventory = VirtualInventory.query.filter_by(
        product_id=product_id,
        location_id=location_id,
        batch_no=batch_no
    ).first()
    
    if virtual_inventory:
        # 更新虚拟库存的实物库存部分
        if inventory:
            virtual_inventory.physical_quantity = inventory.quantity
        else:
            virtual_inventory.physical_quantity = 0
        db.session.commit()
    
    return virtual_inventory


def update_virtual_inventory(product_id, location_id, batch_no, physical_change=0, in_transit_change=0, allocated_change=0):
    """更新虚拟库存
    参数:
        physical_change: 实物库存变化量（正数增加，负数减少）
        in_transit_change: 在途库存变化量（正数增加，负数减少）
        allocated_change: 已分配库存变化量（正数增加，负数减少）
    """
    from app import db
    from app.models.inventory_count import VirtualInventory
    
    # 获取或创建虚拟库存
    virtual_inventory = VirtualInventory.query.filter_by(
        product_id=product_id,
        location_id=location_id,
        batch_no=batch_no
    ).first()
    
    if not virtual_inventory:
        virtual_inventory = VirtualInventory(
            product_id=product_id,
            location_id=location_id,
            batch_no=batch_no,
            physical_quantity=0,
            in_transit_quantity=0,
            allocated_quantity=0
        )
        db.session.add(virtual_inventory)
    
    # 更新各部分库存
    virtual_inventory.physical_quantity += physical_change
    virtual_inventory.in_transit_quantity += in_transit_change
    virtual_inventory.allocated_quantity += allocated_change
    
    # 验证虚拟库存
    if not virtual_inventory.is_virtual_quantity_valid:
        raise ValueError(f'虚拟库存计算错误: 商品ID{product_id}, 库位ID{location_id}, 批次{batch_no}')
    
    db.session.commit()
    return virtual_inventory


def validate_virtual_inventory(virtual_inventory, tolerance=0):
    """验证虚拟库存是否有效
    参数:
        virtual_inventory: 虚拟库存对象
        tolerance: 允许的误差范围
    返回:
        (is_valid, message) 验证结果和消息
    """
    if not virtual_inventory:
        return False, '虚拟库存不存在'
    
    # 验证各部分库存不能为负数
    if virtual_inventory.physical_quantity < 0:
        return False, f'实物库存不能为负数: {virtual_inventory.physical_quantity}'
    
    if virtual_inventory.in_transit_quantity < 0:
        return False, f'在途库存不能为负数: {virtual_inventory.in_transit_quantity}'
    
    if virtual_inventory.allocated_quantity < 0:
        return False, f'已分配库存不能为负数: {virtual_inventory.allocated_quantity}'
    
    # 验证虚拟库存计算
    calculated_virtual = (virtual_inventory.physical_quantity + 
                         virtual_inventory.in_transit_quantity - 
                         virtual_inventory.allocated_quantity)
    
    if abs(calculated_virtual - virtual_inventory.virtual_quantity) > tolerance:
        return False, f'虚拟库存计算错误: 计算值{calculated_virtual}, 当前值{virtual_inventory.virtual_quantity}'
    
    return True, '验证通过'

