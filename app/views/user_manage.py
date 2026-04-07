from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app.models.user import User, Role
from app import db

user_bp = Blueprint('user', __name__)


@user_bp.route('/list')
@login_required
def list():
    """用户列表"""
    if not current_user.has_permission('user_manage'):
        flash('无权限访问', 'danger')
        return redirect(url_for('product.list'))
    
    users = User.query.all()
    return render_template('user/list.html', users=users)


@user_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """添加用户"""
    if not current_user.has_permission('user_manage'):
        flash('无权限访问', 'danger')
        return redirect(url_for('product.list'))
    
    roles = Role.query.all()
    
    if request.method == 'POST':
        username = request.form.get('username')
        real_name = request.form.get('real_name')
        password = request.form.get('password')
        phone = request.form.get('phone')
        email = request.form.get('email')
        role_id = request.form.get('role_id')
        
        # 检查用户名是否已存在
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('用户名已存在', 'danger')
            return redirect(url_for('user.add'))
        
        # 创建用户
        user = User(
            username=username,
            real_name=real_name,
            phone=phone,
            email=email
        )
        user.set_password(password)
        
        # 分配角色
        if role_id:
            role = Role.query.get(int(role_id))
            if role:
                user.roles.append(role)
        
        db.session.add(user)
        db.session.commit()
        flash('用户添加成功', 'success')
        return redirect(url_for('user.list'))
    
    return render_template('user/add.html', roles=roles)


@user_bp.route('/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit(user_id):
    """编辑用户"""
    if not current_user.has_permission('user_manage'):
        flash('无权限访问', 'danger')
        return redirect(url_for('product.list'))
    
    user = User.query.get(user_id)
    if not user:
        flash('用户不存在', 'danger')
        return redirect(url_for('user.list'))
    
    roles = Role.query.all()
    
    if request.method == 'POST':
        real_name = request.form.get('real_name')
        password = request.form.get('password')
        phone = request.form.get('phone')
        email = request.form.get('email')
        role_id = request.form.get('role_id')
        
        # 更新用户信息
        user.real_name = real_name
        user.phone = phone
        user.email = email
        
        # 如果提供了密码，则更新密码
        if password:
            user.set_password(password)
        
        # 更新角色
        user.roles = []
        if role_id:
            role = Role.query.get(int(role_id))
            if role:
                user.roles.append(role)
        
        db.session.commit()
        flash('用户更新成功', 'success')
        return redirect(url_for('user.list'))
    
    # 获取用户当前角色ID
    user_role_id = user.roles[0].id if user.roles else ''
    return render_template('user/edit.html', user=user, roles=roles, user_role_id=user_role_id)


@user_bp.route('/delete/<int:user_id>')
@login_required
def delete(user_id):
    """删除用户"""
    if not current_user.has_permission('user_manage'):
        flash('无权限访问', 'danger')
        return redirect(url_for('product.list'))
    
    user = User.query.get(user_id)
    if not user:
        flash('用户不存在', 'danger')
        return redirect(url_for('user.list'))
    
    # 不能删除自己
    if user.id == current_user.id:
        flash('不能删除当前登录用户', 'danger')
        return redirect(url_for('user.list'))
    
    db.session.delete(user)
    db.session.commit()
    flash('用户删除成功', 'success')
    return redirect(url_for('user.list'))


@user_bp.route('/role/list')
@login_required
def role_list():
    """角色列表"""
    if not current_user.has_permission('user_manage'):
        flash('无权限访问', 'danger')
        return redirect(url_for('product.list'))
    
    roles = Role.query.all()
    return render_template('user/role_list.html', roles=roles)


@user_bp.route('/role/add', methods=['GET', 'POST'])
@login_required
def role_add():
    """添加角色"""
    if not current_user.has_permission('user_manage'):
        flash('无权限访问', 'danger')
        return redirect(url_for('product.list'))
    
    from app.models.user import Permission
    permissions = Permission.PERMISSIONS
    
    if request.method == 'POST':
        name = request.form.get('name')
        desc = request.form.get('desc')
        perm_names = request.form.getlist('permissions')
        
        # 检查角色名是否已存在
        existing_role = Role.query.filter_by(name=name).first()
        if existing_role:
            flash('角色名已存在', 'danger')
            return redirect(url_for('user.role_add'))
        
        # 创建角色
        role = Role(name=name, desc=desc)
        
        # 分配权限
        for perm_name in perm_names:
            permission = Permission.query.filter_by(name=perm_name).first()
            if not permission:
                perm_desc = Permission.PERMISSIONS.get(perm_name, perm_name)
                permission = Permission(name=perm_name, desc=perm_desc)
                db.session.add(permission)
            role.permissions.append(permission)
        
        db.session.add(role)
        db.session.commit()
        flash('角色添加成功', 'success')
        return redirect(url_for('user.role_list'))
    
    return render_template('user/role_add.html', permissions=permissions)


@user_bp.route('/role/edit/<int:role_id>', methods=['GET', 'POST'])
@login_required
def role_edit(role_id):
    """编辑角色"""
    if not current_user.has_permission('user_manage'):
        flash('无权限访问', 'danger')
        return redirect(url_for('product.list'))
    
    role = Role.query.get(role_id)
    if not role:
        flash('角色不存在', 'danger')
        return redirect(url_for('user.role_list'))
    
    from app.models.user import Permission
    permissions = Permission.PERMISSIONS
    
    if request.method == 'POST':
        name = request.form.get('name')
        desc = request.form.get('desc')
        perm_names = request.form.getlist('permissions')
        
        # 检查角色名是否已存在（排除当前角色）
        existing_role = Role.query.filter_by(name=name).filter(Role.id != role_id).first()
        if existing_role:
            flash('角色名已存在', 'danger')
            return redirect(url_for('user.role_edit', role_id=role_id))
        
        # 更新角色信息
        role.name = name
        role.desc = desc
        
        # 更新权限
        role.permissions = []
        for perm_name in perm_names:
            permission = Permission.query.filter_by(name=perm_name).first()
            if not permission:
                perm_desc = Permission.PERMISSIONS.get(perm_name, perm_name)
                permission = Permission(name=perm_name, desc=perm_desc)
                db.session.add(permission)
            role.permissions.append(permission)
        
        db.session.commit()
        flash('角色更新成功', 'success')
        return redirect(url_for('user.role_list'))
    
    # 获取角色当前权限
    role_perms = [perm.name for perm in role.permissions]
    return render_template('user/role_edit.html', role=role, permissions=permissions, role_perms=role_perms)


@user_bp.route('/role/delete/<int:role_id>')
@login_required
def role_delete(role_id):
    """删除角色"""
    if not current_user.has_permission('user_manage'):
        flash('无权限访问', 'danger')
        return redirect(url_for('product.list'))
    
    role = Role.query.get(role_id)
    if not role:
        flash('角色不存在', 'danger')
        return redirect(url_for('user.role_list'))
    
    # 检查是否有用户使用该角色
    if len(role.users) > 0:
        flash('该角色正在被使用，无法删除', 'danger')
        return redirect(url_for('user.role_list'))
    
    db.session.delete(role)
    db.session.commit()
    flash('角色删除成功', 'success')
    return redirect(url_for('user.role_list'))


@user_bp.route('/permission/list')
@login_required
def permission_list():
    """权限列表"""
    if not current_user.has_permission('user_manage'):
        flash('无权限访问', 'danger')
        return redirect(url_for('product.list'))
    
    from app.models.user import Permission
    permissions = Permission.query.all()
    return render_template('user/permission_list.html', permissions=permissions)


@user_bp.route('/permission/add', methods=['GET', 'POST'])
@login_required
def permission_add():
    """添加权限"""
    if not current_user.has_permission('user_manage'):
        flash('无权限访问', 'danger')
        return redirect(url_for('product.list'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        desc = request.form.get('desc')
        
        # 检查权限名是否已存在
        existing_perm = Permission.query.filter_by(name=name).first()
        if existing_perm:
            flash('权限名已存在', 'danger')
            return redirect(url_for('user.permission_add'))
        
        # 创建权限
        permission = Permission(name=name, desc=desc)
        db.session.add(permission)
        db.session.commit()
        flash('权限添加成功', 'success')
        return redirect(url_for('user.permission_list'))
    
    return render_template('user/permission_add.html')


@user_bp.route('/permission/edit/<int:perm_id>', methods=['GET', 'POST'])
@login_required
def permission_edit(perm_id):
    """编辑权限"""
    if not current_user.has_permission('user_manage'):
        flash('无权限访问', 'danger')
        return redirect(url_for('product.list'))
    
    from app.models.user import Permission
    permission = Permission.query.get(perm_id)
    if not permission:
        flash('权限不存在', 'danger')
        return redirect(url_for('user.permission_list'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        desc = request.form.get('desc')
        
        # 检查权限名是否已存在（排除当前权限）
        existing_perm = Permission.query.filter_by(name=name).filter(Permission.id != perm_id).first()
        if existing_perm:
            flash('权限名已存在', 'danger')
            return redirect(url_for('user.permission_edit', perm_id=perm_id))
        
        # 更新权限信息
        permission.name = name
        permission.desc = desc
        db.session.commit()
        flash('权限更新成功', 'success')
        return redirect(url_for('user.permission_list'))
    
    return render_template('user/permission_edit.html', permission=permission)


@user_bp.route('/permission/delete/<int:perm_id>')
@login_required
def permission_delete(perm_id):
    """删除权限"""
    if not current_user.has_permission('user_manage'):
        flash('无权限访问', 'danger')
        return redirect(url_for('product.list'))
    
    from app.models.user import Permission
    permission = Permission.query.get(perm_id)
    if not permission:
        flash('权限不存在', 'danger')
        return redirect(url_for('user.permission_list'))
    
    # 检查是否有角色使用该权限
    if len(permission.roles) > 0:
        flash('该权限正在被角色使用，无法删除', 'danger')
        return redirect(url_for('user.permission_list'))
    
    db.session.delete(permission)
    db.session.commit()
    flash('权限删除成功', 'success')
    return redirect(url_for('user.permission_list'))