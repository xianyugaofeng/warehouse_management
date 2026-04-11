from flask import Blueprint, render_template, request
from flask_login import login_required
from datetime import datetime, timedelta
from app import db
from app.models.inbound import InboundOrder, InboundItem
from app.models.outbound import OutboundOrder, OutboundItem
from app.models.inventory import Inventory
from app.models.product import Product
from app.utils.auth import permission_required


report_bp = Blueprint('report', __name__)

# 库存商品列表
@report_bp.route('/inventory_products')
@permission_required('report_view')
@login_required
def inventory_products():
    # 库存所有商品(按数量排序)
    inventory_products_result = db.session.query(
        Product.name, Product.code, db.func.sum(Inventory.quantity).label('total_quantity')
    ).join(Inventory).group_by(Product.id).order_by(db.func.sum(Inventory.quantity).desc()).all()
    # 查询会返回一个包含元组的列表，每个元组包含产品名称、产品代码和该产品的总库存量
    # (name, code, total_quantity)
    
    # 将查询结果转换为字典列表，以便在模板中使用
    inventory_products = []
    for product in inventory_products_result:
        inventory_products.append({
            'name': product[0],
            'code': product[1],
            'total_quantity': float(product[2])
        })

    return render_template('report/inventory_products.html',
                           inventory_products=inventory_products)

# 综合报表（整合出入库趋势和库存健康度分析）
@report_bp.route('/dashboard')
@permission_required('report_view')
@login_required
def dashboard():
    # 1. 近30天出入库趋势数据
    end_date = datetime.now().date()
    start_date = (datetime.now() - timedelta(days=30)).date()

    # 入库趋势
    inbound_trend = db.session.query(
        InboundOrder.inbound_date.label('date'),
        db.func.sum(InboundItem.quantity).label('total')
    ).join(InboundItem).filter(InboundOrder.inbound_date >= start_date,
                               InboundOrder.inbound_date <= end_date
    ).group_by(InboundOrder.inbound_date).order_by(InboundOrder.inbound_date).all()

    # 出库趋势
    outbound_trend = db.session.query(
        OutboundOrder.outbound_date.label('date'),
        db.func.sum(OutboundItem.quantity).label('total'),
    ).join(OutboundItem).filter(OutboundOrder.outbound_date >= start_date,
                                OutboundOrder.outbound_date <= end_date
    ).group_by(OutboundOrder.outbound_date).order_by(OutboundOrder.outbound_date).all()

    # 格式化出入库趋势数据(适配Echart)
    dates = [d.strftime('%Y-%m-%d') for d in [start_date + timedelta(days=i) for i in range(31)]]
    inbound_data = [0] * 31
    outbound_data = [0] * 31

    for item in inbound_trend:
        idx = (item.date - start_date).days
        if 0 <= idx < 31:
            inbound_data[idx] = float(item.total)

    for item in outbound_trend:
        idx = (item.date - start_date).days
        if 0 <= idx < 31:
            outbound_data[idx] = float(item.total)

    # 2. 库存健康度分析数据
    # 总库存数量
    total_inventory = db.session.query(db.func.sum(Inventory.quantity)).scalar() or 0
    total_inventory = float(total_inventory)
    
    # 预警库存数量（库存数量小于等于预警阈值的商品的库存总和）
    warning_inventory = db.session.query(db.func.sum(Inventory.quantity)).join(
        Product
    ).filter(
        Inventory.quantity <= Product.warning_stock
    ).scalar() or 0
    warning_inventory = float(warning_inventory)
    
    # 健康库存数量
    healthy_inventory = total_inventory - warning_inventory
    
    # 总商品数
    total_product_count = Product.query.count()
    
    # 健康度评分（基于库存数量和预警比例）
    if total_inventory > 0:
        # 计算预警库存比例
        warning_ratio = warning_inventory / total_inventory
        
        # 健康度评分计算：
        # - 如果预警比例为0，健康度为100%
        # - 如果预警比例在0-50%之间，健康度线性下降
        # - 如果预警比例超过50%，健康度下降更快
        if warning_ratio == 0:
            health_score = 100
        elif warning_ratio <= 0.5:
            # 0-50%预警比例，健康度从100%线性下降到70%
            health_score = 100 - (warning_ratio * 60)
        else:
            # 50-100%预警比例，健康度从70%线性下降到0%
            health_score = 70 - ((warning_ratio - 0.5) * 140)
    else:
        health_score = 0
    
    # 库存周转情况（简单计算）
    # 近30天入库总量
    inbound_total = db.session.query(db.func.sum(InboundItem.quantity)).join(
        InboundOrder
    ).filter(
        InboundOrder.inbound_date >= start_date,
        InboundOrder.inbound_date <= end_date
    ).scalar() or 0
    inbound_total = float(inbound_total)
    
    # 近30天出库总量
    outbound_total = db.session.query(db.func.sum(OutboundItem.quantity)).join(
        OutboundOrder
    ).filter(
        OutboundOrder.outbound_date >= start_date,
        OutboundOrder.outbound_date <= end_date
    ).scalar() or 0
    outbound_total = float(outbound_total)
    
    return render_template('report/dashboard.html',
                           # 出入库趋势数据
                           dates=dates,
                           inbound_data=inbound_data,
                           outbound_data=outbound_data,
                           # 库存健康度数据
                           total_inventory=total_inventory,
                           healthy_inventory=healthy_inventory,
                           warning_inventory=warning_inventory,
                           total_product_count=total_product_count,
                           health_score=health_score,
                           inbound_total=inbound_total,
                           outbound_total=outbound_total)

# 入库报表
@report_bp.route('/inbound_report')
@permission_required('report_view')
@login_required
def inbound_report():
    # 查询每个商品的入库总数和当前库存
    inbound_data = db.session.query(
        Product.name.label('product_name'),
        Product.code.label('product_code'),
        db.func.sum(InboundItem.quantity).label('inbound_quantity'),
        db.func.sum(Inventory.quantity).label('inventory_quantity')
    ).outerjoin(
        InboundItem, Product.id == InboundItem.product_id
    ).outerjoin(
        Inventory, Product.id == Inventory.product_id
    ).group_by(Product.id).order_by(db.func.sum(InboundItem.quantity).desc()).all()
    
    # 转换为字典列表
    report_data = []
    max_quantity = 0
    for item in inbound_data:
        inbound_qty = float(item.inbound_quantity) if item.inbound_quantity else 0
        inventory_qty = float(item.inventory_quantity) if item.inventory_quantity else 0
        report_data.append({
            'product_name': item.product_name,
            'product_code': item.product_code,
            'inbound_quantity': inbound_qty,
            'inventory_quantity': inventory_qty
        })
        if inbound_qty > max_quantity:
            max_quantity = inbound_qty
    
    return render_template('report/inbound_report.html',
                           report_data=report_data,
                           max_quantity=max_quantity)

# 出库报表
@report_bp.route('/outbound_report')
@permission_required('report_view')
@login_required
def outbound_report():
    # 查询每个商品的出库总数和当前库存
    outbound_data = db.session.query(
        Product.name.label('product_name'),
        Product.code.label('product_code'),
        db.func.sum(OutboundItem.quantity).label('outbound_quantity'),
        db.func.sum(Inventory.quantity).label('inventory_quantity')
    ).outerjoin(
        OutboundItem, Product.id == OutboundItem.product_id
    ).outerjoin(
        Inventory, Product.id == Inventory.product_id
    ).group_by(Product.id).order_by(db.func.sum(OutboundItem.quantity).desc()).all()
    
    # 转换为字典列表
    report_data = []
    max_quantity = 0
    for item in outbound_data:
        outbound_qty = float(item.outbound_quantity) if item.outbound_quantity else 0
        inventory_qty = float(item.inventory_quantity) if item.inventory_quantity else 0
        report_data.append({
            'product_name': item.product_name,
            'product_code': item.product_code,
            'outbound_quantity': outbound_qty,
            'inventory_quantity': inventory_qty
        })
        if outbound_qty > max_quantity:
            max_quantity = outbound_qty
    
    return render_template('report/outbound_report.html',
                           report_data=report_data,
                           max_quantity=max_quantity)