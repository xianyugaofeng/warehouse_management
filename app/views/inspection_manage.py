from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from datetime import datetime
import logging
from app import db
from app.models.inspection import InspectionOrder, InspectionItem
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
        old_status = purchase_order.status
        if complete_receipt:
            purchase_order.status = 'completed'
        else:
            purchase_order.status = 'receiving'
        
        # 采购单状态变更的自动化规则
        # 规则1：当采购单处于收货状态时，创建库存记录，放到待检区，同步库存状态为待检状态
        # 规则2：当采购单从收货中转换到已完成时，将库存放到待检区，同步库存状态为待检状态
        # 规则3：采购单直接从待收货到已完成时，创建库存，将库存放到待检区，同步库存状态为待检状态
        if (old_status == 'pending_receipt' and purchase_order.status == 'receiving') or \
           (old_status == 'receiving' and purchase_order.status == 'completed') or \
           (old_status == 'pending_receipt' and purchase_order.status == 'completed'):
            
            # 查找待检区库位
            inspection_location = WarehouseLocation.query.filter_by(location_type='inspection', status=True).first()
            if not inspection_location:
                logger.error(f'未找到待检区库位，无法创建待检库存记录')
                flash('未设置待检区，请先配置仓库位置', 'danger')
                return render_template('inspection/receive.html', 
                                       purchase_order=purchase_order, now=datetime.now(), 
                                       reject_locations=WarehouseLocation.query.filter_by(location_type='reject').all())
            
            # 创建待检库存记录
            logger.info(f'采购单 {purchase_order.order_no} 状态从 {old_status} 变更为 {purchase_order.status}，执行自动化规则：创建待检库存记录')
            
            batch_no = f'B{datetime.now().strftime("%Y%m%d")}{purchase_order.id}'
            existing_inventory = Inventory.query.filter_by(
                product_id=purchase_order.product_id,
                location_id=inspection_location.id,
                batch_no=batch_no
            ).first()
            
            if existing_inventory:
                # 如果已存在，更新数量
                existing_inventory.quantity += actual_quantity
                logger.info(f'更新待检库存记录 {existing_inventory.id}，数量增加 {actual_quantity}')
            else:
                # 如果不存在，创建新记录
                inventory = Inventory(
                    product_id=purchase_order.product_id,
                    location_id=inspection_location.id,
                    batch_no=batch_no,
                    quantity=actual_quantity,
                    remark='待检'
                )
                db.session.add(inventory)
                logger.info(f'创建待检库存记录，商品:{purchase_order.product_id}, 库位:{inspection_location.id}, 数量:{actual_quantity}')

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
            
            # 检验时为不合格商品和合格商品分开创建库存记录
            if quality_status == 'completed':
                # 查找待检区库位
                inspection_location = WarehouseLocation.query.filter_by(location_type='inspection', status=True).first()
                # 查找待处理区库位
                pending_location = WarehouseLocation.query.filter_by(location_type='pending', status=True).first()
                
                if not inspection_location:
                    logger.error(f'未找到待检区库位，无法处理检验后的库存')
                    flash('未设置待检区，请先配置仓库位置', 'danger')
                    return render_template('inspection/receive.html', 
                                            purchase_order=purchase_order, now=datetime.now(), 
                                            reject_locations=WarehouseLocation.query.filter_by(location_type='reject').all())
                
                if not pending_location:
                    logger.error(f'未找到待处理区库位，无法处理检验后的库存')
                    flash('未设置待处理区，请先配置仓库位置', 'danger')
                    return render_template('inspection/receive.html', 
                                            purchase_order=purchase_order, now=datetime.now(), 
                                            reject_locations=WarehouseLocation.query.filter_by(location_type='reject').all())
                
                # 查找待检区的库存记录
                batch_no = f'B{datetime.now().strftime("%Y%m%d")}{purchase_order.id}'
                inspection_inventories = Inventory.query.filter_by(
                    product_id=purchase_order.product_id,
                    location_id=inspection_location.id,
                    batch_no=batch_no
                ).all()
                
                # 处理不合格商品：将不合格商品从待检区转移到不合格品区
                if unqualified_quantity > 0:
                    # 获取暂存区库位
                    reject_location_id = int(defect_location_id) if defect_location_id else None
                    if not reject_location_id:
                        reject_location = WarehouseLocation.query.filter_by(location_type='reject').first()
                        if reject_location:
                            reject_location_id = reject_location.id
                    
                    if reject_location_id:
                        # 检查是否已存在相同商品、库位和批次的库存记录
                        existing_inventory = Inventory.query.filter_by(
                            product_id=purchase_order.product_id,
                            location_id=reject_location_id,
                            batch_no=batch_no
                        ).first()
                        
                        if existing_inventory:
                            # 如果已存在，更新数量
                            existing_inventory.quantity += unqualified_quantity
                            existing_inventory.defect_reason = defect_reason
                            existing_inventory.inspection_order_id = inspection_order.id
                            logger.info(f'更新不合格品库存记录 {existing_inventory.id}，数量增加 {unqualified_quantity}，检验单:{inspection_order.order_no}')
                        else:
                            # 如果不存在，创建新记录
                            inventory = Inventory(
                                product_id=purchase_order.product_id,
                                location_id=reject_location_id,
                                batch_no=batch_no,
                                quantity=unqualified_quantity,
                                defect_reason=defect_reason,
                                inspection_order_id=inspection_order.id,
                                remark='检验不合格'
                            )
                            db.session.add(inventory)
                            logger.info(f'创建不合格品库存记录，商品:{purchase_order.product_id}, 库位:{reject_location_id}, 数量:{unqualified_quantity}，检验单:{inspection_order.order_no}')
                
                # 处理合格商品：将合格商品从待检区转移到待处理区
                if qualified_quantity > 0:
                    # 查找待处理区的库存记录
                    existing_pending_inventory = Inventory.query.filter_by(
                        product_id=purchase_order.product_id,
                        location_id=pending_location.id,
                        batch_no=batch_no
                    ).first()
                    
                    if existing_pending_inventory:
                        # 如果待处理区已存在库存记录，更新数量
                        existing_pending_inventory.quantity += qualified_quantity
                        existing_pending_inventory.inspection_order_id = inspection_order.id
                        logger.info(f'更新待处理库存记录 {existing_pending_inventory.id}，数量增加 {qualified_quantity}，检验单:{inspection_order.order_no}')
                    else:
                        # 如果待处理区不存在库存记录，创建新记录
                        pending_inventory = Inventory(
                            product_id=purchase_order.product_id,
                            location_id=pending_location.id,
                            batch_no=batch_no,
                            quantity=qualified_quantity,
                            inspection_order_id=inspection_order.id,
                            remark='待处理'
                        )
                        db.session.add(pending_inventory)
                        logger.info(f'创建待处理库存记录，商品:{purchase_order.product_id}, 库位:{pending_location.id}, 数量:{qualified_quantity}，检验单:{inspection_order.order_no}')
                
                # 更新待检区库存记录的数量
                for inv in inspection_inventories:
                    # 计算剩余数量
                    remaining_quantity = inv.quantity - actual_quantity
                    if remaining_quantity <= 0:
                        # 如果数量为0或负数，删除库存记录
                        db.session.delete(inv)
                        logger.info(f'删除待检库存记录 {inv.id}，数量已全部转移')
                    else:
                        # 如果还有剩余数量，更新库存记录
                        inv.quantity = remaining_quantity
                        logger.info(f'更新待检库存记录 {inv.id}，剩余数量:{remaining_quantity}')
        else:
            flash(f'收货完成：本次收货{actual_quantity}件，累计合格{purchase_order.qualified_quantity + qualified_quantity}件，累计不合格{purchase_order.unqualified_quantity + unqualified_quantity}件。采购单状态为收货中，允许后续再次收货。', 'info')

        try:
            db.session.commit()
            return redirect(url_for('inspection.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'操作失败:{str(e)}', 'danger')

    return render_template('inspection/receive.html', purchase_order=purchase_order)