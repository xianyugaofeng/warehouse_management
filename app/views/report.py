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

# 库存Top10商品
@report_bp.route('/top_products')
@permission_required('report_view')
@login_required
def top_products():
    # 库存Top10商品(按数量排序)
    top_products_result = db.session.query(
        Product.name, Product.code, db.func.sum(Inventory.quantity).label('total_quantity')
    ).join(Inventory).group_by(Product.id).order_by(db.func.sum(Inventory.quantity).desc()).limit(10).all()
    # 查询会返回一个包含元组的列表，每个元组包含产品名称、产品代码和该产品的总库存量
    # (name, code, total_quantity)
    
    # 将查询结果转换为字典列表，以便在模板中使用
    top_products = []
    for product in top_products_result:
        top_products.append({
            'name': product[0],
            'code': product[1],
            'total_quantity': float(product[2])
        })

    return render_template('report/top_products.html',
                           top_products=top_products)

# 近30天出入库趋势
@report_bp.route('/trend')
@permission_required('report_view')
@login_required
def trend():
    # 近30天出入库趋势（按日期分组）
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

    # 格式化数据(适配Echart)
    dates = [d.strftime('%Y-%m-%d') for d in [start_date + timedelta(days=i) for i in range(31)]]
    # 从start_date开始遍历的后30天日期进行格式化
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

    return render_template('report/trend.html',
                           dates=dates,
                           inbound_data=inbound_data,
                           outbound_data=outbound_data)

# 库存健康度分析
@report_bp.route('/health')
@permission_required('report_view')
@login_required
def health():
    # 计算库存健康度相关数据
    # 1. 总库存
    total_inventory = db.session.query(db.func.sum(Inventory.quantity)).scalar() or 0
    total_inventory = float(total_inventory)
    
    # 2. 计算库存相关数据
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
    
    # 3. 总商品数
    total_product_count = Product.query.count()
    
    # 4. 健康度评分（基于库存数量和预警比例）
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
    
    # 5. 库存周转情况（简单计算）
    # 近30天入库总量
    end_date = datetime.now().date()
    start_date = (datetime.now() - timedelta(days=30)).date()
    
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
    
    return render_template('report/health.html',
                           total_inventory=total_inventory,
                           healthy_inventory=healthy_inventory,
                           warning_inventory=warning_inventory,
                           total_product_count=total_product_count,
                           health_score=health_score,
                           inbound_total=inbound_total,
                           outbound_total=outbound_total)