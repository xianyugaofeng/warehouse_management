from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app as app
from flask_login import current_user, login_required
from datetime import datetime
from app import db
from app.models.check import CheckInventory, CheckInventoryItem, CheckInventoryResult
from app.models.product import Product, Category
from app.models.inventory import WarehouseLocation, Inventory
from app.utils.auth import permission_required
from app.utils.helpers import generate_check_no

check_bp = Blueprint('check', __name__)

# 辅助函数类
class CheckInventoryHelper:
    """盘点管理辅助函数类"""
    
    @staticmethod
    def _get_inventories_for_check(filter_product_id, filter_category_id, filter_location_id):
        """
        根据筛选条件获取库存记录
        
        Args:
            filter_product_id: 产品ID筛选
            filter_category_id: 分类ID筛选
            filter_location_id: 库位ID筛选
            
        Returns:
            符合条件的库存记录列表
        """
        query = Inventory.query.filter(Inventory.quantity > 0)
        
        if filter_product_id:
            query = query.filter(Inventory.product_id == filter_product_id)
        if filter_category_id:
            query = query.join(Product).filter(Product.category_id == filter_category_id)
        if filter_location_id:
            query = query.filter(Inventory.location_id == filter_location_id)
        
        return query.all()
    
    @staticmethod
    def _add_inventory_items(check_order, inventories, check_no):
        """
        添加库存明细并冻结库存
        
        Args:
            check_order: 盘点单对象
            inventories: 库存记录列表
            check_no: 盘点单号
        """
        for inv in inventories:
            item = CheckInventoryItem(
                check_inventory_id=check_order.id,
                product_id=inv.product_id,
                location_id=inv.location_id,
                book_quantity=inv.quantity
            )
            db.session.add(item)
            
            inv.stock_status = 'frozen'
            inv.status_remark = f'盘点冻结 - {check_no}'
        
        check_order.frozen_status = True
    
    @staticmethod
    def _add_manual_items(check_order, product_ids, location_ids, book_quantities, check_no):
        """
        添加手动盘点明细并冻结库存
        
        Args:
            check_order: 盘点单对象
            product_ids: 产品ID列表
            location_ids: 库位ID列表
            book_quantities: 账面数量列表（不再使用，会自动统计）
            check_no: 盘点单号
        """
        for i in range(len(product_ids)):
            product_id = int(product_ids[i])
            location_id = int(location_ids[i])
            
            # 自动统计该库位上该商品的所有库存（包括不同批次）
            inventories = Inventory.query.filter_by(
                product_id=product_id,
                location_id=location_id
            ).filter(Inventory.quantity > 0).all()
            
            if not inventories:
                flash(f'库位 {location_id} 上没有商品 {product_id} 的库存', 'warning')
                continue
            
            # 为每个批次创建盘点明细
            for inv in inventories:
                item = CheckInventoryItem(
                    check_inventory_id=check_order.id,
                    product_id=product_id,
                    location_id=location_id,
                    book_quantity=inv.quantity
                )
                db.session.add(item)
                
                # 冻结库存
                inv.stock_status = 'frozen'
                inv.status_remark = f'盘点冻结 - {check_no}'
        
        check_order.frozen_status = True
    
    @staticmethod
    def _create_check_results(check_order):
        """
        创建盘点结果记录
        
        Args:
            check_order: 盘点单对象
        """
        items = CheckInventoryItem.query.filter_by(check_inventory_id=check_order.id).all()
        for item in items:
            result = CheckInventoryResult(
                check_inventory_id=check_order.id,
                check_item_id=item.id,
                check_time=datetime.utcnow(),
                book_quantity=item.book_quantity,
                actual_quantity=None,  # 使用None表示未盘点
                diff_quantity=0,  # 初始差异为0
                check_result='pending'
            )
            db.session.add(result)
    
    @staticmethod
    def _process_check_results(order, all_results):
        """
        处理盘点结果并更新库存
        
        Args:
            order: 盘点单对象
            all_results: 盘点结果列表
        """
        for result in all_results:
            if result.diff_quantity > 0:
                result.check_result = 'profit'
            elif result.diff_quantity < 0:
                result.check_result = 'loss'
            else:
                result.check_result = 'equal'
        
        for result in all_results:
            item = result.check_item
            inv = Inventory.query.filter_by(
                product_id=item.product_id,
                location_id=item.location_id
            ).first()
            
            if inv:
                inv.quantity = result.actual_quantity
                inv.stock_status = 'normal'
                inv.status_remark = None
        
        order.check_status = 'completed'
        order.frozen_status = False

# 创建辅助函数实例
helper = CheckInventoryHelper()


@check_bp.route('/list')
@permission_required('inventory_manage')
@login_required
def list():
    keyword = request.args.get('keyword', '')
    check_status = request.args.get('check_status', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    query = CheckInventory.query
    if keyword:
        query = query.filter(CheckInventory.check_no.ilike(f'%{keyword}%'))
    if check_status:
        query = query.filter_by(check_status=check_status)
    if start_date:
        query = query.filter(CheckInventory.create_time >= start_date)
    if end_date:
        query = query.filter(CheckInventory.create_time <= end_date)

    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(CheckInventory.create_time.desc()).paginate(page=page, per_page=per_page)
    orders = pagination.items

    return render_template('check/list.html',
                           orders=orders,
                           pagination=pagination,
                           keyword=keyword,
                           check_status=check_status,
                           start_date=start_date,
                           end_date=end_date
    )


@check_bp.route('/add', methods=['GET', 'POST'])
@permission_required('inventory_manage')
@login_required
def add():
    products = Product.query.all()
    categories = Category.query.all()
    locations = WarehouseLocation.query.filter_by(status=True).all()

    if request.method == 'POST':
        filter_type = request.form.get('filter_type', 'manual')
        filter_product_id = request.form.get('filter_product_id') or None
        filter_category_id = request.form.get('filter_category_id') or None
        filter_location_id = request.form.get('filter_location_id') or None
        remark = request.form.get('remark')

        check_no = generate_check_no()
        check_order = CheckInventory(
            check_no=check_no,
            check_status='pending',
            checker_id=current_user.id,
            filter_product_id=filter_product_id,
            filter_category_id=filter_category_id,
            filter_location_id=filter_location_id,
            remark=remark,
            frozen_status=False
        )
        db.session.add(check_order)
        db.session.flush()

        try:
            # 处理自动添加盘点明细
            if filter_type == 'auto':
                inventories = helper._get_inventories_for_check(filter_product_id, filter_category_id, filter_location_id)
                
                if not inventories:
                    flash('没有找到符合条件的库存记录', 'warning')
                    return render_template('check/add.html',
                                           products=products,
                                           categories=categories,
                                           locations=locations,
                                           now=datetime.now()
                    )
                
                # 添加盘点明细并冻结库存
                helper._add_inventory_items(check_order, inventories, check_no)
                
            else:
                # 处理手动添加盘点明细
                product_ids = request.form.getlist('product_id[]')
                location_ids = request.form.getlist('location_id[]')
                book_quantities = request.form.getlist('book_quantity[]')
                
                if not product_ids:
                    flash('请添加至少一条盘点明细', 'danger')
                    return render_template('check/add.html',
                                           products=products,
                                           categories=categories,
                                           locations=locations,
                                           now=datetime.now()
                    )
                
                # 验证并添加手动盘点明细
                helper._add_manual_items(check_order, product_ids, location_ids, book_quantities, check_no)

            # 创建盘点结果记录
            helper._create_check_results(check_order)

            db.session.commit()
            flash('盘点单创建成功，状态为待录入', 'success')
            return redirect(url_for('check.detail', id=check_order.id))

        except Exception as e:
            db.session.rollback()
            # 避免显示敏感错误信息
            flash('创建失败，请检查输入信息并重试', 'danger')
            # 可以将详细错误信息记录到日志
            app.logger.error(f'创建盘点单失败: {str(e)}')

    return render_template('check/add.html',
                           products=products,
                           categories=categories,
                           locations=locations,
                           now=datetime.now()
    )


@check_bp.route('/detail/<int:id>')
@permission_required('inventory_manage')
@login_required
def detail(id):
    order = CheckInventory.query.get_or_404(id)
    return render_template('check/detail.html', order=order)


@check_bp.route('/input/<int:id>', methods=['GET', 'POST'])
@permission_required('inventory_manage')
@login_required
def input_page(id):
    order = CheckInventory.query.get_or_404(id)
    
    if order.check_status != 'pending':
        flash('只有待录入状态的盘点单才能录入结果', 'warning')
        return redirect(url_for('check.detail', id=id))
    
    if request.method == 'POST':
        try:
            actual_quantities = request.form.getlist('actual_quantity[]')
            result_ids = request.form.getlist('result_id[]')
            
            # 验证输入数据长度
            if len(actual_quantities) != len(result_ids):
                flash('数据错误，请重试', 'danger')
                return redirect(url_for('check.input_page', id=id))
            
            # 录入实际盘点数量
            for i in range(len(result_ids)):
                result_id = int(result_ids[i])
                # 验证实际数量格式
                if not actual_quantities[i].isdigit():
                    flash('实际数量必须为数字', 'danger')
                    return redirect(url_for('check.input_page', id=id))
                
                actual_quantity = int(actual_quantities[i])
                
                if actual_quantity < 0:
                    flash('实际数量不能为负数', 'danger')
                    return redirect(url_for('check.input_page', id=id))
                
                result = CheckInventoryResult.query.get(result_id)
                if result and result.check_inventory_id == order.id:
                    result.actual_quantity = actual_quantity
                    result.diff_quantity = actual_quantity - result.book_quantity
                    result.check_time = datetime.utcnow()
            
            # 检查是否所有结果都已录入
            all_results = order.results.all()
            all_input = all(r.actual_quantity is not None and r.actual_quantity >= 0 for r in all_results)
            
            if all_input:
                # 处理盘点结果
                helper._process_check_results(order, all_results)
                
                db.session.commit()
                flash('盘点结果录入完成，库存已更新', 'success')
                return redirect(url_for('check.list'))
            else:
                db.session.commit()
                flash('盘点结果已保存', 'success')
                return redirect(url_for('check.input_page', id=id))
                
        except Exception as e:
            db.session.rollback()
            # 避免显示敏感错误信息
            flash('录入失败，请检查输入信息并重试', 'danger')
            # 可以将详细错误信息记录到日志
            app.logger.error(f'录入盘点结果失败: {str(e)}')
            return redirect(url_for('check.input_page', id=id))
    
    results = order.results.all()
    return render_template('check/input.html', order=order, results=results)


@check_bp.route('/cancel/<int:id>', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def cancel(id):
    order = CheckInventory.query.get_or_404(id)
    
    if order.check_status != 'pending':
        flash('只有待录入状态的盘点单才能取消', 'warning')
        return redirect(url_for('check.detail', id=id))
    
    try:
            # 解冻相关库存
            for item in order.items:
                inv = Inventory.query.filter_by(
                    product_id=item.product_id,
                    location_id=item.location_id
                ).first()
                if inv and inv.stock_status == 'frozen':
                    inv.stock_status = 'normal'
                    inv.status_remark = None
            
            # 更新盘点单状态
            order.check_status = 'canceled'
            order.frozen_status = False
            db.session.commit()
            
            flash('盘点单已取消，库存已解冻', 'success')
            return redirect(url_for('check.list'))
            
    except Exception as e:
        db.session.rollback()
        # 避免显示敏感错误信息
        flash('取消失败，请重试', 'danger')
        # 可以将详细错误信息记录到日志
        app.logger.error(f'取消盘点单失败: {str(e)}')
        return redirect(url_for('check.detail', id=id))


@check_bp.route('/get_inventory')
@permission_required('inventory_manage')
@login_required
def get_inventory():
    product_id = request.args.get('product_id', type=int)
    location_id = request.args.get('location_id', type=int)
    
    query = Inventory.query.filter(Inventory.quantity > 0)
    
    if product_id:
        query = query.filter(Inventory.product_id == product_id)
    if location_id:
        query = query.filter(Inventory.location_id == location_id)
    
    inventories = query.all()
    result = []
    
    for inv in inventories:
        result.append({
            'product_id': inv.product_id,
            'product_name': inv.product.name if inv.product else '',
            'location_id': inv.location_id,
            'location_code': inv.location.code if inv.location else '',
            'quantity': inv.quantity
        })
    
    return jsonify({'success': True, 'data': result})


@check_bp.route('/history')
@permission_required('inventory_manage')
@login_required
def history():
    keyword = request.args.get('keyword', '')
    filter_location_id = request.args.get('filter_location_id', '')
    filter_category_id = request.args.get('filter_category_id', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    query = CheckInventory.query.filter_by(check_status='completed')
    
    if keyword:
        query = query.filter(CheckInventory.check_no.ilike(f'%{keyword}%'))
    if filter_location_id:
        query = query.filter_by(filter_location_id=filter_location_id)
    if filter_category_id:
        query = query.filter_by(filter_category_id=filter_category_id)
    if start_date:
        query = query.filter(CheckInventory.create_time >= start_date)
    if end_date:
        query = query.filter(CheckInventory.create_time <= end_date)

    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(CheckInventory.create_time.desc()).paginate(page=page, per_page=per_page)
    orders = pagination.items

    locations = WarehouseLocation.query.filter_by(status=True).all()
    categories = Category.query.all()

    return render_template('check/history.html',
                           orders=orders,
                           pagination=pagination,
                           keyword=keyword,
                           filter_location_id=filter_location_id,
                           filter_category_id=filter_category_id,
                           start_date=start_date,
                           end_date=end_date,
                           locations=locations,
                           categories=categories
    )


@check_bp.route('/history/<int:id>')
@permission_required('inventory_manage')
@login_required
def history_detail(id):
    order = CheckInventory.query.get_or_404(id)
    
    if order.check_status != 'completed':
        flash('只能查看已完成状态的盘点单', 'warning')
        return redirect(url_for('check.history'))
    
    results = order.results.all()
    return render_template('check/history_detail.html', order=order, results=results)


@check_bp.route('/input')
@permission_required('inventory_manage')
@login_required
def input_select():
    """
    盘点结果录入选择页面
    显示所有待录入状态的盘点单，供用户选择
    """
    # 查询所有待录入状态的盘点单
    pending_orders = CheckInventory.query.filter_by(check_status='pending').order_by(CheckInventory.create_time.desc()).all()
    
    return render_template('check/input_select.html', orders=pending_orders)