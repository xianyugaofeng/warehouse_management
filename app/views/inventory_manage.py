from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models.inventory import Inventory, WarehouseLocation, InventoryChangeLog
from app.models.product import Product, Category
from app.utils.auth import permission_required
from app import db
from datetime import datetime


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
    status = request.args.get('status', '')
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
    if status:
        # 过滤特定状态的库存
        query = query.filter(WarehouseLocation.location_type==status)

    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(Inventory.update_time.desc()).paginate(page=page, per_page=10)
    inventories = pagination.items

    # 下拉框数据
    categories = Category.query.all()
    locations = WarehouseLocation.query.filter_by(status=True).all()

    return render_template('inventory/list.html',
                           inventories=inventories,
                           categories=categories,
                           locations=locations,
                           pagination=pagination,
                           category_id=category_id,
                           location_id=location_id,
                           warning_only=warning_only,
                           status=status,
                           keyword=keyword
    )

# 库存详情
@inventory_bp.route('/detail/<int:inventory_id>')
@permission_required('inventory_manage')
@login_required
def detail(inventory_id):
    inventory = Inventory.query.get_or_404(inventory_id)
    # 获取库存变更日志
    logs = InventoryChangeLog.query.filter_by(inventory_id=inventory_id).order_by(InventoryChangeLog.create_time.desc()).limit(50).all()
    return render_template('inventory/detail.html', inventory=inventory, logs=logs)

# 库存调整（盘点）
@inventory_bp.route('/adjust/<int:inventory_id>', methods=['GET', 'POST'])
@permission_required('inventory_manage')
@login_required
def adjust(inventory_id):
    inventory = Inventory.query.get_or_404(inventory_id)
    if request.method == 'POST':
        new_quantity = int(request.form.get('quantity', 0))
        reason = request.form.get('reason', '盘点调整')
        try:
            inventory.adjust_quantity(new_quantity, reason)
            db.session.commit()
            flash('库存调整成功', 'success')
            return redirect(url_for('inventory.detail', inventory_id=inventory_id))
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(url_for('inventory.adjust', inventory_id=inventory_id))
    return render_template('inventory/adjust.html', inventory=inventory)

# 库存预警列表
@inventory_bp.route('/warning')
@permission_required('inventory_manage')
@login_required
def warning():
    # 获取所有预警库存
    query = Inventory.query.join(Product).filter(Inventory.quantity <= Product.warning_stock)
    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(Inventory.quantity.asc()).paginate(page=page, per_page=10)
    inventories = pagination.items
    return render_template('inventory/warning.html', inventories=inventories, pagination=pagination)

