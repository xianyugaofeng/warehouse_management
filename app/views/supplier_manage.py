from flask import Blueprint, render_template, request, url_for, flash, redirect
from flask_login import login_required
from app import db
from app.models.product import Supplier
from app.utils.auth import permission_required

supplier_bp = Blueprint('supplier', __name__)


# 供应商列表
@supplier_bp.route('/list')
@permission_required('product_manage')
@login_required
def list():
    # 多条件查询
    keyword = request.args.get('keyword', '')       # 若查询为None返回''

    query = Supplier.query       # 创建一个查询对象
    if keyword:     # 关键字搜索
        query = query.filter(Supplier.name.ilike(f'%{keyword}%') | 
                           Supplier.contact_person.ilike(f'%{keyword}%') |
                           Supplier.phone.ilike(f'%{keyword}%'))

    # 分页
    page = request.args.get('page', 1, type=int)  #  默认值为1
    per_page = 10
    pagination = query.order_by(Supplier.create_time.desc()).paginate(page=page, per_page=per_page)
    suppliers = pagination.items

    return render_template('supplier/list.html',
                           suppliers=suppliers,             # 当前页的供应商数据列表
                           pagination=pagination,         # 分页信息(包含总页数、当前页等)
                           keyword=keyword               # 搜索关键词
    )


# 添加/编辑供应商
@supplier_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@permission_required('product_manage')
@login_required
def edit(id=0):
    supplier = Supplier.query.get_or_404(id) if id else Supplier()
    # 如果id存在，通过get_or_404(id)获取对应供应商实例
    # 如果id不存在则创建一个新的Supplier实例

    if request.method == 'POST':
        name = request.form.get('name')
        contact_person = request.form.get('contact_person')
        phone = request.form.get('phone')
        address = request.form.get('address')
        email = request.form.get('email')

        # 检查供应商名称唯一性(编辑时排除自身)
        name_exist = Supplier.query.filter_by(name=name).first()
        if name_exist and name_exist.id != supplier.id:
            flash('供应商名称已存在', 'danger')
            return render_template('supplier/edit.html',
                                   supplier=supplier
            )

        # 创建或修改Supplier实例
        supplier.name = name
        supplier.contact_person = contact_person
        supplier.phone = phone
        supplier.address = address
        supplier.email = email

        if not id:     # 如果id不存在则创建一个新的Supplier实例
            db.session.add(supplier)
        db.session.commit()

        flash('保存成功', 'success')
        return redirect(url_for('supplier.list'))

    return render_template('supplier/edit.html',
                           supplier=supplier
    )


@supplier_bp.route('/delete/<int:id>')
@permission_required('product_manage')
@login_required
def delete(id):
    supplier = Supplier.query.get_or_404(id)
    db.session.delete(supplier)
    db.session.commit()
    flash('删除成功', 'success')
    return redirect(url_for('supplier.list'))