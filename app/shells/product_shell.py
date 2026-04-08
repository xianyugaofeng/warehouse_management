#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
商品样例初始化脚本
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app import create_app, db
from app.models.product import Product, Category, ProductParamValue, ProductParamKey, Supplier


def init_sample_products():
    """初始化商品样例"""
    app = create_app()
    with app.app_context():
        # 获取电脑分类
        category = Category.query.filter_by(name='电脑').first()
        if not category:
            print('电脑分类不存在，请先运行 information_shell.py 初始化基础数据')
            return
        
        # 添加华硕天选6
        # 检查商品是否已存在
        existing_product = Product.query.filter_by(name='华硕天选6').first()
        if not existing_product:
            # 获取供应商（使用第一个供应商）
            supplier = Supplier.query.first()
            supplier_id = supplier.id if supplier else None
            
            # 创建商品
            product = Product(
                code='ASUS-TX6-2026',
                name='华硕天选6',
                category_id=category.id,
                unit='台',
                warning_stock=5,
                remark='华硕天选6笔记本电脑，搭载锐龙7处理器和RTX 5050显卡'
            )
            db.session.add(product)
            db.session.flush()  # 获取商品ID但不提交事务
            
            # 添加商品参数
            params = {
                '品牌': '华硕（ASUS）',
                '显卡型号': 'RTX 5050',
                '处理器型号': '锐龙7 H 260',
                '屏幕尺寸': '16英寸',
                '存储容量': '16GB+512GB',
                '机型名称': '华硕天选6'
            }
            
            for param_name, param_value in params.items():
                # 查找或创建参数键
                param_key = ProductParamKey.query.filter_by(name=param_name).first()
                if not param_key:
                    param_key = ProductParamKey(name=param_name, desc=param_name)
                    db.session.add(param_key)
                    db.session.flush()
                
                # 创建参数值
                param_value_obj = ProductParamValue(
                    product_id=product.id,
                    param_key_id=param_key.id,
                    value=param_value
                )
                db.session.add(param_value_obj)
            
            # 提交商品和参数
            db.session.commit()
            print('华硕天选6商品添加成功')
        else:
            print('华硕天选6商品已存在')
        
        # 添加机械革命极光X
        # 检查商品是否已存在
        existing_product = Product.query.filter_by(name='机械革命极光X').first()
        if not existing_product:
            # 获取供应商（使用第一个供应商）
            supplier = Supplier.query.first()
            supplier_id = supplier.id if supplier else None
            
            # 创建商品
            product = Product(
                code='10181964004901',
                name='机械革命极光X',
                category_id=category.id,
                unit='台',
                warning_stock=5,
                remark='机械革命极光X笔记本电脑，搭载Intel Core i5处理器和RTX 5050显卡'
            )
            db.session.add(product)
            db.session.flush()  # 获取商品ID但不提交事务
            
            # 添加商品参数
            params = {
                '品牌': '机械革命（MECHREVO）',
                '显卡型号': 'RTX 5050',
                '处理器型号': 'Intel Core i5 14450HX',
                '屏幕尺寸': '16英寸',
                '存储容量': '16GB+1TB',
                '机型名称': '极光X'
            }
            
            for param_name, param_value in params.items():
                # 查找或创建参数键
                param_key = ProductParamKey.query.filter_by(name=param_name).first()
                if not param_key:
                    param_key = ProductParamKey(name=param_name, desc=param_name)
                    db.session.add(param_key)
                    db.session.flush()
                
                # 创建参数值
                param_value_obj = ProductParamValue(
                    product_id=product.id,
                    param_key_id=param_key.id,
                    value=param_value
                )
                db.session.add(param_value_obj)
            
            # 提交商品和参数
            db.session.commit()
            print('机械革命极光X商品添加成功')
        else:
            print('机械革命极光X商品已存在')
        
        # 添加小米REDMI K90手机
        # 检查商品是否已存在
        existing_product = Product.query.filter_by(name='小米 REDMI K90').first()
        if not existing_product:
            # 获取手机分类
            phone_category = Category.query.filter_by(name='手机').first()
            if phone_category:
                # 获取供应商（使用第一个供应商）
                supplier = Supplier.query.first()
                supplier_id = supplier.id if supplier else None
                
                # 创建商品
                product = Product(
                    code='100287758128',
                    name='小米 REDMI K90',
                    category_id=phone_category.id,
                    unit='台',
                    warning_stock=5,
                    remark='小米REDMI K90手机，搭载骁龙8至尊版处理器'
                )
                db.session.add(product)
                db.session.flush()  # 获取商品ID但不提交事务
                
                # 添加商品参数
                params = {
                    '品牌': '小米（MI）',
                    '屏幕尺寸': '6.59英寸',
                    '存储容量': '12GB+256GB',
                    '处理器型号': '骁龙8 至尊版',
                    '机型名称': '小米 REDMI K90'
                }
                
                for param_name, param_value in params.items():
                    # 查找或创建参数键
                    param_key = ProductParamKey.query.filter_by(name=param_name).first()
                    if not param_key:
                        param_key = ProductParamKey(name=param_name, desc=param_name)
                        db.session.add(param_key)
                        db.session.flush()
                    
                    # 创建参数值
                    param_value_obj = ProductParamValue(
                        product_id=product.id,
                        param_key_id=param_key.id,
                        value=param_value
                    )
                    db.session.add(param_value_obj)
                
                # 提交商品和参数
                db.session.commit()
                print('小米 REDMI K90手机添加成功')
            else:
                print('手机分类不存在，请先运行 information_shell.py 初始化基础数据')
        else:
            print('小米 REDMI K90手机已存在')
        
        # 添加vivo iQOO 15手机
        # 检查商品是否已存在
        existing_product = Product.query.filter_by(name='vivo iQOO 15').first()
        if not existing_product:
            # 获取手机分类
            phone_category = Category.query.filter_by(name='手机').first()
            if phone_category:
                # 获取供应商（使用第一个供应商）
                supplier = Supplier.query.first()
                supplier_id = supplier.id if supplier else None
                
                # 创建商品
                product = Product(
                    code='100283677974',
                    name='vivo iQOO 15',
                    category_id=phone_category.id,
                    unit='台',
                    warning_stock=5,
                    remark='vivo iQOO 15手机，搭载第五代骁龙8至尊版处理器'
                )
                db.session.add(product)
                db.session.flush()  # 获取商品ID但不提交事务
                
                # 添加商品参数
                params = {
                    '品牌': 'vivo',
                    '屏幕尺寸': '6.85英寸',
                    '处理器型号': '第五代骁龙8 至尊版',
                    '机型名称': 'vivo iQOO 15'
                }
                
                for param_name, param_value in params.items():
                    # 查找或创建参数键
                    param_key = ProductParamKey.query.filter_by(name=param_name).first()
                    if not param_key:
                        param_key = ProductParamKey(name=param_name, desc=param_name)
                        db.session.add(param_key)
                        db.session.flush()
                    
                    # 创建参数值
                    param_value_obj = ProductParamValue(
                        product_id=product.id,
                        param_key_id=param_key.id,
                        value=param_value
                    )
                    db.session.add(param_value_obj)
                
                # 提交商品和参数
                db.session.commit()
                print('vivo iQOO 15手机添加成功')
            else:
                print('手机分类不存在，请先运行 information_shell.py 初始化基础数据')
        else:
            print('vivo iQOO 15手机已存在')
        
        print('所有商品样例添加完成')


if __name__ == '__main__':
    init_sample_products()