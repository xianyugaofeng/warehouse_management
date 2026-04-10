from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from datetime import datetime
from app import db
from app.models.transfer import TransferOrder, TransferItem
from app.models.product import Product
from app.models.inventory import WarehouseLocation, Inventory
from app.utils.auth import permission_required
from app.utils.helpers import generate_transfer_no, execute_transfer

transfer_bp = Blueprint('transfer', __name__)

# 调拨单列表
@transfer_bp.route('/list')
@permission_required('inventory_manage')
@login_required
def list():
    keyword = request.args.get('keyword', '')
    audit_status = request.args.get('audit_status', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    query = TransferOrder.query
    if keyword:
        query = query.filter(TransferOrder.order_no.ilike(f'%{keyword}%'))
    if audit_status:
        query = query.filter_by(audit_status=audit_status)
    if start_date:
        query = query.filter(TransferOrder.create_time >= start_date)
    if end_date:
        query = query.filter(TransferOrder.create_time <= end_date)

    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(TransferOrder.create_time.desc()).paginate(page=page, per_page=per_page)
    orders = pagination.items

    return render_template('transfer/list.html',
                           orders=orders,
                           pagination=pagination,
                           keyword=keyword,
                           audit_status=audit_status,
                           start_date=start_date,
                           end_date=end_date
    )

# 调拨单审核列表
@transfer_bp.route('/audit_list')
@permission_required('inventory_manage')
@login_required
def audit_list():
    keyword = request.args.get('keyword', '')
    audit_status = request.args.get('audit_status', 'pending')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    query = TransferOrder.query
    if keyword:
        query = query.filter(TransferOrder.order_no.ilike(f'%{keyword}%'))
    if audit_status:
        query = query.filter_by(audit_status=audit_status)
    if start_date:
        query = query.filter(TransferOrder.create_time >= start_date)
    if end_date:
        query = query.filter(TransferOrder.create_time <= end_date)

    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(TransferOrder.create_time.desc()).paginate(page=page, per_page=per_page)
    orders = pagination.items

    # 统计待审核和已通过的数量
    pending_count = TransferOrder.query.filter_by(audit_status='pending').count()
    approved_count = TransferOrder.query.filter_by(audit_status='approved').count()

    return render_template('transfer/audit_list.html',
                           orders=orders,
                           pagination=pagination,
                           keyword=keyword,
                           audit_status=audit_status,
                           start_date=start_date,
                           end_date=end_date,
                           pending_count=pending_count,
                           approved_count=approved_count
    )

# 添加调拨单
@transfer_bp.route('/add', methods=['GET', 'POST'])
@permission_required('inventory_manage')
@login_required
def add():
    products = Product.query.all()
    locations = WarehouseLocation.query.filter_by(status=True).all()

    if request.method == 'POST':
        remark = request.form.get('remark')

        product_ids = request.form.getlist('product_id[]')
        source_location_ids = request.form.getlist('source_location_id[]')
        target_location_ids = request.form.getlist('target_location_id[]')
        quantities = request.form.getlist('quantity[]')

        if not product_ids or len(product_ids) != len(quantities):
            flash('请添加至少一条调拨明细', 'danger')
            return render_template('transfer/add.html',
                                   products=products,
                                   locations=locations,
                                   now=datetime.now()
            )

        order_no = generate_transfer_no()
        transfer_order = TransferOrder(
            order_no=order_no,
            creator_id=current_user.id,
            audit_status='pending',
            remark=remark
        )
        db.session.add(transfer_order)
        db.session.flush()

        try:
            for i in range(len(product_ids)):
                product_id = product_ids[i]
                source_location_id = source_location_ids[i]
                target_location_id = target_location_ids[i]
                quantity = int(quantities[i]) if quantities[i].isdigit() else 0

                if quantity <= 0:
                    flash('数量必须大于0', 'danger')
                    return render_template('transfer/add.html',
                                           products=products,
                                           locations=locations,
                                           now=datetime.now()
                    )

                if source_location_id == target_location_id:
                    flash('原库位和目标库位不能相同', 'danger')
                    return render_template('transfer/add.html',
                                           products=products,
                                           locations=locations,
                                           now=datetime.now()
                    )

                item = TransferItem(
                    order_id=transfer_order.id,
                    product_id=product_id,
                    source_location_id=source_location_id,
                    target_location_id=target_location_id,
                    quantity=quantity
                )
                db.session.add(item)

            db.session.commit()
            flash('调拨单创建成功，状态为未审核', 'success')
            return redirect(url_for('transfer.detail', id=transfer_order.id))
        except Exception as e:
            db.session.rollback()
            flash(f'创建失败:{str(e)}', 'danger')

    return render_template('transfer/add.html',
                           products=products,
                           locations=locations,
                           now=datetime.now()
    )

@transfer_bp.route('/detail/<int:id>')
@permission_required('inventory_manage')
@login_required
def detail(id):
    order = TransferOrder.query.get_or_404(id)
    return render_template('transfer/detail.html', order=order)

@transfer_bp.route('/audit/<int:id>', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def audit(id):
    order = TransferOrder.query.get_or_404(id)

    if order.audit_status != 'pending':
        flash('只有未审核的调拨单才能审核', 'warning')
        return redirect(url_for('transfer.detail', id=id))

    if not order.items.first():
        flash('调拨单没有明细，无法审核', 'warning')
        return redirect(url_for('transfer.detail', id=id))

    audit_result = request.form.get('audit_result')

    try:
        if audit_result == 'approved':
            for item in order.items:
                execute_transfer(
                    product_id=item.product_id,
                    source_location_id=item.source_location_id,
                    target_location_id=item.target_location_id,
                    quantity=item.quantity
                )

            order.audit_status = 'approved'
            order.auditor_id = current_user.id
            order.audit_time = datetime.utcnow()
            db.session.commit()

            flash('审核通过，库存已转移', 'success')
            return redirect(url_for('transfer.list'))

        elif audit_result == 'rejected':
            order.audit_status = 'rejected'
            order.auditor_id = current_user.id
            order.audit_time = datetime.utcnow()
            db.session.commit()

            flash('审核已驳回', 'warning')
            return redirect(url_for('transfer.list'))

        else:
            flash('无效的审核结果', 'danger')
            return redirect(url_for('transfer.detail', id=id))

    except Exception as e:
        db.session.rollback()
        flash(f'审核失败:{str(e)}', 'danger')
        return redirect(url_for('transfer.detail', id=id))

@transfer_bp.route('/items')
@permission_required('inventory_manage')
@login_required
def items():
    keyword = request.args.get('keyword', '')
    product_id = request.args.get('product_id', '')
    source_location_id = request.args.get('source_location_id', '')
    target_location_id = request.args.get('target_location_id', '')
    audit_status = request.args.get('audit_status', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    order_id = request.args.get('order_id', '')

    query = TransferItem.query.join(TransferOrder).join(Product, TransferItem.product_id == Product.id)\
        .join(WarehouseLocation, TransferItem.source_location_id == WarehouseLocation.id)

    if keyword:
        query = query.filter(
            Product.name.ilike(f'%{keyword}%') |
            Product.code.ilike(f'%{keyword}%') |
            TransferOrder.order_no.ilike(f'%{keyword}%')
        )

    if product_id:
        query = query.filter(TransferItem.product_id == product_id)

    if source_location_id:
        query = query.filter(TransferItem.source_location_id == source_location_id)

    if target_location_id:
        query = query.filter(TransferItem.target_location_id == target_location_id)

    if audit_status:
        query = query.filter(TransferOrder.audit_status == audit_status)

    if order_id:
        query = query.filter(TransferItem.order_id == order_id)

    if start_date:
        query = query.filter(TransferOrder.create_time >= start_date)

    if end_date:
        query = query.filter(TransferOrder.create_time <= end_date)

    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(TransferItem.id.desc()).paginate(page=page, per_page=per_page)
    items = pagination.items

    products = Product.query.all()
    locations = WarehouseLocation.query.filter_by(status=True).all()

    return render_template('transfer/items.html',
                           items=items,
                           pagination=pagination,
                           keyword=keyword,
                           product_id=product_id,
                           source_location_id=source_location_id,
                           target_location_id=target_location_id,
                           audit_status=audit_status,
                           start_date=start_date,
                           end_date=end_date,
                           order_id=order_id,
                           products=products,
                           locations=locations
    )