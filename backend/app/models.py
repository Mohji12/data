from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class QuizExam(Base):
    __tablename__ = "quiz_exam"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    section_id = Column(String(255), nullable=False)  # comma-separated section IDs
    batch = Column(String(255))  # comma-separated subscriptions/batches
    timer_time = Column(Integer)  # minutes
    total_questions = Column(Integer)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    status = Column(String(1), nullable=False, default="1")
    is_display_result = Column(String(1), default="1")
    is_display_correct_answer = Column(String(1), default="0")


class QuizSection(Base):
    """Legacy table: id, name, display_order, status. Exams link sections via `quiz_exam.section_id` (CSV), not a column here."""

    __tablename__ = "quiz_section"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    display_order = Column(Integer, default=0)
    status = Column(String(1), nullable=False, default="1")


class MarkingType(Base):
    __tablename__ = "marking_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255))
    description = Column(Text)
    total_correct_answer = Column(Integer, default=0)
    total_correct_answer_mark = Column(Float, default=0.0)
    minimum_correct_answer = Column(Integer, default=0)
    minimum_correct_answer_mark = Column(Float, default=0.0)
    negative_mark = Column(Float, default=0.0)
    status = Column(String(1), nullable=False, default="1")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    section_id = Column(Integer, nullable=False)
    question = Column(Text, nullable=False)
    question_image = Column(String(255))
    option_a = Column(Text)
    option_b = Column(Text)
    option_c = Column(Text)
    option_d = Column(Text)
    option_e = Column(Text)
    answer = Column(String(50))
    answer_type = Column(String(5), nullable=False)  # R, C, MTF
    total_option = Column(Integer, default=0)
    marking_type_id = Column(Integer)
    marks = Column(Integer)
    negative_marks = Column(Integer)
    is_mandatory_question = Column(String(1))
    status = Column(String(1), nullable=False, default="1")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserExam(Base):
    __tablename__ = "user_exam"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    exam_id = Column(Integer, nullable=False)
    exam_question_id = Column(Text, nullable=True)  # comma-separated question IDs
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime)
    remaining_seconds = Column(Integer, nullable=True)
    is_paused = Column(String(1), default="0") # '0' for running, '1' for paused
    is_finish_exam = Column(String(1), default="0")
    marks = Column(Float, default=0.0)


class UserAnswer(Base):
    __tablename__ = "user_answer"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    exam_id = Column(Integer, nullable=False)
    user_exam_id = Column(Integer, nullable=True)
    question_id = Column(Integer, nullable=False)
    answer = Column(String(50))
    is_correct_answer = Column(String(1), default="0")
    is_attempt_question = Column(String(1), default="0")
    marks = Column(Float, default=0.0)
    negative_mark = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    registration_type = Column(String(255))
    subscription = Column(String(255))  # This is the batch name
    title = Column(String(50))
    name = Column(String(255))
    email = Column(String(255), nullable=False, unique=True)
    password = Column(String(255), nullable=False)
    contact_number = Column(String(50))
    hospital = Column(String(255))
    qualification = Column(String(255))
    speciality = Column(String(255))
    country_id = Column(Integer)
    state = Column(String(255))
    city = Column(String(255))
    pin_code = Column(String(20))
    document_file = Column(String(255))
    document_file_2 = Column(String(255), nullable=False, default="")
    document_file_status = Column(Integer, nullable=False, default=0)  # MySQL int (0/1/2); not VARCHAR
    package_id = Column(Integer)
    currency_name = Column(String(20))
    gross_amount = Column(Float, default=0.0)
    gst_percentage = Column(Float, default=0.0)
    gst_amount = Column(Float, default=0.0)
    total_amount = Column(Float, default=0.0)
    coupon_code = Column(String(100))
    payment_request_id = Column(String(255))
    payment_id = Column(String(255))
    payment_status = Column(String(50))
    payment_type = Column(String(50))
    payment_date = Column(DateTime)
    payment_details = Column(Text)
    payment_signature = Column(String(255))
    approve = Column(String(1))
    email_verify_token = Column(String(255))
    forgot_token = Column(String(255))
    verify = Column(String(10))  # MySQL ENUM('Yes','No')
    is_login = Column(String(1), nullable=False, default="0")
    login_token = Column(String(255), nullable=False, default="")
    password_hash = Column(String(255), nullable=False, default="")
    role = Column(String(50), nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Package(Base):
    __tablename__ = "package"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    subscription = Column(String(255))
    category_name = Column(String(255))
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    gross_amount = Column(Float, default=0.0)
    gst_percentage = Column(Float, default=0.0)
    gst_amount = Column(Float, default=0.0)
    total_amount = Column(Float, default=0.0)
    plan_type = Column(String(30), default="one_time")
    duration_months = Column(Integer)
    with_topup = Column(String(1))
    batch_start_date = Column(DateTime)
    discount_percentage = Column(Float, default=0.0)
    discounted_amount = Column(Float, default=0.0)
    discount_start_date = Column(DateTime)
    discount_end_date = Column(DateTime)
    status = Column(String(1), default="1")


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    batch_slug = Column(String(255), nullable=False)
    package_id = Column(Integer, nullable=False)
    duration_months = Column(Integer)
    start_at = Column(DateTime, nullable=False)
    end_at = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False, default="active")
    auto_renew = Column(String(1), nullable=False, default="0")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CouponMaster(Base):
    __tablename__ = "coupon_master"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(100), nullable=False, unique=True)
    status = Column(String(1), default="0")
    discount_amount = Column(Float, default=0.0)
    discount_percent = Column(Float, default=0.0)
    subscriptions = Column(String(255))
    assigned_email = Column(String(255), nullable=True)


class Country(Base):
    __tablename__ = "country"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    status = Column(String(1), default="1")


class UserPackagePayment(Base):
    __tablename__ = "user_package_payment"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    package_id = Column(Integer, nullable=False)
    subscription = Column(String(255))
    package_type = Column(String(100))
    currency_name = Column(String(20))
    payment_request_id = Column(String(255))
    payment_id = Column(String(255))
    payment_status = Column(String(50))
    payment_type = Column(String(50))
    payment_date = Column(DateTime)
    payment_signature = Column(String(255))
    payment_details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RegistrationPaymentTxn(Base):
    __tablename__ = "registration_payment_txn"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(255), nullable=False, unique=True)
    user_id = Column(Integer, nullable=False)
    batch_slug = Column(String(255), nullable=False)
    package_id = Column(Integer, nullable=False)
    amount = Column(Float, default=0.0)
    currency = Column(String(20), default="INR")
    gateway = Column(String(50), default="razorpay")
    gateway_order_id = Column(String(255))
    gateway_payment_id = Column(String(255))
    gateway_signature = Column(String(255))
    gateway_status = Column(String(50), default="created")
    coupon_code = Column(String(100))
    callback_payload = Column(Text)
    webhook_payload = Column(Text)
    is_finalized = Column(String(1), default="0")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Option(Base):
    __tablename__ = "options"

    id = Column(Integer, primary_key=True, autoincrement=True)
    option_name = Column(String(255), nullable=False, unique=True)
    option_value = Column(Text)


class FolderMaster(Base):
    __tablename__ = "folder_master"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    status = Column(String(1), nullable=False, default="1")
    batch = Column(String(255))
    display_order = Column(Integer, default=0)


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    image = Column(String(255))
    video_link = Column(Text)
    folder = Column(String(255))
    batch = Column(String(255))
    status = Column(String(1), nullable=False, default="1")
    upload_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VideoQuestion(Base):
    """Legacy `video_question` table: id, users_id, question, created_at (no video FK in production DB)."""

    __tablename__ = "video_question"

    id = Column(Integer, primary_key=True, autoincrement=True)
    users_id = Column(Integer, nullable=False)
    question = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Audit(Base):
    __tablename__ = "audit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    file_id = Column(Integer)
    file_type = Column(String(50))
    activity = Column(String(255))
    activity_details = Column(Text)
    activity_datetime = Column(DateTime, default=datetime.utcnow)


class Testimonial(Base):
    """Legacy `testimonial` table (PHP): text, display_order, status — no name/description columns."""

    __tablename__ = "testimonial"

    id = Column(Integer, primary_key=True, autoincrement=True)
    text = Column(Text)
    display_order = Column(Integer, default=0)
    status = Column(String(1), default="1")


class LoginActivity(Base):
    __tablename__ = "login_activity"

    id = Column(Integer, primary_key=True, autoincrement=True)
    users_id = Column(Integer, nullable=False)
    activity = Column(String(255))
    activity_datetime = Column(DateTime, default=datetime.utcnow)


class BatchMaster(Base):
    __tablename__ = "batch_master"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    display_order = Column(Integer, default=0)
    registration_fee_structure = Column(Text)
    description = Column(Text)
    video_url = Column(String(255))
    video_file = Column(String(255))
    brochure_file = Column(String(255))
    package_subscription = Column(String(255))
    status = Column(String(1), default="1")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmailTemplateMaster(Base):
    __tablename__ = "email_template_master"
    __table_args__ = (
        UniqueConstraint("batch_id", "template_type", name="uq_email_template_master_batch_type"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, nullable=False)
    template_type = Column(String(64), nullable=False)
    subject = Column(String(255), nullable=False)
    body_html = Column(Text, nullable=False)
    status = Column(String(1), default="1", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EventRegistration(Base):
    __tablename__ = "event_registration"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_slug = Column(String(128), nullable=False)
    registration_number = Column(String(32), nullable=False, unique=True)
    full_name = Column(String(255), nullable=False)
    designation = Column(String(255), nullable=False)
    category = Column(String(32), nullable=False)  # clinician | student
    specialty = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False)
    country_id = Column(Integer)
    country_name = Column(String(255))
    hospital = Column(String(255), nullable=False)
    city = Column(String(128), nullable=False)
    state = Column(String(128), nullable=False)
    council_state = Column(String(128), nullable=False)
    council_registration_number = Column(String(128), nullable=False)
    declaration_accepted = Column(String(1), nullable=False, default="1")
    payment_status = Column(String(32), default="Pending")
    amount_inr = Column(Float, default=0.0)
    payment_id = Column(String(255))
    payment_signature = Column(String(255))
    payment_type = Column(String(50))
    payment_date = Column(DateTime)
    payment_details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EventPaymentTxn(Base):
    __tablename__ = "event_payment_txn"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(255), nullable=False, unique=True)
    event_registration_id = Column(Integer, nullable=False)
    amount = Column(Float, default=0.0)
    currency = Column(String(20), default="INR")
    gateway = Column(String(50), default="razorpay")
    gateway_order_id = Column(String(255))
    gateway_payment_id = Column(String(255))
    gateway_signature = Column(String(255))
    gateway_status = Column(String(50), default="created")
    callback_payload = Column(Text)
    webhook_payload = Column(Text)
    is_finalized = Column(String(1), default="0")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WhatsAppWebhookEvent(Base):
    """Inbound WhatsApp Cloud API webhook events (messages, statuses, errors)."""

    __tablename__ = "whatsapp_webhook_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_kind = Column(String(64), nullable=False)
    field = Column(String(64))
    phone = Column(String(32))
    wa_message_id = Column(String(128))
    event_status = Column(String(64))
    user_id = Column(Integer)
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Admin(Base):
    __tablename__ = "admin"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255))
    username = Column(String(255), nullable=False, unique=True)
    password = Column(String(255), nullable=False)  # md5 in legacy PHP
    user_type = Column(String(50))  # e.g. techadmin
    created_at = Column(DateTime)
