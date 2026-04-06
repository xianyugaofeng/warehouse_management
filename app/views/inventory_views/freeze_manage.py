from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models.count import VarianceDocument, VarianceDetail, InventoryFreezeRecord
from app.models.inventory import InventoryChangeLog
from app.models.user import User
from app.utils.auth import permission_required
from app.utils.helpers import generate_variance_no
from app.views.inventory_views.count_manage import count_bp


@count_bp.route('/freeze/list')
@permission_required('inventory_manage')
@login_required
def freeze_list():
    """冻结记录列表"""
    status = request.args.get('status', '')
    freeze_type = request.args.get('freeze_type', '')
    
    query = InventoryFreezeRecord.query
    
    if status:
        query = query.filter_by(status=status)
    if freeze_type:
        query = query.filter_by(freeze_type=freeze_type)
    
    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(InventoryFreezeRecord.create_time.desc()).paginate(page=page, per_page=10)
    
    return render_template('count/freeze_list.html',
                         freezes=pagination.items,
                         pagination=pagination,
                         status=status,
                         freeze_type=freeze_type)


@count_bp.route('/variances/list')
@permission_required('inventory_manage')
@login_required
def variance_list():
    """差异单列表"""
    status = request.args.get('status', '')
    variance_type = request.args.get('variance_type', '')
    
    query = VarianceDocument.query
    
    if status:
        query = query.filter_by(status=status)
    if variance_type:
        query = query.filter_by(variance_type=variance_type)
    
    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(VarianceDocument.create_time.desc()).paginate(page=page, per_page=10)
    
    return render_template('count/variance_list.html',
                         variances=pagination.items,
                         pagination=pagination,
                         status=status,
                         variance_type=variance_type)


@count_bp.route('/variances/<int:variance_id>/detail')
@permission_required('inventory_manage')
@login_required
def variance_detail(variance_id):
    """差异单详情"""
    variance = VarianceDocument.query.get_or_404(variance_id)
    details = variance.details
    
    return render_template('count/variance_detail.html',
                         variance=variance,
                         details=details)


@count_bp.route('/variances/<int:variance_id>/approve', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def approve_variance(variance_id):
    """审核通过差异单"""
    variance = VarianceDocument.query.get_or_404(variance_id)
    force = request.form.get('force') == '1'
    
    if variance.status != 'pending':
        flash('只有待审状态的差异单可以审核', 'danger')
        return redirect(url_for('count.variance_detail', variance_id=variance_id))
    
    try:
        _approve_variance_internal(variance, force, current_user.id)
        
        db.session.commit()
        flash('差异单已审核通过，库存已调整', 'success')
        return redirect(url_for('count.variance_detail', variance_id=variance_id))
    except Exception as e:
        db.session.rollback()
        flash(f'审核失败: {str(e)}', 'danger')
        return redirect(url_for('count.variance_detail', variance_id=variance_id))


@count_bp.route('/variances/<int:variance_id>/reject', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def reject_variance(variance_id):
    """驳回差异单"""
    variance = VarianceDocument.query.get_or_404(variance_id)
    reason = request.form.get('reason', '')
    
    if variance.status != 'pending':
        flash('只有待审状态的差异单可以驳回', 'danger')
        return redirect(url_for('count.variance_detail', variance_id=variance_id))
    
    try:
        for detail in variance.details:
            if detail.count_detail.freeze_record_id:
                freeze_record = InventoryFreezeRecord.query.get(detail.count_detail.freeze_record_id)
                if freeze_record and freeze_record.status == 'frozen':
                    freeze_record.status = 'released'
                    freeze_record.released_time = datetime.utcnow()
                    freeze_record.released_reason = 'Variance rejected'
                    
                    inventory = freeze_record.inventory
                    if freeze_record.freeze_qty > inventory.frozen_quantity:
                        raise ValueError(
                            f'商品 {inventory.product.code} 冻结数量 {inventory.frozen_quantity} 不足以释放 {freeze_record.freeze_qty}'
                        )
                    inventory.frozen_quantity -= freeze_record.freeze_qty
        
        variance.status = 'rejected'
        variance.rejection_reason = reason
        variance.approver_id = current_user.id
        variance.approved_time = datetime.utcnow()
        
        db.session.commit()
        flash('差异单已驳回，库存冻结已释放', 'success')
        return redirect(url_for('count.variance_detail', variance_id=variance_id))
    except Exception as e:
        db.session.rollback()
        flash(f'驳回失败: {str(e)}', 'danger')
        return redirect(url_for('count.variance_detail', variance_id=variance_id))


def _create_variance_document(count, variance_type, details):
    """创建盘盈/盘亏单并执行冻结"""
    variance_doc = VarianceDocument(
        variance_no=generate_variance_no(),
        count_id=count.id,
        variance_type=variance_type,
        status='pending',
        total_variance_qty=sum(d.variance_quantity if variance_type == 'gain' else abs(d.variance_quantity) for d in details),
        total_items=len(details)
    )
    db.session.add(variance_doc)
    db.session.flush()
    
    for detail in details:
        var_detail = VarianceDetail(
            variance_doc_id=variance_doc.id,
            count_detail_id=detail.id,
            product_id=detail.product_id,
            location_id=detail.location_id,
            batch_no=detail.batch_no,
            snapshot_quantity=detail.snapshot_quantity,
            counted_quantity=detail.counted_quantity,
            variance_quantity=detail.variance_quantity,
            snapshot_locked=detail.snapshot_locked,
            snapshot_frozen=detail.snapshot_frozen,
            variance_reason=detail.variance_reason
        )
        db.session.add(var_detail)
        
        inventory = detail.inventory
        freeze_qty = abs(detail.variance_quantity)
        
        if variance_type == 'loss':
            if freeze_qty > inventory.available_quantity:
                raise ValueError(f'商品 {inventory.product.code} 可用库存 {inventory.available_quantity} 不足以冻结 {freeze_qty}')
        
        freeze_record = InventoryFreezeRecord(
            product_id=inventory.product_id,
            location_id=inventory.location_id,
            inventory_id=inventory.id,
            freeze_qty=freeze_qty,
            freeze_type='count_gain' if variance_type == 'gain' else 'count_loss',
            reason=f'Count Order #{count.count_no} - {variance_type} variance',
            variance_doc_id=variance_doc.id,
            count_id=count.id,
            status='frozen'
        )
        db.session.add(freeze_record)
        db.session.flush()
        
        inventory.frozen_quantity += freeze_qty
        detail.frozen_qty = freeze_qty
        detail.freeze_record_id = freeze_record.id
        detail.variance_doc_id = variance_doc.id


def _approve_variance_internal(variance, force, approver_id):
    """执行差异单审核的内部逻辑"""
    variance.approver_id = approver_id
    variance.approved_time = datetime.utcnow()
    variance.force_approved = force
    
    approver = db.session.get(User, approver_id)
    operator_name = approver.username if approver else 'system'
    
    for detail in variance.details:
        count_detail = detail.count_detail
        inventory = count_detail.inventory
        
        new_physical = inventory.quantity + detail.variance_quantity
        min_required = inventory.locked_quantity + (inventory.frozen_quantity - abs(detail.variance_quantity))
        
        if new_physical < min_required and not force:
            raise ValueError(
                f'商品 {inventory.product.code} 调整后物理库存 {new_physical} '
                f'小于锁定({inventory.locked_quantity}) + 冻结({min_required - inventory.locked_quantity}) 的和，'
                f'可用数量将为负，请使用强制通过选项'
            )
        
        if variance.variance_type == 'gain':
            inventory.quantity += detail.variance_quantity
        else:
            inventory.quantity -= abs(detail.variance_quantity)
            
        freeze_to_release = abs(detail.variance_quantity)
        if freeze_to_release > inventory.frozen_quantity:
            raise ValueError(
                f'商品 {inventory.product.code} 冻结数量 {inventory.frozen_quantity} 不足以释放 {freeze_to_release}'
            )
        inventory.frozen_quantity -= freeze_to_release
        
        quantity_after = inventory.quantity
        locked_after = inventory.locked_quantity
        frozen_after = inventory.frozen_quantity
        
        if count_detail.freeze_record_id:
            freeze_record = InventoryFreezeRecord.query.get(count_detail.freeze_record_id)
            if freeze_record and freeze_record.status == 'frozen':
                freeze_record.status = 'released'
                freeze_record.released_time = datetime.utcnow()
                freeze_record.released_reason = 'Variance approved'
        else:
            freeze_record = InventoryFreezeRecord.query.filter_by(
                variance_doc_id=variance.id,
                product_id=count_detail.product_id,
                location_id=count_detail.location_id,
                status='frozen'
            ).first()
            if freeze_record:
                freeze_record.status = 'released'
                freeze_record.released_time = datetime.utcnow()
                freeze_record.released_reason = 'Variance approved'
        
        detail.processed = True
        detail.processed_time = datetime.utcnow()
        
        change_log = InventoryChangeLog(
            inventory_id=inventory.id,
            change_type='count_adjustment',
            quantity_before=detail.snapshot_quantity,
            quantity_after=quantity_after,
            locked_quantity_before=detail.snapshot_locked,
            locked_quantity_after=locked_after,
            frozen_quantity_before=detail.snapshot_frozen,
            frozen_quantity_after=frozen_after,
            operator=operator_name,
            reason=f'盘点调整 - 盘点单号: {variance.count.count_no}, 差异单号: {variance.variance_no}, 变动量: {"+" if detail.variance_quantity > 0 else ""}{detail.variance_quantity}',
            reference_id=variance.id,
            reference_type='variance'
        )
        db.session.add(change_log)
    
    variance.status = 'approved'