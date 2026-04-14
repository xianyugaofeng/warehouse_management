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
from app.views.check_manage import CheckInventoryHelper


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
        
        # 创建辅助函数实例
        helper = CheckInventoryHelper()
        
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
        
        # 获取前3个商品的库存
        inventories = []
        for product in products[:3]:
            inventory = Inventory.query.filter_by(product_id=product.id).first()
            if inventory:
                inventories.append(inventory)
        
        if inventories:
            # 使用辅助函数添加库存明细并冻结库存
            helper._add_inventory_items(completed_check, inventories, check_no)
            # 创建盘点结果记录
            helper._create_check_results(completed_check)
            db.session.flush()
            
            # 添加盘点结果（假设实际数量与账面数量一致）
            for result in completed_check.results.all():
                result.actual_quantity = result.book_quantity
                result.diff_quantity = 0
                result.check_result = 'equal'
                result.check_time = datetime.utcnow()
            
            # 处理盘点结果
            helper._process_check_results(completed_check, completed_check.results.all())
        
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
        
        # 获取接下来3个商品的库存
        inventories = []
        for product in products[3:6]:
            inventory = Inventory.query.filter_by(product_id=product.id).first()
            if inventory:
                inventories.append(inventory)
        
        if inventories:
            # 使用辅助函数添加库存明细并冻结库存
            helper._add_inventory_items(pending_check, inventories, check_no)
            # 创建盘点结果记录
            helper._create_check_results(pending_check)
        
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
        
        # 获取接下来2个商品的库存
        inventories = []
        for product in products[6:8]:
            inventory = Inventory.query.filter_by(product_id=product.id).first()
            if inventory:
                inventories.append(inventory)
        
        if inventories:
            # 使用辅助函数添加库存明细
            helper._add_inventory_items(canceled_check, inventories, check_no)
            # 创建盘点结果记录
            helper._create_check_results(canceled_check)
            
            # 解冻库存（因为是已取消的盘点单）
            for item in canceled_check.items:
                inv = Inventory.query.filter_by(
                    product_id=item.product_id,
                    location_id=item.location_id
                ).first()
                if inv and inv.stock_status == 'frozen':
                    inv.stock_status = 'normal'
                    inv.status_remark = None
        
        db.session.commit()
        print('盘点单样例添加成功（包含1个已完成、1个待录入、1个已取消的盘点单）')


def main():
    """主函数"""
    print('开始初始化盘点数据样例...')
    init_check_inventories()
    print('盘点数据样例初始化完成')


if __name__ == '__main__':
    main()