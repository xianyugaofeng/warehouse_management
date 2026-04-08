from flask import Blueprint, render_template, request, url_for, flash, redirect, jsonify
from flask_login import login_required
from app import db
from app.models.product import Product, Category, ProductParamKey, CategoryParam, ProductParamValue
from app.utils.auth import permission_required

product_bp = Blueprint('product', __name__)


# 商品列表
@product_bp.route('/list')               # 路由装饰器在最下面：路由可能不工作，或者认证检查不生效
@permission_required('information_manage')
@login_required
def list():
    # 多条件查询
    keyword = request.args.get('keyword', '')       # 若查询为None返回''
    category_id = request.args.get('category_id', '')
    query = Product.query       # 创建一个查询对象，相当于SELECT * FROM product 获取所有产品\
                                # 查询对象是惰性的，不会立即执行数据库查询
    if keyword:     # 关键字搜索
        query = query.filter(Product.name.ilike(f'%{keyword}%') | Product.code.ilike(f'%{keyword}%'))
        # ilike表示模糊匹配 不区分大小写的查询
        # 自动参数化查询，防止SQL注入
    if category_id:   # 按分类筛选
        query = query.filter_by(category_id=category_id)
    """每次调用这些方法都会返回一个修改后的查询对象(链式调用)"""

    # 分页
    page = request.args.get('page', 1, type=int)  #  默认值为1
    per_page = 10
    pagination = query.order_by(Product.update_time.desc()).paginate(page=page, per_page=per_page)
    products = pagination.items

    # 下拉框数据
    categories = Category.query.all()     # 获取分类数据

    return render_template('product/list.html',
                           products=products,             # 当前页的产品数据列表
                           pagination=pagination,         # 分页信息(包含总页数、当前页等)
                           keyword=keyword,               # 搜索关键词
                           category_id=category_id,       # 当前选中分类id(回显筛选状态)
                           categories=categories         # 用于生成下拉选项
    )


# 添加/编辑商品
@product_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@permission_required('information_manage')
@login_required
def edit(id=0):
    product = Product.query.get_or_404(id) if id else Product()
    # 如果id存在，通过get_or_404(id)获取对应产品实例
    # 如果id不存在则创建一个新的Product实例
    categories = Category.query.all()

    # 加载商品参数
    category_params = []
    product_params = {}
    if product.category_id:
        # 获取当前分类的参数
        category_params = CategoryParam.query.filter_by(category_id=product.category_id).order_by(CategoryParam.sort_order).all()
        # 获取商品的参数值
        for param in product.params:
            product_params[param.param_key_id] = param.value
    # 新建商品时，默认不显示参数，需要先选择分类

    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        unit = request.form.get('unit')
        category_id = request.form.get('category_id')
        warning_stock = request.form.get('warning_stock', 10, type=int)
        remark = request.form.get('remark')

        # 检查商品编码唯一性(编辑时排除自身)
        code_exist = Product.query.filter_by(code=code).first()
        if code_exist and code_exist.id != product.id:
            flash('商品编码已存在', 'danger')
            return render_template('product/edit.html',
                               product=product,
                               categories=categories,
                               category_params=category_params,
                               product_params=product_params
        )

        # 创建或修改Product实例
        product.code = code
        product.name = name
        product.unit = unit
        product.category_id = category_id
        product.warning_stock = warning_stock
        product.remark = remark

        if not id:     # 如果id不存在则创建一个新的Product实例
            db.session.add(product)
            db.session.flush()  # 刷新以获取product.id

        # 保存商品参数
        # 删除旧参数
        ProductParamValue.query.filter_by(product_id=product.id).delete()
        # 添加新参数
        if category_id:
            category_params = CategoryParam.query.filter_by(category_id=category_id).all()
            for category_param in category_params:
                param_value = request.form.get(f'param_{category_param.param_key_id}')
                if param_value:
                    new_param = ProductParamValue(
                        product_id=product.id,
                        param_key_id=category_param.param_key_id,
                        value=param_value
                    )
                    db.session.add(new_param)

        db.session.commit()

        flash('保存成功', 'success')
        return redirect(url_for('product.list'))

    return render_template('product/edit.html',
                           product=product,
                           categories=categories,
                           category_params=category_params,
                           product_params=product_params
    )

@product_bp.route('/delete/<int:id>')
@permission_required('information_manage')
@login_required
def delete(id):
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash('删除成功', 'success')
    return redirect(url_for('product.list'))

# 获取分类参数
@product_bp.route('/get_category_params')
@permission_required('information_manage')
@login_required
def get_category_params():
    category_id = request.args.get('category_id', type=int)
    if not category_id:
        return jsonify({'params': []})
    
    # 获取分类的参数
    category_params = CategoryParam.query.filter_by(category_id=category_id).order_by(CategoryParam.sort_order).all()
    params = []
    for cp in category_params:
        params.append({
            'id': cp.param_key.id,
            'name': cp.param_key.name
        })
    
    return jsonify({'params': params})
