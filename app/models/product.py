from datetime import datetime
from app import db


class Category(db.Model):    # 产品分类
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)  # 分类名称
    desc = db.Column(db.String(256))  # 分类描述
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    products = db.relationship('Product', backref='category', lazy='dynamic')  # 关联商品
    # 通过category.products获取属于该分类的全部商品(动态加载)
    # 通过product.category获取该商品属于的所有分类(立即加载)

    def __repr__(self):
        return f'<Category {self.name}>'


class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)   # 供应商名称
    contact_preson = db.Column(db.String(32))   # 联系人
    phone = db.Column(db.String(16))   # 联系电话
    address = db.Column(db.String(256))   # 地址
    email = db.Column(db.String(64))  # 邮箱
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    products = db.relationship('Product', backref='supplier', lazy='dynamic')  # 关联商品
    # 通过supplier.products获取属于该供应商的全部商品（动态加载）
    # 通过product.supplier获取该商品属于的所有供应商（立即加载）

    def __repr__(self):
        return f'<Supplier {self.name}>'


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False)   # 商品编码（唯一）
    name = db.Column(db.String(64), nullable=False)   # 商品名称
    spec = db.Column(db.String(64))  # 规格型号
    unit = db.Column(db.String(16))  # 单位（个/箱/kg）
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))  # 关联分类
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))   # 关联供应商
    warning_stock = db.Column(db.Integer, default=10)   # 库存预警阈值
    remark = db.Column(db.String(256))  # 备注
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Product {self.name}({self.code})>'

