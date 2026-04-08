from flask import Blueprint, render_template, request, url_for, flash, redirect
from flask_login import login_required
from app import db
from app.models.product import Customer
from app.utils.auth import permission_required

customer_bp = Blueprint('customer', __name__)


# 客户列表
@customer_bp.route('/list')
@permission_required('information_manage')
@login_required
def list():
    # 多条件查询
    keyword = request.args.get('keyword', '')       # 若查询为None返回''

    query = Customer.query       # 创建一个查询对象
    if keyword:     # 关键字搜索
        query = query.filter(Customer.name.ilike(f'%{keyword}%') | 
                           Customer.contact_person.ilike(f'%{keyword}%') |
                           Customer.phone.ilike(f'%{keyword}%'))

    # 分页
    page = request.args.get('page', 1, type=int)  #  默认值为1
    per_page = 10
    pagination = query.order_by(Customer.create_time.desc()).paginate(page=page, per_page=per_page)
    customers = pagination.items

    return render_template('customer/list.html',
                           customers=customers,             # 当前页的客户数据列表
                           pagination=pagination,         # 分页信息(包含总页数、当前页等)
                           keyword=keyword               # 搜索关键词
    )


# 添加/编辑客户
@customer_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@permission_required('information_manage')
@login_required
def edit(id=0):
    customer = Customer.query.get_or_404(id) if id else Customer()
    # 如果id存在，通过get_or_404(id)获取对应客户实例
    # 如果id不存在则创建一个新的Customer实例

    if request.method == 'POST':
        name = request.form.get('name')
        contact_person = request.form.get('contact_person')
        phone = request.form.get('phone')
        address = request.form.get('address')
        email = request.form.get('email')

        # 检查客户名称唯一性(编辑时排除自身)
        name_exist = Customer.query.filter_by(name=name).first()
        if name_exist and name_exist.id != customer.id:
            flash('客户名称已存在', 'danger')
            return render_template('customer/edit.html',
                                   customer=customer
            )

        # 创建或修改Customer实例
        customer.name = name
        customer.contact_person = contact_person
        customer.phone = phone
        customer.address = address
        customer.email = email

        if not id:     # 如果id不存在则创建一个新的Customer实例
            db.session.add(customer)
        db.session.commit()

        flash('保存成功', 'success')
        return redirect(url_for('customer.list'))

    return render_template('customer/edit.html',
                           customer=customer
    )


@customer_bp.route('/delete/<int:id>')
@permission_required('information_manage')
@login_required
def delete(id):
    customer = Customer.query.get_or_404(id)
    db.session.delete(customer)
    db.session.commit()
    flash('删除成功', 'success')
    return redirect(url_for('customer.list'))