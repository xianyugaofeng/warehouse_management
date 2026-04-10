from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models.inventory import Inventory, WarehouseLocation
from app.models.product import Product, Category, ProductParamValue
from app.utils.auth import permission_required


inventory_bp = Blueprint('inventory', __name__)

# 库存列表（专门查看库存模型）
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
    locations = WarehouseLocation.query.filter_by(status=True).all()

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

# 库存明细（专门用于查询商品参数）
@inventory_bp.route('/detail')
@permission_required('inventory_manage')
@login_required
def detail():
    keyword = request.args.get('keyword', '')
    category_id = request.args.get('category_id', '')
    location_id = request.args.get('location_id', '')
    warning_only = request.args.get('warning_only', '') == '1'

    query = Inventory.query.join(Product).join(WarehouseLocation)
    if keyword:
        query = query.filter(Product.name.ilike(f'%{keyword}%') |
                             Product.code.ilike(f'%{keyword}%')
        )
    # 确保只按分类查询
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
    locations = WarehouseLocation.query.filter_by(status=True).all()

    # 加载商品参数信息
    product_params = {}
    for inventory in inventories:
        product_id = inventory.product.id
        if product_id not in product_params:
            params = ProductParamValue.query.filter_by(product_id=product_id).all()
            product_params[product_id] = {param.param_key.name: param.value for param in params}

    return render_template('inventory/detail.html',
                           inventories=inventories,
                           categories=categories,
                           locations=locations,
                           pagination=pagination,
                           category_id=category_id,
                           location_id=location_id,
                           warning_only=warning_only,
                           keyword=keyword,
                           product_params=product_params
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
            return redirect(url_for('inventory.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败：{str(e)}', 'danger')
    
    return render_template('inventory/update_status.html', inventory=inventory)

