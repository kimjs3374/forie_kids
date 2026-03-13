from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class Admin(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    last_login_at = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Setting(db.Model):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True, default=1)
    notice_text = db.Column(db.Text, nullable=False, default="현재 공지사항이 없습니다.")
    policy_json = db.Column(db.JSON, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReservationMonth(TimestampMixin, db.Model):
    __tablename__ = "reservation_months"

    id = db.Column(db.Integer, primary_key=True)
    target_month = db.Column(db.String(7), unique=True, nullable=False)
    title = db.Column(db.String(100), nullable=True)
    open_at = db.Column(db.DateTime, nullable=False)
    close_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="DRAFT")
    max_reservations_per_household = db.Column(db.Integer, nullable=True, default=1)

    slots = db.relationship("ReservationSlot", backref="month", lazy=True)
    reservations = db.relationship("Reservation", backref="month", lazy=True)


class ReservationSlot(TimestampMixin, db.Model):
    __tablename__ = "reservation_slots"

    id = db.Column(db.Integer, primary_key=True)
    month_id = db.Column(db.Integer, db.ForeignKey("reservation_months.id"), nullable=False)
    play_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="ACTIVE")

    reservations = db.relationship("Reservation", backref="slot", lazy=True)

    @property
    def remaining_capacity(self):
        reserved_count = sum(1 for reservation in self.reservations if reservation.status == "RESERVED")
        return max(self.capacity - reserved_count, 0)


class Reservation(TimestampMixin, db.Model):
    __tablename__ = "reservations"

    id = db.Column(db.Integer, primary_key=True)
    month_id = db.Column(db.Integer, db.ForeignKey("reservation_months.id"), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey("reservation_slots.id"), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    apt_unit = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    children_count = db.Column(db.Integer, nullable=False)
    consent_agreed = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default="RESERVED")


def ensure_default_data(app):
    with app.app_context():
        if not Setting.query.get(1):
            db.session.add(Setting(id=1))

        admin_username = app.config["ADMIN_USERNAME"]
        admin_password = app.config["ADMIN_PASSWORD"]
        admin = Admin.query.filter_by(username=admin_username).first()
        if not admin:
            admin = Admin(username=admin_username)
            admin.set_password(admin_password)
            db.session.add(admin)

        db.session.commit()