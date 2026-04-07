from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app.models.inventory import WarehouseLocation
from app import db

location_bp = Blueprint('location', __name__)


@location_bp.route('/list')
@login_required
def list():
    """库位列表"""
    if not current_user.has_permission('inventory_manage'):
        flash('无权限访问', 'danger')
        return redirect(url_for('product.list'))
    
    locations = WarehouseLocation.query.all()
    return render_template('location/list.html', locations=locations)


@location_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """添加库位"""
    if not current_user.has_permission('inventory_manage'):
        flash('无权限访问', 'danger')
        return redirect(url_for('product.list'))
    
    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        area = request.form.get('area')
        status = request.form.get('status') == '1'
        remark = request.form.get('remark')
        
        # 检查库位编码是否已存在
        existing_location = WarehouseLocation.query.filter_by(code=code).first()
        if existing_location:
            flash('库位编码已存在', 'danger')
            return redirect(url_for('location.add'))
        
        # 创建库位
        location = WarehouseLocation(
            code=code,
            name=name,
            area=area,
            status=status,
            remark=remark
        )
        
        db.session.add(location)
        db.session.commit()
        flash('库位添加成功', 'success')
        return redirect(url_for('location.list'))
    
    return render_template('location/add.html')


@location_bp.route('/edit/<int:location_id>', methods=['GET', 'POST'])
@login_required
def edit(location_id):
    """编辑库位"""
    if not current_user.has_permission('inventory_manage'):
        flash('无权限访问', 'danger')
        return redirect(url_for('product.list'))
    
    location = WarehouseLocation.query.get(location_id)
    if not location:
        flash('库位不存在', 'danger')
        return redirect(url_for('location.list'))
    
    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        area = request.form.get('area')
        status = request.form.get('status') == '1'
        remark = request.form.get('remark')
        
        # 检查库位编码是否已存在（排除当前库位）
        existing_location = WarehouseLocation.query.filter_by(code=code).filter(WarehouseLocation.id != location_id).first()
        if existing_location:
            flash('库位编码已存在', 'danger')
            return redirect(url_for('location.edit', location_id=location_id))
        
        # 更新库位信息
        location.code = code
        location.name = name
        location.area = area
        location.status = status
        location.remark = remark
        
        db.session.commit()
        flash('库位更新成功', 'success')
        return redirect(url_for('location.list'))
    
    return render_template('location/edit.html', location=location)


@location_bp.route('/delete/<int:location_id>')
@login_required
def delete(location_id):
    """删除库位"""
    if not current_user.has_permission('inventory_manage'):
        flash('无权限访问', 'danger')
        return redirect(url_for('product.list'))
    
    location = WarehouseLocation.query.get(location_id)
    if not location:
        flash('库位不存在', 'danger')
        return redirect(url_for('location.list'))
    
    # 检查是否有关联的库存
    if location.inventories.count() > 0:
        flash('该库位已有库存，无法删除', 'danger')
        return redirect(url_for('location.list'))
    
    db.session.delete(location)
    db.session.commit()
    flash('库位删除成功', 'success')
    return redirect(url_for('location.list'))