from flask import Blueprint, render_template, request, url_for, flash, redirect
from flask_login import login_required
from app import db
from app.models.product import Customer
from app.utils.auth import permission_required
from datetime import datetime

customer_bp = Blueprint('customer', __name__)


@customer_bp.route('/list')
@permission_required('inbound_manage')
@login_required
def list():
    keyword = request.args.get('keyword', '')
    status = request.args.get('status', '')
    
    query = Customer.query
    
    if keyword:
        query = query.filter(
            Customer.name.ilike(f'%{keyword}%') |
            Customer.code.ilike(f'%{keyword}%') |
            Customer.contact_person.ilike(f'%{keyword}%') |
            Customer.phone.ilike(f'%{keyword}%')
        )
    
    if status:
        if status == 'active':
            query = query.filter_by(status=True)
        elif status == 'inactive':
            query = query.filter_by(status=False)
    
    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(Customer.create_time.desc()).paginate(page=page, per_page=per_page)
    customers = pagination.items
    
    return render_template('customer/list.html',
                         customers=customers,
                         pagination=pagination,
                         keyword=keyword,
                         status=status)


@customer_bp.route('/add', methods=['GET', 'POST'])
@permission_required('inbound_manage')
@login_required
def add():
    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        contact_person = request.form.get('contact_person')
        phone = request.form.get('phone')
        email = request.form.get('email')
        address = request.form.get('address')
        status = request.form.get('status') == 'on'
        remark = request.form.get('remark', '')
        
        if not code or not name:
            flash('客户编号和名称不能为空', 'danger')
            return render_template('customer/edit.html', customer=None)
        
        code_exist = Customer.query.filter_by(code=code).first()
        if code_exist:
            flash('客户编号已存在', 'danger')
            return render_template('customer/edit.html', customer=None)
        
        customer = Customer(
            code=code,
            name=name,
            contact_person=contact_person,
            phone=phone,
            email=email,
            address=address,
            status=status,
            remark=remark
        )
        db.session.add(customer)
        db.session.commit()
        
        flash('客户添加成功', 'success')
        return redirect(url_for('customer.list'))
    
    return render_template('customer/edit.html', customer=None)


@customer_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@permission_required('inbound_manage')
@login_required
def edit(id):
    customer = Customer.query.get_or_404(id)
    
    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        contact_person = request.form.get('contact_person')
        phone = request.form.get('phone')
        email = request.form.get('email')
        address = request.form.get('address')
        status = request.form.get('status') == 'on'
        remark = request.form.get('remark', '')
        
        if not code or not name:
            flash('客户编号和名称不能为空', 'danger')
            return render_template('customer/edit.html', customer=customer)
        
        code_exist = Customer.query.filter_by(code=code).first()
        if code_exist and code_exist.id != customer.id:
            flash('客户编号已存在', 'danger')
            return render_template('customer/edit.html', customer=customer)
        
        customer.code = code
        customer.name = name
        customer.contact_person = contact_person
        customer.phone = phone
        customer.email = email
        customer.address = address
        customer.status = status
        customer.remark = remark
        
        db.session.commit()
        flash('客户信息更新成功', 'success')
        return redirect(url_for('customer.list'))
    
    return render_template('customer/edit.html', customer=customer)


@customer_bp.route('/delete/<int:id>')
@permission_required('inbound_manage')
@login_required
def delete(id):
    customer = Customer.query.get_or_404(id)
    
    db.session.delete(customer)
    db.session.commit()
    flash('客户删除成功', 'success')
    return redirect(url_for('customer.list'))


@customer_bp.route('/toggle_status/<int:id>')
@permission_required('inbound_manage')
@login_required
def toggle_status(id):
    customer = Customer.query.get_or_404(id)
    customer.status = not customer.status
    db.session.commit()
    
    status_text = '启用' if customer.status else '停用'
    flash(f'客户已{status_text}', 'success')
    return redirect(url_for('customer.list'))