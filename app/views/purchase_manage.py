from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from datetime import datetime
from app import db
from app.models.purchase import PurchaseOrder, PurchaseItem
from app.models.product import Product, Supplier
from app.models.inventory import WarehouseLocation
from app.models.inspection import InspectionOrder, InspectionItem
from app.utils.auth import permission_required
from app.utils.helpers import generate_purchase_no, generate_inspection_no

purchase_bp = Blueprint('purchase', __name__)

# 采购单列表
@purchase_bp.route('/list')
@permission_required('inbound_manage')
@login_required
def list():
    keyword = request.args.get('keyword', '')
    supplier_id = request.args.get('supplier_id', '')
    status = request.args.get('status', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    query = PurchaseOrder.query
    if keyword:
        query = query.filter(PurchaseOrder.order_no.ilike(f'%{keyword}%'))
    if supplier_id:
        try:
            supplier_id_int = int(supplier_id)
            query = query.filter_by(supplier_id=supplier_id_int)
        except ValueError:
            pass
    if status:
        query = query.filter_by(status=status)
    if start_date:
        query = query.filter(PurchaseOrder.create_time >= start_date)
    if end_date:
        query = query.filter(PurchaseOrder.create_time <= end_date)

    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(PurchaseOrder.create_time.desc()).paginate(page=page, per_page=per_page)
    orders = pagination.items

    suppliers = Supplier.query.all()
    return render_template('purchase/list.html',
                           orders=orders,
                           pagination=pagination,
                           keyword=keyword,
                           supplier_id=supplier_id,
                           status=status,
                           start_date=start_date,
                           end_date=end_date,
                           suppliers=suppliers
    )

# 添加采购单
@purchase_bp.route('/add', methods=['GET', 'POST'])
@permission_required('inbound_manage')
@login_required
def add():
    products = Product.query.all()
    suppliers = Supplier.query.all()

    if request.method == 'POST':
        # 接收表单数据
        supplier_id = request.form.get('supplier_id')
        expected_date = request.form.get('expected_date', datetime.now().strftime('%Y-%m-%d'))
        remark = request.form.get('remark')

        # 接收明细数据
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')
        subtotals = request.form.getlist('subtotal[]')

        # 验证数据
        if not product_ids or len(product_ids) != len(quantities):
            flash('请添加至少一条采购明细', 'danger')
            return render_template('purchase/add.html',
                                   products=products,
                                   suppliers=suppliers,
                                   now=datetime.now()
            )

        # 创建采购单
        order_no = generate_purchase_no()
        total_amount = sum(int(qty) for qty in quantities if qty.isdigit())
        purchase_order = PurchaseOrder(
            order_no=order_no,
            supplier_id=supplier_id,
            operator_id=current_user.id,
            expected_date=expected_date,
            total_amount=total_amount,
            status='pending_receipt',  # 初始状态为待收货
            remark=remark
        )
        db.session.add(purchase_order)
        db.session.flush()  # 刷新获取order_id,用于明细关联

        # 处理采购明细
        try:
            for i in range(len(product_ids)):
                product_id = product_ids[i]
                quantity = int(quantities[i]) if quantities[i].isdigit() else 0
                unit_price = float(unit_prices[i]) if unit_prices[i] else 0.0
                subtotal = float(subtotals[i]) if subtotals[i] else 0.0

                if quantity <= 0:
                    flash('数量必须大于0', 'danger')
                    return render_template('purchase/add.html',
                                   products=products,
                                   suppliers=suppliers,
                                   now=datetime.now()
                    )

                # 创建采购明细
                item = PurchaseItem(
                    order_id=purchase_order.id,
                    product_id=product_id,
                    quantity=quantity,
                    unit_price=unit_price,
                    subtotal=subtotal
                )
                db.session.add(item)

            db.session.commit()
            flash('采购单创建成功', 'success')
            return redirect(url_for('purchase.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'创建失败:{str(e)}', 'danger')

    return render_template('purchase/add.html',
                           products=products,
                           suppliers=suppliers,
                           now=datetime.now()
    )

# 编辑采购单
@purchase_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@permission_required('inbound_manage')
@login_required
def edit(id):
    purchase_order = PurchaseOrder.query.get_or_404(id)
    if purchase_order.status != 'pending_receipt':
        flash('只能编辑待收货状态的采购单', 'danger')
        return redirect(url_for('purchase.list'))

    products = Product.query.all()
    suppliers = Supplier.query.all()

    if request.method == 'POST':
        # 接收表单数据
        supplier_id = request.form.get('supplier_id')
        expected_date = request.form.get('expected_date')
        remark = request.form.get('remark')

        # 更新采购单
        purchase_order.supplier_id = supplier_id
        purchase_order.expected_date = expected_date
        purchase_order.remark = remark

        # 删除原有明细
        PurchaseItem.query.filter_by(order_id=id).delete()

        # 接收新的明细数据
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')
        subtotals = request.form.getlist('subtotal[]')

        # 验证数据
        if not product_ids or len(product_ids) != len(quantities):
            flash('请添加至少一条采购明细', 'danger')
            return render_template('purchase/edit.html',
                                   purchase_order=purchase_order,
                                   products=products,
                                   suppliers=suppliers
            )

        # 处理采购明细
        total_amount = 0
        try:
            for i in range(len(product_ids)):
                product_id = product_ids[i]
                quantity = int(quantities[i]) if quantities[i].isdigit() else 0
                unit_price = float(unit_prices[i]) if unit_prices[i] else 0.0
                subtotal = float(subtotals[i]) if subtotals[i] else 0.0

                if quantity <= 0:
                    flash('数量必须大于0', 'danger')
                    return render_template('purchase/edit.html',
                                   purchase_order=purchase_order,
                                   products=products,
                                   suppliers=suppliers
                    )

                total_amount += quantity

                # 创建采购明细
                item = PurchaseItem(
                    order_id=purchase_order.id,
                    product_id=product_id,
                    quantity=quantity,
                    unit_price=unit_price,
                    subtotal=subtotal
                )
                db.session.add(item)

            purchase_order.total_amount = total_amount
            db.session.commit()
            flash('采购单更新成功', 'success')
            return redirect(url_for('purchase.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败:{str(e)}', 'danger')

    return render_template('purchase/edit.html',
                           purchase_order=purchase_order,
                           products=products,
                           suppliers=suppliers
    )

# 采购单详情
@purchase_bp.route('/detail/<int:id>')
@permission_required('inbound_manage')
@login_required
def detail(id):
    purchase_order = PurchaseOrder.query.get_or_404(id)
    return render_template('purchase/detail.html', purchase_order=purchase_order)

# 查看采购单收货状态
@purchase_bp.route('/receive/<int:id>')
@permission_required('inbound_manage')
@login_required
def receive(id):
    purchase_order = PurchaseOrder.query.get_or_404(id)
    if purchase_order.status == 'completed':
        flash('该采购单已完成', 'info')
        return redirect(url_for('purchase.detail', id=id))
    return redirect(url_for('inspection.receive', id=id))