from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from datetime import datetime
from app import db
from app.models.inspection import InspectionOrder, InspectionItem
from app.models.purchase import PurchaseOrder
from app.models.product import Product, Supplier
from app.models.inventory import WarehouseLocation, Inventory
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
        signature = request.form.get('signature')
        
        if not signature:
            flash('请仓库管理员签字确认', 'danger')
            return render_template('inspection/receive.html', 
                                   purchase_order=purchase_order, now=datetime.now(), 
                                   reject_locations=WarehouseLocation.query.filter_by(location_type='reject').all())

        # 获取质检数据
        actual_quantity = int(request.form.get('actual_quantity', 0))
        qualified_quantity = int(request.form.get('qualified_quantity', 0))
        unqualified_quantity = int(request.form.get('unqualified_quantity', 0))
        quality_status = request.form.get('quality_status', 'pending')
        defect_reason = request.form.get('defect_reason', '')
        defect_location_id = request.form.get('defect_location', '')

        # 验证数量
        if qualified_quantity + unqualified_quantity != actual_quantity:
            flash('合格数量和不合格数量之和必须等于实际收货数量', 'danger')
            return render_template('inspection/receive.html', 
                                   purchase_order=purchase_order, now=datetime.now(), 
                                   reject_locations=WarehouseLocation.query.filter_by(location_type='reject').all())
        
        # 检查本次收货数量是否超过剩余数量
        remaining_quantity = purchase_order.quantity - (purchase_order.actual_quantity or 0)
        if actual_quantity > remaining_quantity:
            flash(f'本次收货数量不能超过剩余数量{remaining_quantity}', 'danger')
            return render_template('inspection/receive.html', 
                                   purchase_order=purchase_order, now=datetime.now(), 
                                   reject_locations=WarehouseLocation.query.filter_by(location_type='reject').all())
        
        # 更新采购单（累计更新）
        purchase_order.actual_date = datetime.now().date()
        purchase_order.actual_quantity = (purchase_order.actual_quantity or 0) + actual_quantity
        purchase_order.qualified_quantity = (purchase_order.qualified_quantity or 0) + qualified_quantity
        purchase_order.unqualified_quantity = (purchase_order.unqualified_quantity or 0) + unqualified_quantity
        purchase_order.quality_status = quality_status

        # 判断采购单是否完成：累计实际收货数量达到计划数量时自动完成
        complete_receipt = purchase_order.actual_quantity >= purchase_order.quantity
        
        # 更新采购单状态
        if complete_receipt:
            purchase_order.status = 'completed'
        else:
            purchase_order.status = 'receiving'

        # 只有已完成的采购单才能进行质检和创建检验合格单
        if purchase_order.status == 'completed':
            # 检查是否有不合格品需要处理
            if unqualified_quantity > 0:
                # 查找不合格品暂放区域
                reject_location = WarehouseLocation.query.filter_by(location_type='reject').first()
                if not reject_location:
                    flash('未设置不合格品暂放区域，请先配置仓库位置', 'danger')
                    return render_template('inspection/receive.html', 
                                            purchase_order=purchase_order, now=datetime.now(), 
                                            reject_locations=WarehouseLocation.query.filter_by(location_type='reject').all())

                flash(f'检验完成：合格{qualified_quantity}件，不合格{unqualified_quantity}件（已存放于暂放区域）', 'warning')
            else:
                flash(f'检验完成：全部合格{qualified_quantity}件，请到入库管理创建入库单', 'success')

            # 创建检验单
            inspection_no = generate_inspection_no()
            inspection_order = InspectionOrder(
                order_no=inspection_no,
                purchase_order_id=purchase_order.id,
                supplier_id=purchase_order.supplier_id,
                delivery_order_no=purchase_order.order_no,
                operator_id=current_user.id,
                inspection_date=datetime.now().date(),
                total_quantity=actual_quantity,
                qualified_quantity=qualified_quantity,
                unqualified_quantity=unqualified_quantity,
                status='completed',
                signature=signature,
                remark='检验完成'
            )
            db.session.add(inspection_order)
            db.session.flush()

            # 创建检验明细
            inspection_item = InspectionItem(
                inspection_id=inspection_order.id,
                product_id=purchase_order.product_id,
                quantity=actual_quantity,
                qualified_quantity=qualified_quantity,
                unqualified_quantity=unqualified_quantity,
                quality_status=quality_status,
                defect_reason=defect_reason if quality_status == 'completed' else None
            )
            db.session.add(inspection_item)
            
            # 处理不合格商品（只有不合格商品才创建库存记录并关联检验单）
            if quality_status == 'completed' and unqualified_quantity > 0:
                # 获取暂存区库位
                reject_location_id = int(defect_location_id) if defect_location_id else None
                if not reject_location_id:
                    reject_location = WarehouseLocation.query.filter_by(location_type='reject').first()
                    if reject_location:
                        reject_location_id = reject_location.id
                
                if reject_location_id:
                    # 创建不合格商品库存记录
                    # 检查是否已存在相同商品、库位和批次的库存记录
                    existing_inventory = Inventory.query.filter_by(
                        product_id=purchase_order.product_id,
                        location_id=reject_location_id,
                        batch_no=f'B{datetime.now().strftime("%Y%m%d")}{purchase_order.id}'
                    ).first()
                    
                    if existing_inventory:
                        # 如果已存在，更新数量
                        existing_inventory.quantity += unqualified_quantity
                        existing_inventory.defect_reason = defect_reason
                        existing_inventory.inspection_order_id = inspection_order.id
                    else:
                        # 如果不存在，创建新记录
                        inventory = Inventory(
                            product_id=purchase_order.product_id,
                            location_id=reject_location_id,
                            batch_no=f'B{datetime.now().strftime("%Y%m%d")}{purchase_order.id}',
                            quantity=unqualified_quantity,
                            defect_reason=defect_reason,
                            inspection_order_id=inspection_order.id,
                            remark='检验不合格'
                        )
                        db.session.add(inventory)
            
            # 注意：合格商品不在这里创建库存记录，需要通过入库流程创建入库单
        else:
            flash(f'收货完成：本次收货{actual_quantity}件，累计合格{purchase_order.qualified_quantity + qualified_quantity}件，累计不合格{purchase_order.unqualified_quantity + unqualified_quantity}件。采购单状态为收货中，允许后续再次收货。', 'info')

        try:
            db.session.commit()
            return redirect(url_for('inspection.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'操作失败:{str(e)}', 'danger')

    return render_template('inspection/receive.html', purchase_order=purchase_order)