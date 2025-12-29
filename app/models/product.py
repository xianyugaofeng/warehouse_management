from datetime import datetime
from app import db


class Category(db.Model):    # 产品分类
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unqiue=True, nullable=False)  # 分类名称
    desc = db.Column(db.String(256))  # 分类描述
    create_time = db.Column(db.Datetime, default=datetime.utcnow)
    products = db.relationship('Product', backref='category', lazy='dynamic')  # 关联商品


