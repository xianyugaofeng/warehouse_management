from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user, login_required
from datetime import datetime
from app import db
from app.models.check import CheckInventory, CheckInventoryItem, CheckInventoryResult
from app.models.product import Product, Category
from app.models.inventory import WarehouseLocation, Inventory
from app.utils.auth import permission_required
from app.utils.helpers import generate_check_no

check_bp = Blueprint('check', __name__)


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
            if filter_type == 'auto':
                query = Inventory.query.filter(Inventory.quantity > 0)
                
                if filter_product_id:
                    query = query.filter(Inventory.product_id == filter_product_id)
                if filter_category_id:
                    query = query.join(Product).filter(Product.category_id == filter_category_id)
                if filter_location_id:
                    query = query.filter(Inventory.location_id == filter_location_id)
                
                inventories = query.all()
                
                if not inventories:
                    flash('没有找到符合条件的库存记录', 'warning')
                    return render_template('check_inventory/add.html',
                                           products=products,
                                           categories=categories,
                                           locations=locations,
                                           now=datetime.now()
                    )
                
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
                
            else:
                product_ids = request.form.getlist('product_id[]')
                location_ids = request.form.getlist('location_id[]')
                book_quantities = request.form.getlist('book_quantity[]')
                
                if not product_ids:
                    flash('请添加至少一条盘点明细', 'danger')
                    return render_template('check_inventory/add.html',
                                           products=products,
                                           categories=categories,
                                           locations=locations,
                                           now=datetime.now()
                    )
                
                for i in range(len(product_ids)):
                    product_id = int(product_ids[i])
                    location_id = int(location_ids[i])
                    book_quantity = int(book_quantities[i]) if book_quantities[i].isdigit() else 0
                    
                    if book_quantity < 0:
                        flash('账面数量不能为负数', 'danger')
                        return render_template('check_inventory/add.html',
                                               products=products,
                                               categories=categories,
                                               locations=locations,
                                               now=datetime.now()
                        )
                    
                    item = CheckInventoryItem(
                        check_inventory_id=check_order.id,
                        product_id=product_id,
                        location_id=location_id,
                        book_quantity=book_quantity
                    )
                    db.session.add(item)
                    
                    inv = Inventory.query.filter_by(
                        product_id=product_id,
                        location_id=location_id
                    ).first()
                    if inv:
                        inv.stock_status = 'frozen'
                        inv.status_remark = f'盘点冻结 - {check_no}'
                
                check_order.frozen_status = True

            db.session.flush()
            
            items = CheckInventoryItem.query.filter_by(check_inventory_id=check_order.id).all()
            for item in items:
                result = CheckInventoryResult(
                    check_inventory_id=check_order.id,
                    check_item_id=item.id,
                    check_time=datetime.utcnow(),
                    book_quantity=item.book_quantity,
                    actual_quantity=0,
                    diff_quantity=-item.book_quantity,
                    check_result='pending'
                )
                db.session.add(result)

            db.session.commit()
            flash('盘点单创建成功，状态为待录入', 'success')
            return redirect(url_for('check.detail', id=check_order.id))

        except Exception as e:
            db.session.rollback()
            flash(f'创建失败: {str(e)}', 'danger')

    return render_template('check_inventory/add.html',
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
            
            if len(actual_quantities) != len(result_ids):
                flash('数据错误，请重试', 'danger')
                return redirect(url_for('check.input_page', id=id))
            
            for i in range(len(result_ids)):
                result_id = int(result_ids[i])
                actual_quantity = int(actual_quantities[i]) if actual_quantities[i].isdigit() else 0
                
                if actual_quantity < 0:
                    flash('实际数量不能为负数', 'danger')
                    return redirect(url_for('check.input_page', id=id))
                
                result = CheckInventoryResult.query.get(result_id)
                if result and result.check_inventory_id == order.id:
                    result.actual_quantity = actual_quantity
                    result.diff_quantity = actual_quantity - result.book_quantity
                    result.check_time = datetime.utcnow()
            
            all_results = order.results.all()
            all_input = all(r.actual_quantity is not None and r.actual_quantity >= 0 for r in all_results)
            
            if all_input:
                for result in all_results:
                    if result.diff_quantity > 0:
                        result.check_result = 'profit'
                    elif result.diff_quantity < 0:
                        result.check_result = 'loss'
                    else:
                        result.check_result = 'equal'
                
                for result in all_results:
                    item = result.item
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
                
                db.session.commit()
                flash('盘点结果录入完成，库存已更新', 'success')
                return redirect(url_for('check.list'))
            else:
                db.session.commit()
                flash('盘点结果已保存', 'success')
                return redirect(url_for('check.input_page', id=id))
                
        except Exception as e:
            db.session.rollback()
            flash(f'录入失败: {str(e)}', 'danger')
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
        for item in order.items:
            inv = Inventory.query.filter_by(
                product_id=item.product_id,
                location_id=item.location_id
            ).first()
            if inv and inv.stock_status == 'frozen':
                inv.stock_status = 'normal'
                inv.status_remark = None
        
        order.check_status = 'canceled'
        order.frozen_status = False
        db.session.commit()
        
        flash('盘点单已取消，库存已解冻', 'success')
        return redirect(url_for('check.list'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'取消失败: {str(e)}', 'danger')
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