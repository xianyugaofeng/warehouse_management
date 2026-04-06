from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from datetime import datetime
import logging
from app import db
from app.models.inspection import InspectionOrder
from app.models.purchase import PurchaseOrder
from app.models.product import Product, Supplier
from app.models.inventory import WarehouseLocation, Inventory
from app.utils.auth import permission_required
from app.utils.helpers import generate_inspection_no

# 配置日志记录器
logger = logging.getLogger(__name__)

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
    pending_orders = PurchaseOrder.query.filter(PurchaseOrder.status.in_(['pending_receipt', 'receiving'])).all()
    reject_locations = WarehouseLocation.query.filter_by(location_type='reject').all()
    return render_template('inspection/receive_list.html', 
                           pending_orders=pending_orders, 
                           reject_locations=reject_locations)

# 收货（不含质检）
@inspection_bp.route('/receive/<int:id>', methods=['GET', 'POST'])
@permission_required('inbound_manage')
@login_required
def receive_goods(id):
    purchase_order = PurchaseOrder.query.get_or_404(id)
    if purchase_order.status == 'completed':
        flash('该采购单已完成收货，请到待质检列表进行质检', 'info')
        return redirect(url_for('inspection.pending_inspection_list'))

    if request.method == 'POST':
        signature = request.form.get('signature')
        if not signature:
            flash('请仓库管理员签字确认', 'danger')
            return render_template('inspection/receive.html', 
                                   purchase_order=purchase_order, now=datetime.now())

        actual_quantity = int(request.form.get('actual_quantity', 0))
        
        if actual_quantity <= 0:
            flash('收货数量必须大于0', 'danger')
            return render_template('inspection/receive.html', 
                                   purchase_order=purchase_order, now=datetime.now())
        
        # 检查本次收货数量是否超过剩余数量
        remaining_quantity = purchase_order.quantity - (purchase_order.actual_quantity or 0)
        if actual_quantity > remaining_quantity:
            flash(f'本次收货数量不能超过剩余数量{remaining_quantity}', 'danger')
            return render_template('inspection/receive.html', 
                                   purchase_order=purchase_order, now=datetime.now())
        
        inspection_location = WarehouseLocation.query.filter_by(location_type='inspection', status=True).first()
        if not inspection_location:
            logger.error('未找到待检区库位，无法创建待检库存记录')
            flash('未设置待检区，请先配置仓库位置', 'danger')
            return render_template('inspection/receive.html', 
                                   purchase_order=purchase_order, now=datetime.now())
        
        purchase_order.actual_date = datetime.now().date()
        purchase_order.actual_quantity = (purchase_order.actual_quantity or 0) + actual_quantity

        # 判断采购单是否完成：累计实际收货数量达到计划数量时自动完成
        complete_receipt = purchase_order.actual_quantity >= purchase_order.quantity
        
        # 更新采购单状态
        if complete_receipt:
            purchase_order.status = 'completed'
        else:
            purchase_order.status = 'receiving'
        
        existing_inventory = Inventory.query.join(WarehouseLocation).filter(
            Inventory.product_id == purchase_order.product_id,
            WarehouseLocation.location_type == 'inspection'
        ).first()
        
        if existing_inventory:
            existing_inventory.quantity += actual_quantity
            logger.info(f'更新待检库存记录 {existing_inventory.id}，数量增加 {actual_quantity}')
        else:
            inventory = Inventory(
                product_id=purchase_order.product_id,
                location_id=inspection_location.id,
                quantity=actual_quantity,
                remark='待检'
            )
            db.session.add(inventory)
            logger.info(f'创建待检库存记录，商品:{purchase_order.product_id}, 库位:{inspection_location.id}, 数量:{actual_quantity}')
        
        try:
            db.session.commit()
            if complete_receipt:
                flash(f'收货完成！累计收货{purchase_order.actual_quantity}件，请到待质检列表进行质检', 'success')
                return redirect(url_for('inspection.pending_inspection_list'))
            else:
                flash(f'收货成功！本次收货{actual_quantity}件，累计收货{purchase_order.actual_quantity}件，剩余{remaining_quantity - actual_quantity}件待收货', 'success')
                return redirect(url_for('inspection.receive_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'收货失败:{str(e)}', 'danger')

    return render_template('inspection/receive.html', purchase_order=purchase_order, now=datetime.now())

# 待质检采购单列表
@inspection_bp.route('/pending_inspection')
@permission_required('inbound_manage')
@login_required
def pending_inspection_list():
    pending_orders = PurchaseOrder.query.filter_by(status='completed', quality_status='pending').all()
    return render_template('inspection/pending_inspection_list.html', pending_orders=pending_orders)

# 质检（收货完成后）
@inspection_bp.route('/inspect/<int:id>', methods=['GET', 'POST'])
@permission_required('inbound_manage')
@login_required
def inspect(id):
    purchase_order = PurchaseOrder.query.get_or_404(id)
    
    if purchase_order.status != 'completed':
        flash('只有已完成收货的采购单才能进行质检', 'danger')
        return redirect(url_for('inspection.receive_list'))
    
    if purchase_order.quality_status == 'completed':
        flash('该采购单已完成质检', 'info')
        return redirect(url_for('inspection.list'))
    
    reject_locations = WarehouseLocation.query.filter_by(location_type='reject').all()
    
    if request.method == 'POST':
        signature = request.form.get('signature')
        if not signature:
            flash('请仓库管理员签字确认', 'danger')
            return render_template('inspection/inspect.html', 
                                   purchase_order=purchase_order, 
                                   now=datetime.now(),
                                   reject_locations=reject_locations)
        
        qualified_quantity = int(request.form.get('qualified_quantity', 0))
        unqualified_quantity = int(request.form.get('unqualified_quantity', 0))
        defect_reason = request.form.get('defect_reason', '')
        defect_location_id = request.form.get('defect_location', '')
        
        total_quantity = purchase_order.actual_quantity or 0
        if qualified_quantity + unqualified_quantity != total_quantity:
            flash(f'合格数量和不合格数量之和必须等于收货总数量{total_quantity}', 'danger')
            return render_template('inspection/inspect.html', 
                                   purchase_order=purchase_order, 
                                   now=datetime.now(),
                                   reject_locations=reject_locations)
        
        inspection_location = WarehouseLocation.query.filter_by(location_type='inspection', status=True).first()
        pending_location = WarehouseLocation.query.filter_by(location_type='pending', status=True).first()
        
        if not inspection_location:
            flash('未设置待检区，请先配置仓库位置', 'danger')
            return render_template('inspection/inspect.html', 
                                   purchase_order=purchase_order, 
                                   now=datetime.now(),
                                   reject_locations=reject_locations)
        
        if not pending_location:
            flash('未设置待处理区，请先配置仓库位置', 'danger')
            return render_template('inspection/inspect.html', 
                                   purchase_order=purchase_order, 
                                   now=datetime.now(),
                                   reject_locations=reject_locations)
        
        inspection_inventory = Inventory.query.join(WarehouseLocation).filter(
            Inventory.product_id == purchase_order.product_id,
            WarehouseLocation.location_type == 'inspection'
        ).first()
        
        if not inspection_inventory or inspection_inventory.quantity < total_quantity:
            flash(f'待检区库存不足，无法进行质检', 'danger')
            return render_template('inspection/inspect.html', 
                                   purchase_order=purchase_order, 
                                   now=datetime.now(),
                                   reject_locations=reject_locations)
        
        inspection_no = generate_inspection_no()
        inspection_order = InspectionOrder(
            order_no=inspection_no,
            purchase_order_id=purchase_order.id,
            product_id=purchase_order.product_id,
            supplier_id=purchase_order.supplier_id,
            delivery_order_no=purchase_order.order_no,
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
        
        if unqualified_quantity > 0:
            reject_location_id = int(defect_location_id) if defect_location_id else None
            if not reject_location_id:
                flash('请选择不合格品暂存区库位', 'danger')
                return render_template('inspection/inspect.html', 
                                       purchase_order=purchase_order, 
                                       now=datetime.now(),
                                       reject_locations=reject_locations)
            
            reject_inventory = Inventory.query.join(WarehouseLocation).filter(
                Inventory.product_id == purchase_order.product_id,
                WarehouseLocation.location_type == 'reject'
            ).first()
            
            if reject_inventory:
                reject_inventory.quantity += unqualified_quantity
                reject_inventory.defect_reason = defect_reason
                reject_inventory.inspection_order_id = inspection_order.id
                logger.info(f'更新不合格品库存记录 {reject_inventory.id}，数量增加 {unqualified_quantity}')
            else:
                reject_inventory = Inventory(
                    product_id=purchase_order.product_id,
                    location_id=reject_location_id,
                    quantity=unqualified_quantity,
                    defect_reason=defect_reason,
                    inspection_order_id=inspection_order.id,
                    remark='检验不合格'
                )
                db.session.add(reject_inventory)
                logger.info(f'创建不合格品库存记录，商品:{purchase_order.product_id}, 库位:{reject_location_id}, 数量:{unqualified_quantity}')
        
        if qualified_quantity > 0:
            pending_inventory = Inventory.query.join(WarehouseLocation).filter(
                Inventory.product_id == purchase_order.product_id,
                WarehouseLocation.location_type == 'pending'
            ).first()
            
            if pending_inventory:
                pending_inventory.quantity += qualified_quantity
                pending_inventory.inspection_order_id = inspection_order.id
                logger.info(f'更新待处理库存记录 {pending_inventory.id}，数量增加 {qualified_quantity}')
            else:
                pending_inventory = Inventory(
                    product_id=purchase_order.product_id,
                    location_id=pending_location.id,
                    quantity=qualified_quantity,
                    inspection_order_id=inspection_order.id,
                    remark='待处理'
                )
                db.session.add(pending_inventory)
                logger.info(f'创建待处理库存记录，商品:{purchase_order.product_id}, 库位:{pending_location.id}, 数量:{qualified_quantity}')
        
        remaining_quantity = inspection_inventory.quantity - total_quantity
        if remaining_quantity == 0:
            db.session.delete(inspection_inventory)
            logger.info(f'删除待检库存记录 {inspection_inventory.id}，数量已全部转移')
        elif remaining_quantity > 0:
            inspection_inventory.quantity = remaining_quantity
            logger.info(f'更新待检库存记录 {inspection_inventory.id}，剩余数量:{remaining_quantity}')
        
        purchase_order.qualified_quantity = qualified_quantity
        purchase_order.unqualified_quantity = unqualified_quantity
        purchase_order.quality_status = 'completed'
        
        try:
            db.session.commit()
            if unqualified_quantity > 0:
                flash(f'质检完成：合格{qualified_quantity}件，不合格{unqualified_quantity}件（已存放于暂存区域）', 'warning')
            else:
                flash(f'质检完成：全部合格{qualified_quantity}件，请到入库管理创建入库单', 'success')
            return redirect(url_for('inspection.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'质检失败:{str(e)}', 'danger')
    
    return render_template('inspection/inspect.html', 
                           purchase_order=purchase_order, 
                           now=datetime.now(),
                           reject_locations=reject_locations)