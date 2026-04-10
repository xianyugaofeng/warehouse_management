#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调拨单数据样例初始化脚本
"""

import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app import create_app, db
from app.models.transfer import TransferOrder, TransferItem
from app.models.product import Product
from app.models.inventory import WarehouseLocation, Inventory
from app.models.user import User
from app.utils.helpers import generate_transfer_no, execute_transfer


def init_transfer_orders():
    """初始化调拨单样例"""
    app = create_app()
    with app.app_context():
        # 获取必要的数据
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print('管理员用户不存在，请先运行 information_shell.py 初始化基础数据')
            return
        
        products = Product.query.all()
        if not products:
            print('商品不存在，请先运行 product_shell.py 添加商品样例')
            return
        
        locations = WarehouseLocation.query.filter_by(status=True).all()
        if len(locations) < 4:
            print('库位数量不足，至少需要4个库位才能进行调拨')
            return
        
        # 检查是否有库存
        if Inventory.query.count() == 0:
            print('库存不存在，请先运行 inventory_shell.py 添加入库单')
            return
        
        # 检查是否已有调拨单
        if TransferOrder.query.count() > 0:
            print('调拨单已存在')
            return
        
        # 获取所有库存记录
        all_inventories = Inventory.query.filter(Inventory.quantity > 0).all()
        if len(all_inventories) < 2:
            print('库存数量不足，至少需要2条库存记录才能进行调拨')
            return
        
        # 找出空闲库位（没有库存的库位）
        used_location_ids = [inv.location_id for inv in all_inventories]
        free_locations = [loc for loc in locations if loc.id not in used_location_ids]
        
        if len(free_locations) < 2:
            print('空闲库位不足，至少需要2个空闲库位才能进行调拨')
            return
        
        # 创建调拨单1：将前两个库存商品调拨到空闲库位
        order_no = generate_transfer_no()
        transfer_order1 = TransferOrder(
            order_no=order_no,
            creator_id=admin.id,
            audit_status='approved',
            remark='商品库位调拨（初始化数据）'
        )
        db.session.add(transfer_order1)
        db.session.flush()
        
        # 添加调拨明细
        transfer_count = 0
        for i, inventory in enumerate(all_inventories[:2]):
            if inventory.quantity >= 2:
                target_location = free_locations[i]
                item = TransferItem(
                    order_id=transfer_order1.id,
                    product_id=inventory.product_id,
                    source_location_id=inventory.location_id,
                    target_location_id=target_location.id,
                    quantity=2
                )
                db.session.add(item)
                transfer_count += 1
        
        # 执行调拨（库存转移）
        if transfer_count > 0:
            for item in transfer_order1.items:
                execute_transfer(
                    product_id=item.product_id,
                    source_location_id=item.source_location_id,
                    target_location_id=item.target_location_id,
                    quantity=item.quantity
                )
            
            # 设置审核信息
            transfer_order1.auditor_id = admin.id
            transfer_order1.audit_time = datetime.utcnow()
            
            print(f'调拨单创建成功：{transfer_order1.order_no}，调拨商品数量：{transfer_count}')
        else:
            db.session.delete(transfer_order1)
            print('调拨单创建失败：没有足够的库存进行调拨')
        
        db.session.commit()
        print('调拨单样例添加成功')


def main():
    """主函数"""
    print('开始初始化调拨单数据样例...')
    init_transfer_orders()
    print('调拨单数据样例初始化完成')


if __name__ == '__main__':
    main()