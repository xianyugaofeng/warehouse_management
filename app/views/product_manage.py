from flask import Blueprint, render_template, request, url_for, flash, redirect
from flask_login import login_required
from app import db
from app.models.product import Product,Category, Supplier
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
    pageination = query.order_by(Product.update_time.desc()).paginate(page=page, per_page=per_page)
    products = pageination.items

