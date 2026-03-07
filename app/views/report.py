from flask import Blueprint, render_template, request
from flask_login import login_required
from datetime import datetime, timedelta
from app import db
from app.models.inbound import InboundOrder, InboundItem
from app.models.outbound import OutboundOrder, OutboundItem
from app.models.inventory import Inventory
from app.models.product import Product
from app.utils.auth import permission_required
from sqlalchemy.orm import joinedload


report_bp = Blueprint('report', __name__)

# 库存统计报表
@report_bp.route('/index')
@permission_required('report_view')
@login_required
def index():
    # 1. 库存Top10商品(按数量排序)
    top_products = db.session.query(
        Product.name, Product.code, db.func.sum(Inventory.quantity).label('total_quantity')
    ).join(Inventory).group_by(Product.id).order_by(db.func.sum(Inventory.quantity).desc()).limit(10).all()
    # 查询会返回一个包含元组的列表，每个元组包含产品名称、产品代码和该产品的总库存量
    # (name, code, total_quantity)

    # 2. 近30天出入库趋势（按日期分组）
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
            inbound_data[idx] = item.total

    for item in outbound_trend:
        idx = (item.date - start_date).days
        if 0 <= idx < 31:
            outbound_data[idx] = item.total

    inventories = Inventory.query.options(joinedload(Inventory.product)).join(Product).filter(Inventory.quantity > 0).all()
    # 关键修改 - 使用 SQLAlchemy 的 joinedload 预加载 Inventory 模型的 product 关联
    # 这会通过 LEFT JOIN 在一次查询中同时加载库存记录和关联的商品信息
    
    return render_template('report/index.html',
                           top_products=top_products,
                           dates=dates,
                           inbound_data=inbound_data,
                           outbound_data=outbound_data,
                           inventories=inventories,
                           start_date=start_date,
                           end_date=end_date
    )