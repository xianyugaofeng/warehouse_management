from flask import Blueprint, render_template, request
from flask_login import login_required
from app.models.inventory import Inventory, WarehouseLocation
from app.models.product import Product, Category
from app.utils.auth import permission_required


inventory_bp = Blueprint('inventory', __name__)

# 库存列表
@inventory_bp.route('/list')
@permission_required('inventory_manage')
@login_required
def list():
    keyword = request.args.get('keyword', '')
    category_id = request.args.get('category_id', '')
    location_id = request.args.get('location_id', '')
    warning_only = request.args.get('warning_only', '') == '1'
    # 判断预警库存是否为1，将bool值结果赋值给变量warning_only

    query = Inventory.query.join(Product).join(WarehouseLocation)
    # 默认情况下会尝试根据外键关系自动确定连接条件
    if keyword:
        query = query.filter(Product.name.ilike(f'%{keyword}%') |
                             Product.code.ilike(f'%{keyword}%')
        )
    if category_id:
        query = query.filter(Product.category_id==category_id)
    if location_id:
        query = query.filter(Inventory.location_id==location_id)
    if warning_only:
        query = query.filter(Inventory.quantity <= Product.warning_stock)

    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(Inventory.update_time.desc()).paginate(page=page, per_page=10)
    inventories = pagination.items

    # 下拉框数据
    categories = Category.query.all()
    locations = WarehouseLocation.query.filter(status=True).all()

    return render_template('inventory/list.html',
                           inventories=inventories,
                           categories=categories,
                           locations=locations,
                           pagination=pagination,
                           category_id=category_id,
                           location_id=location_id,
                           warning_only=warning_only,
                           keyword=keyword
    )

