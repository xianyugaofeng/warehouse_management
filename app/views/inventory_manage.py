from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models.inventory import Inventory, WarehouseLocation
from app.models.product import Product, Category, ProductParamValue
from app.utils.auth import permission_required


inventory_bp = Blueprint('inventory', __name__)

# 库存预警（专门查看预警库存）
@inventory_bp.route('/warning')
@permission_required('inventory_manage')
@login_required
def warning():
    keyword = request.args.get('keyword', '')
    category_id = request.args.get('category_id', '')
    location_id = request.args.get('location_id', '')

    query = Inventory.query.join(Product).join(WarehouseLocation)
    if keyword:
        query = query.filter(Product.name.ilike(f'%{keyword}%') |
                             Product.code.ilike(f'%{keyword}%')
        )
    if category_id:
        query = query.filter(Product.category_id==category_id)
    if location_id:
        query = query.filter(Inventory.location_id==location_id)
    # 只显示预警库存
    query = query.filter(Inventory.quantity <= Product.warning_stock)

    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(Inventory.update_time.desc()).paginate(page=page, per_page=10)
    inventories = pagination.items

    categories = Category.query.all()
    locations = WarehouseLocation.query.filter_by(status=True).all()

    return render_template('inventory/warning.html',
                           inventories=inventories,
                           categories=categories,
                           locations=locations,
                           pagination=pagination,
                           category_id=category_id,
                           location_id=location_id,
                           keyword=keyword
    )

# 库存查询（按商品分组统计总库存）
@inventory_bp.route('/detail')
@permission_required('inventory_manage')
@login_required
def detail():
    keyword = request.args.get('keyword', '')
    category_id = request.args.get('category_id', '')
    location_id = request.args.get('location_id', '')

    # 基础查询：按商品分组统计库存
    from sqlalchemy import func
    query = db.session.query(
        Product.id,
        Product.code,
        Product.name,
        Product.warning_stock,
        func.sum(Inventory.quantity).label('total_quantity')
    ).join(Inventory, Product.id == Inventory.product_id).join(WarehouseLocation, Inventory.location_id == WarehouseLocation.id)

    # 筛选条件
    if keyword:
        query = query.filter(Product.name.ilike(f'%{keyword}%') | Product.code.ilike(f'%{keyword}%'))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if location_id:
        query = query.filter(Inventory.location_id == location_id)

    # 分组并按总库存排序
    query = query.group_by(Product.id).order_by(func.sum(Inventory.quantity).desc())

    # 分页
    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.paginate(page=page, per_page=per_page)
    products = pagination.items

    # 下拉框数据
    categories = Category.query.all()
    locations = WarehouseLocation.query.filter_by(status=True).all()

    # 加载商品参数信息
    product_params = {}
    for product in products:
        params = ProductParamValue.query.filter_by(product_id=product.id).all()
        product_params[product.id] = {param.param_key.name: param.value for param in params}

    return render_template('inventory/detail.html',
                           products=products,
                           categories=categories,
                           locations=locations,
                           pagination=pagination,
                           category_id=category_id,
                           location_id=location_id,
                           keyword=keyword,
                           product_params=product_params
    )

# 库存状态管理（查看所有库存并修改状态）
@inventory_bp.route('/status')
@permission_required('inventory_manage')
@login_required
def status():
    keyword = request.args.get('keyword', '')
    category_id = request.args.get('category_id', '')
    location_id = request.args.get('location_id', '')
    stock_status = request.args.get('stock_status', '')

    query = Inventory.query.join(Product).join(WarehouseLocation)
    if keyword:
        query = query.filter(Product.name.ilike(f'%{keyword}%') | Product.code.ilike(f'%{keyword}%'))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if location_id:
        query = query.filter(Inventory.location_id == location_id)
    if stock_status:
        query = query.filter(Inventory.stock_status == stock_status)

    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(Inventory.update_time.desc()).paginate(page=page, per_page=10)
    inventories = pagination.items

    categories = Category.query.all()
    locations = WarehouseLocation.query.filter_by(status=True).all()

    return render_template('inventory/status.html',
                           inventories=inventories,
                           categories=categories,
                           locations=locations,
                           pagination=pagination,
                           category_id=category_id,
                           location_id=location_id,
                           stock_status=stock_status,
                           keyword=keyword
    )

# 修改库存状态
@inventory_bp.route('/update_status/<int:id>', methods=['GET', 'POST'])
@permission_required('inventory_manage')
@login_required
def update_status(id):
    inventory = Inventory.query.get_or_404(id)
    
    if request.method == 'POST':
        # 接收表单数据
        stock_status = request.form.get('stock_status')
        status_remark = request.form.get('status_remark', '')
        
        # 验证状态值
        if stock_status not in ['normal', 'damaged', 'frozen']:
            flash('无效的库存状态', 'danger')
            return redirect(url_for('inventory.update_status', id=id))
        
        # 更新库存状态
        try:
            inventory.stock_status = stock_status
            inventory.status_remark = status_remark
            db.session.commit()
            
            status_names = {'normal': '正常', 'damaged': '损坏', 'frozen': '冻结'}
            flash(f'库存状态已更新为：{status_names[stock_status]}', 'success')
            return redirect(url_for('inventory.status'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败：{str(e)}', 'danger')
    
    return render_template('inventory/update_status.html', inventory=inventory)

