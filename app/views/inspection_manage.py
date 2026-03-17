from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from datetime import datetime
from app import db
from app.models.inspection import InspectionOrder, InspectionItem, DefectiveProduct
from app.models.purchase import PurchaseOrder, PurchaseItem
from app.models.product import Product, Supplier
from app.models.inventory import WarehouseLocation
from app.utils.auth import permission_required
from app.utils.helpers import generate_inspection_no

inspection_bp = Blueprint('inspection', __name__)

# 质检单列表
@inspection_bp.route('/list')
@permission_required('inbound_manage')
@login_required
def list():
    keyword = request.args.get('keyword', '')
    supplier_id = request.args.get('supplier_id', '')
    status = request.args.get('status', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    query = InspectionOrder.query
    if keyword:
        query = query.filter(InspectionOrder.order_no.ilike(f'%{keyword}%') |
                             InspectionOrder.purchase_order.has(order_no=keyword))
    if supplier_id:
        try:
            supplier_id_int = int(supplier_id)
            query = query.filter_by(supplier_id=supplier_id_int)
        except ValueError:
            pass
    if status:
        query = query.filter_by(status=status)
    if start_date:
        query = query.filter(InspectionOrder.create_time >= start_date)
    if end_date:
        query = query.filter(InspectionOrder.create_time <= end_date)

    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(InspectionOrder.create_time.desc()).paginate(page=page, per_page=per_page)
    orders = pagination.items

    suppliers = Supplier.query.all()
    return render_template('inspection/list.html',
                           orders=orders,
                           pagination=pagination,
                           keyword=keyword,
                           supplier_id=supplier_id,
                           status=status,
                           start_date=start_date,
                           end_date=end_date,
                           suppliers=suppliers
    )

# 质检单详情
@inspection_bp.route('/detail/<int:id>')
@permission_required('inbound_manage')
@login_required
def detail(id):
    inspection_order = InspectionOrder.query.get_or_404(id)
    return render_template('inspection/detail.html', inspection_order=inspection_order)

# 待收货采购单列表
@inspection_bp.route('/receive_list')
@permission_required('inbound_manage')
@login_required
def receive_list():
    # 查找待收货的采购单
    pending_orders = PurchaseOrder.query.filter_by(status='pending_receipt').all()
    # 获取暂存区库位
    reject_locations = WarehouseLocation.query.filter_by(location_type='reject').all()
    return render_template('inspection/receive_list.html', 
                           pending_orders=pending_orders, 
                           reject_locations=reject_locations)

# 收货和质检
@inspection_bp.route('/receive/<int:id>', methods=['GET', 'POST'])
@permission_required('inbound_manage')
@login_required
def receive(id):
    purchase_order = PurchaseOrder.query.get_or_404(id)
    if purchase_order.status == 'completed':
        flash('该采购单已完成', 'danger')
        return redirect(url_for('purchase.list'))

    if request.method == 'POST':
        # 接收质检和收货数据
        delivery_order_no = purchase_order.order_no  # 送货单号即采购单号
        signature = request.form.get('signature')
        
        if not signature:
            flash('请仓库管理员签字确认', 'danger')
            return render_template('inspection/receive.html', 
                                   purchase_order=purchase_order, now=datetime.now(), 
                                   reject_locations=WarehouseLocation.query.filter_by(location_type='reject').all())

        # 更新采购单状态为收货中
        purchase_order.status = 'receiving'
        purchase_order.actual_date = datetime.now().date()

        # 创建检验单
        inspection_no = generate_inspection_no()
        total_quantity = 0
        qualified_quantity = 0
        unqualified_quantity = 0
        # 处理每个采购明细的质检和收货
        for item in purchase_order.items:
            actual_quantity = int(request.form.get(f'actual_quantity_{item.id}', 0))
            quality_status = request.form.get(f'quality_status_{item.id}', 'pending')
            defect_reason = request.form.get(f'defect_reason_{item.id}', '')
            defect_location_id = request.form.get(f'defect_location_{item.id}', '')

            item.actual_quantity = actual_quantity
            item.quality_status = quality_status

            total_quantity += actual_quantity
            if quality_status == 'passed':
                qualified_quantity += actual_quantity
            elif quality_status == 'failed':
                unqualified_quantity += actual_quantity
        # 检查是否有不合格品需要处理
        if unqualified_quantity > 0:
            # 查找不合格品暂放区域
            reject_location = WarehouseLocation.query.filter_by(location_type='reject').first()
            if not reject_location:
                flash('未设置不合格品暂放区域，请先配置仓库位置', 'danger')
                # 获取暂存区库位
                reject_locations = WarehouseLocation.query.filter_by(location_type='reject').all()
                return render_template('inspection/receive.html', 
                                        purchase_order=purchase_order, now=datetime.now(), 
                                        reject_locations=WarehouseLocation.query.filter_by(location_type='reject').all())

            flash(f'检验完成：合格{qualified_quantity}件，不合格{unqualified_quantity}件（已存放于暂放区域）', 'warning')
        else:
            flash(f'检验完成：全部合格{qualified_quantity}件，请到入库管理创建入库单', 'success')

        # 创建检验单
        inspection_order = InspectionOrder(
            order_no=inspection_no,
            purchase_order_id=purchase_order.id,
            supplier_id=purchase_order.supplier_id,
            delivery_order_no=purchase_order.order_no,  # 送货单号即采购单号
            operator_id=current_user.id,
            inspection_date=datetime.now().date(),
            total_quantity=total_quantity,
            qualified_quantity=qualified_quantity,
            unqualified_quantity=unqualified_quantity,
            status='completed',
            signature=signature,
            remark='检验完成'
        )
        db.session.add(inspection_order)
        db.session.flush()

        # 创建检验明细
        for item in purchase_order.items:
            actual_quantity = int(request.form.get(f'actual_quantity_{item.id}', 0))
            quality_status = request.form.get(f'quality_status_{item.id}', 'pending')
            defect_reason = request.form.get(f'defect_reason_{item.id}', '')
            defect_location_id = request.form.get(f'defect_location_{item.id}', '')

            qualified_qty = actual_quantity if quality_status == 'passed' else 0
            unqualified_qty = actual_quantity if quality_status == 'failed' else 0
            
            # 创建检验明细
            inspection_item = InspectionItem(
                inspection_id=inspection_order.id,
                product_id=item.product_id,
                quantity=actual_quantity,
                qualified_quantity=qualified_qty,
                unqualified_quantity=unqualified_qty,
                quality_status=quality_status,
                defect_reason=defect_reason if quality_status == 'failed' else None
            )
            db.session.add(inspection_item)
            
            # 处理不合格商品
            if quality_status == 'failed' and actual_quantity > 0:
                # 获取暂存区库位
                reject_location_id = int(defect_location_id) if defect_location_id else None
                if not reject_location_id:
                    reject_location = WarehouseLocation.query.filter_by(location_type='reject').first()
                    if reject_location:
                        reject_location_id = reject_location.id
                
                if reject_location_id:
                    # 创建不合格商品记录
                    defective_product = DefectiveProduct(
                        product_id=item.product_id,
                        location_id=reject_location_id,
                        batch_no=f'B{datetime.now().strftime("%Y%m%d")}{item.id}',
                        quantity=actual_quantity,
                        defect_reason=defect_reason,
                        inspection_order_id=inspection_order.id,
                        remark='检验不合格'
                    )
                    db.session.add(defective_product)
        # 计算累计合格数量
        total_qualified = sum(item.actual_quantity or 0 for item in purchase_order.items if item.quality_status == 'passed')
        
        # 判断采购单是否完成
        if purchase_order.allow_partial_receipt:
            # 允许部分收货，需要用户手动标记完成
            complete_receipt = request.form.get('complete_receipt') == 'true'
        else:
            # 不允许部分收货，累计合格数量达到计划数量时自动完成
            complete_receipt = total_qualified >= purchase_order.total_amount
        
        # 更新采购单状态
        if complete_receipt:
            purchase_order.status = 'completed'
        else:
            purchase_order.status = 'receiving'

        try:
            db.session.commit()
            return redirect(url_for('inspection.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'操作失败:{str(e)}', 'danger')

    return render_template('inspection/receive.html', purchase_order=purchase_order)