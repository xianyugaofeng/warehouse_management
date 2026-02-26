from flask import Blueprint, render_template, request, url_for, flash, redirect
from flask_login import login_required
from app import db
from app.models.product import Supplier
from app.utils.auth import permission_required

supplier_bp = Blueprint('supplier', __name__)

#供应商列表
@supplier_bp.route('/list')
@permission_required('product_manage')
@login_required
def list():
    #多条件查询
    keyword = request.args.get('keyword', '')

    query = Supplier.query

    if keyword:
        query = query.filter(Supplier.name.ilike(f'%{keyword}%')) | 
                             Supplier.contact_person.ilike(f'%{keyword}%') | 
                             Supplier.phone.ilike(f'%{keyword}%')
    
    # 分页
    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(Supplier.create_time.desc()).paginate(page=page, per_page=per_page)
    suppliers = pagination.items

    return render_template('supploer/list.html',
                            supppliers=suppliers,
                            papgination=pagination,
                            keyword=keyword
    )

# 添加/编辑供应商
@supplier_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@permission_required('product_manage')
@login_required
def edit(id=0):
    supplier = Supplier.query.get_or_404(id) if id else Supplier()

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
                                    supplier=supplier)
        
        # 创建或修改Supplier实例
        supplier.name = name
        supplier.contact_person = contact_person
        supplier.phone = phone
        supplier.address = address
        supplier.email = email

        if not id:
            db.session.add(supplier)
        db.session.commit()

        flash('保存成功', 'success')
        return redirect(url_for('supplier.list'))
    
    return render_template('supplier/edit.html',
                            supplier=supplier)

# 删除供应商
@supplier_bp.route('/delete/<int:id>')
@permission_required('product_manage')
@login_required
def delete(id):
    supplier = Supplier.query.get_or_404(id)
    # 检查是否有关联的商品
    if supplier.products.count() > 0:
        flash('该供应商下有关联商品，无法删除', 'danger')
        return redirect(url_for('supplier.list'))
    
    db.session.delete(supplier)
    db.session.commit()
    flash('删除成功', 'success')
    return redirect(url_for('supplier.list'))
