from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models.count import InventoryCount, InventoryCountDetail, VarianceDocument, VarianceDetail, InventoryFreezeRecord
from app.models.inventory import Inventory, WarehouseLocation, InventoryChangeLog
from app.models.product import Product, Category, Supplier
from app.models.user import User
from app.utils.auth import permission_required
from app.utils.helpers import generate_count_no, generate_variance_no
import json

count_bp = Blueprint('count', __name__)


# ==================== 盘点单管理 ====================

@count_bp.route('/list')
@permission_required('inventory_manage')
@login_required
def count_list():
    """盘点单列表"""
    status = request.args.get('status', '')
    count_type = request.args.get('count_type', '')
    keyword = request.args.get('keyword', '')
    
    query = InventoryCount.query
    
    if status:
        query = query.filter_by(status=status)
    if count_type:
        query = query.filter_by(count_type=count_type)
    if keyword:
        query = query.filter(InventoryCount.count_no.ilike(f'%{keyword}%'))
    
    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(InventoryCount.create_time.desc()).paginate(page=page, per_page=10)
    
    return render_template('count/list.html',
                         counts=pagination.items,
                         pagination=pagination,
                         status=status,
                         count_type=count_type,
                         keyword=keyword)


@count_bp.route('/create', methods=['GET', 'POST'])
@permission_required('inventory_manage')
@login_required
def create_count():
    """创建盘点单"""
    if request.method == 'POST':
        count_type = request.form.get('count_type')  # open_count / blind_count
        scope_type = request.form.get('scope_type')  # location / category / product / all
        plan_date = request.form.get('plan_date')
        remark = request.form.get('remark', '')
        
        # 解析范围筛选条件
        scope_filter = {}
        if scope_type == 'location':
            location_ids = request.form.getlist('location_ids')
            scope_filter = {'location_ids': [int(x) for x in location_ids if x]}
        elif scope_type == 'category':
            category_ids = request.form.getlist('category_ids')
            scope_filter = {'category_ids': [int(x) for x in category_ids if x]}
        elif scope_type == 'product':
            product_ids = request.form.getlist('product_ids')
            scope_filter = {'product_ids': [int(x) for x in product_ids if x]}
        
        try:
            # 创建盘点单
            count = InventoryCount(
                count_no=generate_count_no(),
                count_type=count_type,
                scope_type=scope_type,
                scope_filter=json.dumps(scope_filter),
                plan_date=datetime.strptime(plan_date, '%Y-%m-%d').date(),
                operator_id=current_user.id,
                status='draft',
                remark=remark
            )
            db.session.add(count)
            db.session.flush()  # 获取count.id
            
            # 创建盘点单时会自动创建盘点明细和创建快照数据
            # 创建快照：根据范围筛选获取库存数据
            _create_snapshot(count, scope_type, scope_filter)
            
            db.session.commit()
            flash(f'盘点单 {count.count_no} 创建成功，共 {count.total_items} 个商品', 'success')
            return redirect(url_for('count.detail', count_id=count.id))
        except Exception as e:
            db.session.rollback()
            flash(f'创建盘点单失败: {str(e)}', 'danger')
            return redirect(url_for('count.create_count'))
    
    # GET 请求：渲染创建页面
    categories = Category.query.all()
    locations = WarehouseLocation.query.filter_by(status=True).all()
    products = Product.query.all()
    
    return render_template('count/create.html',
                         categories=categories,
                         locations=locations,
                         products=products)


def _create_snapshot(count, scope_type, scope_filter):
    """
    创建库存快照：根据范围类型和筛选条件，获取当前库存数据
    并创建InventoryCountDetail快照记录
    """
    query = Inventory.query
    
    # 应用范围筛选
    if scope_type == 'location':
        location_ids = scope_filter.get('location_ids', [])
        query = query.filter(Inventory.location_id.in_(location_ids))
    elif scope_type == 'category':
        category_ids = scope_filter.get('category_ids', [])
        query = query.join(Product).filter(Product.category_id.in_(category_ids))
    elif scope_type == 'product':
        product_ids = scope_filter.get('product_ids', [])
        query = query.filter(Inventory.product_id.in_(product_ids))
    # scope_type == 'all' 时不加额外过滤
    
    inventories = query.all()
    
    for inv in inventories:
        detail = InventoryCountDetail(
            count_id=count.id,
            inventory_id=inv.id,
            product_id=inv.product_id,
            location_id=inv.location_id,
            batch_no=inv.batch_no,      # 库存的批次号
            snapshot_quantity=inv.quantity,
            snapshot_locked=inv.locked_quantity,
            snapshot_frozen=inv.frozen_quantity,
            snapshot_available=inv.available_quantity,
            snapshot_time=datetime.utcnow()
        )
        db.session.add(detail)
    
    count.total_items = len(inventories)
    count.counted_items = 0
    count.variance_items = 0


@count_bp.route('/detail/<int:count_id>')
@permission_required('inventory_manage')
@login_required
def detail(count_id):
    """盘点单详情与实盘录入页面"""
    count = InventoryCount.query.get_or_404(count_id)
    
    # 分页获取明细
    page = request.args.get('page', 1, type=int)
    details = count.details.paginate(page=page, per_page=20)
    
    # 计算统计数据
    all_details = count.details.all()
    counted = sum(1 for d in all_details if d.counted_quantity is not None)
    has_variance = sum(1 for d in all_details if d.variance_type in ['gain', 'loss'])
    
    count.counted_items = counted
    count.variance_items = has_variance
    
    return render_template('count/detail.html',
                         count=count,
                         details=details.items,
                         pagination=details,
                         count_type_display='明盘' if count.count_type == 'open_count' else '暗盘')


@count_bp.route('/detail/<int:count_id>/update_item/<int:detail_id>', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def update_item(count_id, detail_id):
    """
    更新单条盘点明细的实盘数量
    请求体：{ "counted_qty": 100, "reason": "可选的原因" }
    """
    count = InventoryCount.query.get_or_404(count_id)
    detail = InventoryCountDetail.query.get_or_404(detail_id)
    
    if detail.count_id != count_id:
        return jsonify({'success': False, 'message': '明细不属于该盘点单'}), 400
    
    try:
        data = request.get_json()
        counted_qty = data.get('counted_qty')
        reason = data.get('reason', '')
        
        if counted_qty is None:
            return jsonify({'success': False, 'message': '实盘数量不能为空'}), 400
        
        if counted_qty < 0:
            return jsonify({'success': False, 'message': '实盘数量不能为负'}), 400
        
        # 更新实盘数量
        detail.counted_quantity = int(counted_qty)
        detail.counted_time = datetime.utcnow()
        detail.variance_reason = reason
        
        # 自动计算差异
        detail.calculate_variance()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '实盘数量已更新',
            'variance_qty': detail.variance_quantity,
            'variance_type': detail.variance_type
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'}), 500


@count_bp.route('/detail/<int:count_id>/variance_preview')
@permission_required('inventory_manage')
@login_required
def variance_preview(count_id):
    """差异预览"""
    count = InventoryCount.query.get_or_404(count_id)
    
    all_details = count.details.all()
    
    # 分类整理差异
    gains = []  # 盘盈
    losses = []  # 盘亏
    no_variance = []  # 无差异
    uncounted = []  # 未实盘
    
    for detail in all_details:
        if detail.counted_quantity is None:
            uncounted.append(detail)
        elif detail.variance_type == 'gain':
            gains.append(detail)
        elif detail.variance_type == 'loss':
            losses.append(detail)
        else:
            no_variance.append(detail)
    
    # 计算合计
    total_gain = sum(d.variance_quantity for d in gains)
    total_loss = sum(abs(d.variance_quantity) for d in losses)
    
    return render_template('count/variance_preview.html',
                         count=count,
                         gains=gains,
                         losses=losses,
                         no_variance=no_variance,
                         uncounted=uncounted,
                         total_gain=total_gain,
                         total_loss=total_loss)


@count_bp.route('/detail/<int:count_id>/generate_variances', methods=['POST'])
@permission_required('inventory_manage')
@login_required
def generate_variances(count_id):
    """
    根据差异明细生成盘盈/盘亏单
    同时冻结差异数量的物理库存
    """
    count = InventoryCount.query.get_or_404(count_id)
    
    if count.status != 'draft' and count.status != 'in_progress':
        flash('只有草稿或进行中的盘点单可以生成差异单', 'danger')
        return redirect(url_for('count.detail', count_id=count_id))
    
    try:
        all_details = count.details.all()
        
        # 按差异类型分组
        gains = [d for d in all_details if d.variance_type == 'gain']
        losses = [d for d in all_details if d.variance_type == 'loss']
        
        # 生成盘盈单
        # 盘点单对应多条盘点明细
        if gains:
            _create_variance_document(count, 'gain', gains)
        
        # 生成盘亏单
        if losses:
            _create_variance_document(count, 'loss', losses)
        
        # 更新盘点单状态
        count.status = 'completed'
        
        db.session.commit()
        flash('差异单已生成并已冻结差异数量，等待审核...', 'success')
        return redirect(url_for('count.detail', count_id=count_id))
    except Exception as e:
        db.session.rollback()
        flash(f'生成差异单失败: {str(e)}', 'danger')
        return redirect(url_for('count.detail', count_id=count_id))


def _create_variance_document(count, variance_type, details):
    """创建盘盈/盘亏单并执行冻结"""
    variance_doc = VarianceDocument(
        variance_no=generate_variance_no(),
        count_id=count.id,
        variance_type=variance_type,
        status='pending',
        total_variance_qty=sum(d.variance_quantity if variance_type == 'gain' else abs(d.variance_quantity) for d in details),
        total_items=len(details)    # 统计录入实盘的盘点明细数量
    )
    db.session.add(variance_doc)
    db.session.flush()
    
    # 创建明细并冻结库存
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
        
        # 冻结差异数量到库存
        inventory = detail.inventory
        freeze_qty = abs(detail.variance_quantity)
        
        # 检查可用库存是否足够（盘亏时需要检查）
        if variance_type == 'loss':
            if freeze_qty > inventory.available_quantity:
                raise ValueError(f'商品 {inventory.product.code} 可用库存 {inventory.available_quantity} 不足以冻结 {freeze_qty}')
        
        # 创建冻结记录
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
        
        # 更新库存冻结数量
        inventory.frozen_quantity += freeze_qty
        detail.frozen_qty = freeze_qty
        detail.freeze_record_id = freeze_record.id
        detail.variance_doc_id = variance_doc.id


# ==================== 差异单审核 ====================

@count_bp.route('/variances/list')
@permission_required('inventory_manage')
@login_required
def variance_list():
    """差异单列表"""
    status = request.args.get('status', 'pending')
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
        # 执行库存调整
        _approve_variance_internal(variance, force, current_user.id)
        
        db.session.commit()
        flash('差异单已审核通过，库存已调整', 'success')
        return redirect(url_for('count.variance_detail', variance_id=variance_id))
    except Exception as e:
        db.session.rollback()
        flash(f'审核失败: {str(e)}', 'danger')
        return redirect(url_for('count.variance_detail', variance_id=variance_id))


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
        # 解冻所有冻结记录
        for detail in variance.details:
            if detail.count_detail.freeze_record_id:
                freeze_record = InventoryFreezeRecord.query.get(detail.count_detail.freeze_record_id)
                if freeze_record and freeze_record.status == 'frozen':
                    freeze_record.status = 'released'
                    freeze_record.released_time = datetime.utcnow()
                    freeze_record.released_reason = 'Variance rejected'
                    
                    # 恢复库存冻结数量
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


# ==================== 导入功能 ====================

@count_bp.route('/detail/<int:count_id>/import', methods=['GET', 'POST'])
@permission_required('inventory_manage')
@login_required
def import_counted(count_id):
    """导入实盘数量（Excel/CSV）"""
    count = InventoryCount.query.get_or_404(count_id)
    
    if request.method == 'POST':
        # 接收AJAX请求
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '未上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': '文件名为空'}), 400
        
        try:
            import openpyxl
            
            # 限制文件类型
            if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
                return jsonify({'success': False, 'message': '只支持 xlsx/xls/csv 格式'}), 400
            
            # 读取Excel/CSV
            import pandas as pd
            df = pd.read_excel(file) if file.filename.endswith(('.xlsx', '.xls')) else pd.read_csv(file)
            
            # 检查必需列
            if 'sku' not in df.columns or 'counted_qty' not in df.columns:
                return jsonify({'success': False, 'message': '文件必须包含 sku 和 counted_qty 列'}), 400
            
            success_count = 0
            error_rows = []
            
            for idx, row in df.iterrows():
                sku = str(row['sku']).strip()
                counted_qty = row['counted_qty']
                
                try:
                    counted_qty = int(counted_qty)
                    if counted_qty < 0:
                        raise ValueError('数量不能为负')
                except:
                    error_rows.append((idx + 2, f'SKU {sku}: 数量格式错误'))
                    continue
                
                # 根据SKU和库位查找明细（或模糊匹配Product）
                product = Product.query.filter_by(code=sku).first()
                if not product:
                    error_rows.append((idx + 2, f'SKU {sku}: 商品不存在'))
                    continue
                
                # 查找对应的盘点明细
                detail = InventoryCountDetail.query.filter_by(
                    count_id=count.id,
                    product_id=product.id
                ).first()
                
                if not detail:
                    error_rows.append((idx + 2, f'SKU {sku}: 不在当前盘点范围内'))
                    continue
                
                # 更新实盘数量
                detail.counted_quantity = counted_qty
                detail.counted_time = datetime.utcnow()
                detail.calculate_variance()
                success_count += 1
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'导入成功，更新 {success_count} 条记录',
                'error_count': len(error_rows),
                'errors': error_rows
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f'导入失败: {str(e)}'}), 500
    
    # GET 请求：显示导入页面
    return render_template('count/import.html', count=count)


@count_bp.route('/detail/<int:count_id>/export_template')
@permission_required('inventory_manage')
@login_required
def export_template(count_id):
    """导出盘点明细模板（Excel）"""
    count = InventoryCount.query.get_or_404(count_id)
    
    try:
        import pandas as pd
        from io import BytesIO
        
        details = count.details.all()
        
        # 构建DataFrame
        data = []
        for detail in details:
            data.append({
                'sku': detail.product.code,
                'product_name': detail.product.name,
                'spec': detail.product.spec,
                'location': detail.location.code,
                'snapshot_qty': detail.snapshot_quantity,
                'counted_qty': detail.counted_quantity or ''
            })
        
        df = pd.DataFrame(data)
        
        # 创建Excel写入器
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='盘点明细', index=False)
        
        output.seek(0)
        return output.getvalue(), 200, {
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'Content-Disposition': f'attachment; filename=count_{count.count_no}_template.xlsx'
        }
    except Exception as e:
        flash(f'导出失败: {str(e)}', 'danger')
        return redirect(url_for('count.detail', count_id=count_id))
