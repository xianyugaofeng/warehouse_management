#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
出入库数据样例初始化脚本
"""

import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app import create_app, db
from app.models.inbound import InboundOrder, InboundItem
from app.models.outbound import OutboundOrder, OutboundItem
from app.models.product import Product, Supplier, Customer
from app.models.inventory import WarehouseLocation, Inventory
from app.models.user import User
from app.utils.helpers import generate_inbound_no, generate_outbound_no, update_inventory


def init_inbound_orders():
    """初始化入库单样例"""
    app = create_app()
    with app.app_context():
        # 获取必要的数据
        supplier = Supplier.query.first()
        if not supplier:
            print('供应商不存在，请先运行 information_shell.py 初始化基础数据')
            return
        
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print('管理员用户不存在，请先运行 information_shell.py 初始化基础数据')
            return
        
        products = Product.query.all()
        if not products:
            print('商品不存在，请先运行 product_shell.py 添加商品样例')
            return
        
        location = WarehouseLocation.query.first()
        if not location:
            print('库位不存在，请先运行 information_shell.py 初始化基础数据')
            return
        
        # 检查是否已有入库单
        if InboundOrder.query.count() > 0:
            print('入库单已存在')
            return
        
        # 创建入库单1：电脑商品入库
        order_no = generate_inbound_no()
        inbound_order1 = InboundOrder(
            order_no=order_no,
            supplier_id=supplier.id,
            operator_id=admin.id,
            inbound_date=datetime.now().date(),
            total_amount=15,
            remark='电脑商品批量入库'
        )
        db.session.add(inbound_order1)
        db.session.flush()
        
        # 添加入库明细
        computer_products = [p for p in products if p.category.name == '电脑']
        for i, product in enumerate(computer_products):
            item = InboundItem(
                order_id=inbound_order1.id,
                product_id=product.id,
                location_id=location.id,
                quantity=5,
                batch_no=f'IN-{datetime.now().strftime("%Y%m%d")}-{i+1}',
                production_date=datetime.now().date() - timedelta(days=30),
                expire_date=datetime.now().date() + timedelta(days=365)
            )
            db.session.add(item)
            # 更新库存
            update_inventory(product.id, location.id, item.batch_no, 5, is_bound=True)
        
        # 创建入库单2：手机商品入库
        order_no = generate_inbound_no()
        inbound_order2 = InboundOrder(
            order_no=order_no,
            supplier_id=supplier.id,
            operator_id=admin.id,
            inbound_date=datetime.now().date(),
            total_amount=10,
            remark='手机商品批量入库'
        )
        db.session.add(inbound_order2)
        db.session.flush()
        
        # 添加入库明细
        phone_products = [p for p in products if p.category.name == '手机']
        for i, product in enumerate(phone_products):
            item = InboundItem(
                order_id=inbound_order2.id,
                product_id=product.id,
                location_id=location.id,
                quantity=5,
                batch_no=f'IN-{datetime.now().strftime("%Y%m%d")}-{i+10}',
                production_date=datetime.now().date() - timedelta(days=30),
                expire_date=datetime.now().date() + timedelta(days=365)
            )
            db.session.add(item)
            # 更新库存
            update_inventory(product.id, location.id, item.batch_no, 5, is_bound=True)
        
        db.session.commit()
        print('入库单样例添加成功')


def init_outbound_orders():
    """初始化出库单样例"""
    app = create_app()
    with app.app_context():
        # 获取必要的数据
        customer = Customer.query.first()
        if not customer:
            print('客户不存在，请先运行 information_shell.py 初始化基础数据')
            return
        
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print('管理员用户不存在，请先运行 information_shell.py 初始化基础数据')
            return
        
        products = Product.query.all()
        if not products:
            print('商品不存在，请先运行 product_shell.py 添加商品样例')
            return
        
        # 检查是否有库存
        if Inventory.query.count() == 0:
            print('库存不存在，请先运行 init_inbound_orders() 添加入库单')
            return
        
        # 检查是否已有出库单
        if OutboundOrder.query.count() > 0:
            print('出库单已存在')
            return
        
        # 创建出库单1：电脑商品出库
        order_no = generate_outbound_no()
        outbound_order1 = OutboundOrder(
            order_no=order_no,
            customer_id=customer.id,
            operator_id=admin.id,
            receive_phone=customer.phone,
            outbound_date=datetime.now().date(),
            total_amount=4,
            remark='电脑商品出库'
        )
        db.session.add(outbound_order1)
        db.session.flush()
        
        # 添加出库明细
        computer_products = [p for p in products if p.category.name == '电脑'][:2]
        for i, product in enumerate(computer_products):
            # 获取商品库存
            inventory = Inventory.query.filter_by(product_id=product.id).first()
            if inventory:
                item = OutboundItem(
                    order_id=outbound_order1.id,
                    product_id=product.id,
                    location_id=inventory.location_id,
                    quantity=2,
                    batch_no=inventory.batch_no
                )
                db.session.add(item)
                # 更新库存
                update_inventory(product.id, inventory.location_id, inventory.batch_no, 2, is_bound=False)
        
        # 创建出库单2：手机商品出库
        order_no = generate_outbound_no()
        outbound_order2 = OutboundOrder(
            order_no=order_no,
            customer_id=customer.id,
            operator_id=admin.id,
            receive_phone=customer.phone,
            outbound_date=datetime.now().date(),
            total_amount=2,
            remark='手机商品出库'
        )
        db.session.add(outbound_order2)
        db.session.flush()
        
        # 添加出库明细
        phone_products = [p for p in products if p.category.name == '手机'][:1]
        for i, product in enumerate(phone_products):
            # 获取商品库存
            inventory = Inventory.query.filter_by(product_id=product.id).first()
            if inventory:
                item = OutboundItem(
                    order_id=outbound_order2.id,
                    product_id=product.id,
                    location_id=inventory.location_id,
                    quantity=2,
                    batch_no=inventory.batch_no
                )
                db.session.add(item)
                # 更新库存
                update_inventory(product.id, inventory.location_id, inventory.batch_no, 2, is_bound=False)
        
        db.session.commit()
        print('出库单样例添加成功')


def main():
    """主函数"""
    print('开始初始化出入库数据样例...')
    init_inbound_orders()
    init_outbound_orders()
    print('出入库数据样例初始化完成')


if __name__ == '__main__':
    main()