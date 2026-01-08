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

# 库存统计报表
@report_bp.route('/index')
@permission_required('report_view')
@login_required
def index():
    # 1. 库存Top10商品(按数量排序)
    top_products = db.session.query(

    )