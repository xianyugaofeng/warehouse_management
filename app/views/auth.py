from flask import Blueprint, request, url_for, redirect, flash, render_template
from flask_login import login_user, logout_user, login_required
from app import db
from app.models.user import User
from app.utils.helpers import generate_inbound_no

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'

        user = User.query.filter_by(username=username, is_active=True).first()