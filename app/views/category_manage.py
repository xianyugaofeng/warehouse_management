from flask import Blueprint, render_template, request, url_for, flash, redirect, jsonify, current_app
from flask_login import login_required
from app import db
from app.models.product import Category, ProductParamKey, CategoryParam
from app.utils.auth import permission_required

category_bp = Blueprint('category', __name__)


# 分类列表
@category_bp.route('/list')
@permission_required('information_manage')
@login_required
def category_list():
    keyword = request.args.get('keyword', '')
    query = Category.query
    
    if keyword:
        query = query.filter(Category.name.ilike(f'%{keyword}%'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(Category.create_time.desc()).paginate(page=page, per_page=per_page)
    categories = pagination.items
    
    return render_template('category/list.html',
                           categories=categories,
                           pagination=pagination,
                           keyword=keyword)


# 添加/编辑分类
@category_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@permission_required('information_manage')
@login_required
def edit(id=0):
    category = Category.query.get_or_404(id) if id else Category()
    
    # 获取所有参数键
    param_keys = ProductParamKey.query.order_by(ProductParamKey.name).all()
    
    # 获取当前分类的参数
    category_params = []
    if category.id:
        category_params = CategoryParam.query.filter_by(category_id=category.id).order_by(CategoryParam.sort_order).all()
    
    if request.method == 'POST':
        name = request.form.get('name')
        desc = request.form.get('desc')
        param_ids = request.form.getlist('param_ids[]')
        param_names = request.form.getlist('param_names[]')
        
        # 调试信息
        print(f'=== 分类编辑调试信息 ===')
        print(f'分类ID: {id}')
        print(f'分类名称: {name}')
        print(f'参数ID列表: {param_ids}')
        print(f'参数名称列表: {param_names}')
        print(f'参数ID数量: {len(param_ids)}')
        print(f'参数名称数量: {len(param_names)}')
        print(f'表单所有数据: {request.form}')
        print(f'表单keys: {list(request.form.keys())}')
        
        # 检查分类名称唯一性(编辑时排除自身)
        name_exist = Category.query.filter_by(name=name).first()
        if name_exist and name_exist.id != category.id:
            flash('分类名称已存在', 'danger')
            return render_template('category/edit.html',
                                   category=category,
                                   param_keys=param_keys,
                                   category_params=category_params)
        
        # 创建或修改分类
        category.name = name
        category.desc = desc
        
        if not id:
            db.session.add(category)
            db.session.flush()
        
        # 保存分类参数
        # 删除旧参数
        CategoryParam.query.filter_by(category_id=category.id).delete()
        
        # 添加新参数
        for idx, (param_id, param_name) in enumerate(zip(param_ids, param_names)):
            if param_id:
                # 从下拉框选择的参数
                category_param = CategoryParam(
                    category_id=category.id,
                    param_key_id=int(param_id),
                    sort_order=idx
                )
                db.session.add(category_param)
            elif param_name and param_name.strip():
                # 手动输入的参数
                # 检查参数名称是否已存在
                param_key = ProductParamKey.query.filter_by(name=param_name.strip()).first()
                if not param_key:
                    # 创建新的参数键
                    param_key = ProductParamKey(name=param_name.strip())
                    db.session.add(param_key)
                    db.session.flush()
                
                # 创建分类参数关联
                category_param = CategoryParam(
                    category_id=category.id,
                    param_key_id=param_key.id,
                    sort_order=idx
                )
                db.session.add(category_param)
        
        try:
            db.session.commit()
            
            # 验证参数是否保存成功
            saved_params = CategoryParam.query.filter_by(category_id=category.id).all()
            current_app.logger.info(f'分类保存成功: ID={category.id}, 名称={category.name}')
            current_app.logger.info(f'保存的参数数量: {len(saved_params)}')
            current_app.logger.info(f'参数详情: {[(p.param_key.name, p.sort_order) for p in saved_params]}')
            
            flash(f'保存成功，共保存{len(saved_params)}个参数', 'success')
            
            # 如果是编辑模式，重定向到详情页面
            if id:
                return redirect(url_for('category.detail', id=category.id))
            else:
                return redirect(url_for('category.list'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'分类保存失败: {str(e)}')
            flash(f'保存失败：{str(e)}', 'danger')
            # 重新获取分类参数
            category_params = CategoryParam.query.filter_by(category_id=category.id).order_by(CategoryParam.sort_order).all()
            return render_template('category/edit.html',
                                   category=category,
                                   param_keys=param_keys,
                                   category_params=category_params)
    
    return render_template('category/edit.html',
                           category=category,
                           param_keys=param_keys,
                           category_params=category_params)


# 删除分类
@category_bp.route('/delete/<int:id>')
@permission_required('information_manage')
@login_required
def delete(id):
    category = Category.query.get_or_404(id)
    
    # 检查是否有商品使用该分类
    product_count = category.products.count()
    if product_count > 0:
        flash(f'该分类下有{product_count}个商品，无法删除', 'danger')
        return redirect(url_for('category.list'))
    
    db.session.delete(category)
    db.session.commit()
    flash('删除成功', 'success')
    return redirect(url_for('category.list'))


# 查看分类详情
@category_bp.route('/detail/<int:id>')
@permission_required('information_manage')
@login_required
def detail(id):
    category = Category.query.get_or_404(id)
    
    # 获取分类参数
    category_params = CategoryParam.query.filter_by(category_id=category.id).order_by(CategoryParam.sort_order).all()
    
    # 获取该分类下的商品
    products = category.products.limit(10).all()
    
    return render_template('category/detail.html',
                           category=category,
                           category_params=category_params,
                           products=products)