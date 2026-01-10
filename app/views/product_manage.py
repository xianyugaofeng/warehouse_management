from flask import Blueprint, render_template, request, url_for, flash, redirect
from flask_login import login_required
from app import db
from app.models.product import Product, Category, Supplier
from app.utils.auth import permission_required

product_bp = Blueprint('product', __name__)


# 商品列表
@product_bp.route('/list')               # 路由装饰器在最下面：路由可能不工作，或者认证检查不生效
@permission_required('product_manage')
@login_required
def list():
    # 多条件查询
    keyword = request.args.get('keyword', '')       # 若查询为None返回''
    category_id = request.args.get('category_id', '')
    supplier_id = request.args.get('supplier_id', '')

    query = Product.query       # 创建一个查询对象，相当于SELECT * FROM product 获取所有产品\
                                # 查询对象是惰性的，不会立即执行数据库查询
    if keyword:     # 关键字搜索
        query = query.filter(Product.name.ilike(f'%{keyword}%') | Product.code.ilike(f'%{keyword}%'))
        # ilike表示模糊匹配 不区分大小写的查询
        # 自动参数化查询，防止SQL注入
    if category_id:   # 按分类筛选
        query = query.filter_by(category_id=category_id)
    if supplier_id:   # 按供应商筛选
        query = query.filter_by(supplier_id=supplier_id)
    """每次调用这些方法都会返回一个修改后的查询对象(链式调用)"""

    # 分页
    page = request.args.get('page', 1, type=int)  #  默认值为1
    per_page = 10
    pagination = query.order_by(Product.update_time.desc()).paginate(page=page, per_page=per_page)
    products = pagination.items

    # 下拉框数据
    categories = Category.query.all()     # 获取分类数据
    suppliers = Supplier.query.all()       # 获取供应商数据

    return render_template('product/list.html',
                           products=products,             # 当前页的产品数据列表
                           pagination=pagination,         # 分页信息(包含总页数、当前页等)
                           keyword=keyword,               # 搜索关键词
                           category_id=category_id,       # 当前选中分类id(回显筛选状态)
                           categories=categories,         # 用于生成下拉选项
                           suppliers=suppliers
    )


# 添加/编辑商品
@product_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@permission_required('product_manage')
@login_required
def edit(id=0):
    product = Product.query.get_or_404(id) if id else Product()
    # 如果id存在，通过get_or_404(id)获取对应产品实例
    # 如果id不存在则创建一个新的Product实例
    categories = Category.query.all()
    suppliers = Supplier.query.all()

    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        spec = request.form.get('spec')
        unit = request.form.get('unit')
        category_id = request.form.get('category_id')
        supplier_id = request.form.get('supplier_id')
        warning_stock = request.form.get('warning_stock', 10, type=int)
        remark = request.form.get('remark')

        # 检查商品编码唯一性(编辑时排除自身)
        code_exist = Product.query.filter_by(code=code).first()
        if code_exist and code_exist.id != product.id:
            flash('商品编码已存在', 'danger')
            return render_template('product/edit.html',
                                   product=product,
                                   categories=categories,
                                   suppliers=suppliers
            )

        # 创建或修改Product实例
        product.code = code
        product.name = name
        product.spec = spec
        product.unit = unit
        product.category_id = category_id
        product.supplier_id = supplier_id
        product.warning_stock = warning_stock
        product.remark = remark

        if not id:     # 如果id不存在则创建一个新的Product实例
            db.session.add(product)
        db.session.commit()

        flash('保存成功', 'success')
        return redirect(url_for('product.list'))

    return render_template('product/edit.html',
                           product=product,
                           categories=categories,
                           suppliers=suppliers
    )

@product_bp.route('/delete/<int:id>')
@permission_required('product_manage')
@login_required
def delete(id):
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash('删除成功', 'success')
    return redirect(url_for('product.list'))
