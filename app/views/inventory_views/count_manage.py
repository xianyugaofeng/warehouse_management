from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models.count import InventoryCount, InventoryCountDetail
from app.models.inventory import Inventory, WarehouseLocation
from app.models.product import Product, Category
from app.utils.auth import permission_required
from app.utils.helpers import generate_count_no
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
    
    if count.status == 'completed':
        return jsonify({'success': False, 'message': '已完成的盘点单无法修改'}), 400
    
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
        if gains:
            from app.views.inventory_views.freeze_manage import _create_variance_document
            _create_variance_document(count, 'gain', gains)
        
        # 生成盘亏单
        if losses:
            from app.views.inventory_views.freeze_manage import _create_variance_document
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




