#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘点数据样例初始化脚本
"""

import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app import create_app, db
from app.models.check import CheckInventory, CheckInventoryItem, CheckInventoryResult
from app.models.product import Product, Category
from app.models.inventory import WarehouseLocation, Inventory
from app.models.user import User
from app.utils.helpers import generate_check_no


def init_check_inventories():
    """初始化盘点单样例"""
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
        if not locations:
            print('库位不存在，请先运行 information_shell.py 初始化基础数据')
            return
        
        # 检查是否有库存
        if Inventory.query.count() == 0:
            print('库存不存在，请先运行 inventory_shell.py 添加入库单')
            return
        
        # 检查是否已有盘点单
        if CheckInventory.query.count() > 0:
            print('盘点单已存在')
            return
        
        # 1. 创建已完成的盘点单
        check_no = generate_check_no()
        completed_check = CheckInventory(
            check_no=check_no,
            check_status='completed',
            checker_id=admin.id,
            remark='',
            frozen_status=False
        )
        db.session.add(completed_check)
        db.session.flush()
        
        # 添加盘点明细和结果
        for i, product in enumerate(products[:3]):
            # 获取商品库存
            inventory = Inventory.query.filter_by(product_id=product.id).first()
            if inventory:
                # 添加盘点明细
                item = CheckInventoryItem(
                    check_inventory_id=completed_check.id,
                    product_id=product.id,
                    location_id=inventory.location_id,
                    book_quantity=inventory.quantity
                )
                db.session.add(item)
                db.session.flush()
                
                # 添加盘点结果（假设实际数量与账面数量一致）
                result = CheckInventoryResult(
                    check_inventory_id=completed_check.id,
                    check_item_id=item.id,
                    book_quantity=inventory.quantity,
                    actual_quantity=inventory.quantity,
                    diff_quantity=0,
                    check_result='equal'
                )
                db.session.add(result)
        
        # 2. 创建待录入的盘点单
        check_no = generate_check_no()
        pending_check = CheckInventory(
            check_no=check_no,
            check_status='pending',
            checker_id=admin.id,
            remark='',
            frozen_status=True
        )
        db.session.add(pending_check)
        db.session.flush()
        
        # 添加盘点明细
        for i, product in enumerate(products[3:6]):
            # 获取商品库存
            inventory = Inventory.query.filter_by(product_id=product.id).first()
            if inventory:
                # 添加盘点明细
                item = CheckInventoryItem(
                    check_inventory_id=pending_check.id,
                    product_id=product.id,
                    location_id=inventory.location_id,
                    book_quantity=inventory.quantity
                )
                db.session.add(item)
                db.session.flush()
                
                # 添加盘点结果（初始状态）
                result = CheckInventoryResult(
                    check_inventory_id=pending_check.id,
                    check_item_id=item.id,
                    book_quantity=inventory.quantity,
                    actual_quantity=None,
                    diff_quantity=0,
                    check_result='pending'
                )
                db.session.add(result)
                
                # 冻结库存
                inventory.stock_status = 'frozen'
                inventory.status_remark = f'盘点冻结 - {check_no}'
        
        # 3. 创建已取消的盘点单
        check_no = generate_check_no()
        canceled_check = CheckInventory(
            check_no=check_no,
            check_status='canceled',
            checker_id=admin.id,
            remark='',
            frozen_status=False
        )
        db.session.add(canceled_check)
        db.session.flush()
        
        # 添加盘点明细
        for i, product in enumerate(products[6:8]):
            # 获取商品库存
            inventory = Inventory.query.filter_by(product_id=product.id).first()
            if inventory:
                # 添加盘点明细
                item = CheckInventoryItem(
                    check_inventory_id=canceled_check.id,
                    product_id=product.id,
                    location_id=inventory.location_id,
                    book_quantity=inventory.quantity
                )
                db.session.add(item)
                db.session.flush()
                
                # 添加盘点结果（初始状态）
                result = CheckInventoryResult(
                    check_inventory_id=canceled_check.id,
                    check_item_id=item.id,
                    book_quantity=inventory.quantity,
                    actual_quantity=None,
                    diff_quantity=0,
                    check_result='pending'
                )
                db.session.add(result)
        
        db.session.commit()
        print('盘点单样例添加成功（包含1个已完成、1个待录入、1个已取消的盘点单）')


def main():
    """主函数"""
    print('开始初始化盘点数据样例...')
    init_check_inventories()
    print('盘点数据样例初始化完成')


if __name__ == '__main__':
    main()