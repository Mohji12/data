from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ExamSummary(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    total_questions: int
    duration_seconds: int
    is_finished: bool = False
    attempts_used: int = 0
    max_attempts: int = 2
    remaining_attempts: int = 2
    can_retake: bool = False
    has_active_attempt: bool = False


class ExamDetail(ExamSummary):
    section_ids: list[int]


class QuestionOption(BaseModel):
    key: str
    text: str


class QuestionPayload(BaseModel):
    id: int
    text: str
    image_url: Optional[str] = None
    marking_description: Optional[str] = None
    answer_type: str
    options: list[QuestionOption]
    user_answer: Optional[list[str]] = None


class AttemptState(BaseModel):
    exam_id: int
    user_id: int
    total_questions: int
    current_question_no: int
    is_first_question: bool
    is_last_question: bool
    remaining_seconds: int
    attempt_no: int = 1
    attempts_used: int = 0
    max_attempts: int = 2
    remaining_attempts: int = 2


class AnswerSubmitRequest(BaseModel):
    user_id: int
    question_id: int
    display_question_id: Optional[int] = None
    answers: Optional[list[str]] = None
    is_last_question: bool = False


class AnswerSubmitResponse(BaseModel):
    finish_exam: bool
    total_user_marks: float
    attempt: AttemptState
    question: Optional[QuestionPayload] = None


class QuestionReview(BaseModel):
    id: int
    text: str
    options: list[QuestionOption]
    user_answer: Optional[list[str]] = None
    correct_answer: list[str]
    is_correct: bool
    marks: float
    negative_mark: float


class ResultSummary(BaseModel):
    exam_id: int
    user_id: int
    exam_title: str
    attempt_no: int = 1
    total_questions: int
    total_answered: int
    total_correct: int
    total_wrong: int
    total_marks: float
    reviews: list[QuestionReview] = []


class AllQuestionsResponse(BaseModel):
    exam_id: int
    exam_title: str
    attempt_no: int = 1
    questions: list[QuestionPayload]
    remaining_seconds: int


class AttemptSummary(BaseModel):
    attempt_no: int
    user_exam_id: int
    is_finished: bool
    marks: float
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    total_answered: int
    total_correct: int
    total_wrong: int


class FeatureAccess(BaseModel):
    enabled: bool
    reason: Optional[str] = None


class ExtensionAccess(BaseModel):
    enabled: bool
    reason: Optional[str] = None
    days_to_expiry: Optional[int] = None
    current_end_at: Optional[datetime] = None
    extension_months: int = 2
    estimated_amount: Optional[float] = None
    currency_name: Optional[str] = None
    gross_amount: Optional[float] = None
    gst_percentage: Optional[float] = None
    gst_amount: Optional[float] = None
    payment_amount_inr: Optional[float] = None
    batch_end_date: Optional[str] = None
    extended_end_date: Optional[str] = None
    headline: Optional[str] = None


class DashboardSummary(BaseModel):
    user_id: int
    name: Optional[str] = None
    email: str
    subscription: Optional[str] = None
    video: FeatureAccess
    mock_test: FeatureAccess
    certificate: FeatureAccess
    certificate_only: bool = False
    extension: ExtensionAccess


class SubscriptionPeriodInfo(BaseModel):
    """Active time-bound entitlement for subscription plan_type packages."""

    plan_type: str = "one_time"
    status: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    duration_months: Optional[int] = None
    days_remaining: Optional[int] = None
    extension_months: Optional[int] = None
    end_at_if_extended: Optional[datetime] = None


class DashboardProfile(BaseModel):
    id: int
    registration_type: Optional[str] = None
    subscription: Optional[str] = None
    title: Optional[str] = None
    name: Optional[str] = None
    email: str
    contact_number: Optional[str] = None
    hospital: Optional[str] = None
    qualification: Optional[str] = None
    speciality: Optional[str] = None
    country_id: Optional[int] = None
    state: Optional[str] = None
    city: Optional[str] = None
    pin_code: Optional[str] = None
    currency_name: Optional[str] = None
    payment_status: Optional[str] = None
    approve: Optional[str] = None
    subscription_period: Optional[SubscriptionPeriodInfo] = None


class DashboardProfileUpdateRequest(BaseModel):
    title: Optional[str] = None
    name: Optional[str] = None
    contact_number: Optional[str] = None
    hospital: Optional[str] = None
    qualification: Optional[str] = None
    speciality: Optional[str] = None
    country_id: Optional[int] = None
    state: Optional[str] = None
    city: Optional[str] = None
    pin_code: Optional[str] = None


class DashboardPaymentItem(BaseModel):
    id: int
    subscription: Optional[str] = None
    package_type: Optional[str] = None
    currency_name: Optional[str] = None
    payment_status: Optional[str] = None
    payment_type: Optional[str] = None
    payment_date: Optional[datetime] = None


class VideoFolderItem(BaseModel):
    id: int
    name: str
    display_order: int


class VideoListItem(BaseModel):
    id: int
    title: str
    folder_id: Optional[int] = None
    folder_name: Optional[str] = None
    thumbnail_url: Optional[str] = None
    description: Optional[str] = None
    upload_date: Optional[datetime] = None


class VideoListPage(BaseModel):
    items: list[VideoListItem]
    total: int
    page: int
    page_size: int
    has_more: bool


class VideoDetail(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    folder_id: Optional[int] = None
    folder_name: Optional[str] = None
    thumbnail_url: Optional[str] = None
    video_url: Optional[str] = None
    upload_date: Optional[datetime] = None


class VideoQuestionCreate(BaseModel):
    question: str


class VideoQuestionCreateResponse(BaseModel):
    status: str
    message: str


class BatchDefinition(BaseModel):
    slug: str
    title: str
    registration_type: str
    requires_document: bool = False
    coupon_enabled: bool = False
    # When set, `package.subscription` is matched by this value instead of `title` (display name).
    package_subscription: Optional[str] = None


class FeeStructureBlock(BaseModel):
    """One delegate block (INR or USD) — cell strings align with column_headers."""

    group_label: str
    registration_fee: list[str]
    discount: list[str]
    total: list[str]
    total_payable: list[str]
    package_ids: list[int] = []
    plan_badges: list[str] = []
    column_headers: list[str] = []


class FeeStructureResponse(BaseModel):
    """Public fee table for registration landing pages (all active tiers, not date-filtered)."""

    batch_slug: str
    batch_name: str
    page_title: str
    breadcrumb_tail: str
    notice: Optional[str] = None
    description: Optional[str] = None
    brochure_url: Optional[str] = None
    video_url: Optional[str] = None
    video_resolved_url: Optional[str] = None
    column_headers: list[str]
    indian: FeeStructureBlock
    foreign: FeeStructureBlock


class RegistrationCatalogItem(BaseModel):
    batch_id: int
    batch_slug: str
    batch_name: str
    registration_type: str
    status: str
    brochure_url: Optional[str] = None
    notice: Optional[str] = None
    description: Optional[str] = None
    video_url: Optional[str] = None
    video_resolved_url: Optional[str] = None
    has_indian_package: bool
    has_foreign_package: bool
    indian_package_count: int
    foreign_package_count: int
    launch_ready: bool
    launch_issues: list[str] = []


class PayableAmountRequest(BaseModel):
    batch_slug: str
    package_id: int
    country_id: int
    coupon_code: Optional[str] = None
    email: Optional[str] = Field(default=None, description="Required for assigned-email coupons when previewing.")
    subscription: Optional[str] = Field(
        default=None,
        description="Batch/course title for subscription-scoped coupons; defaults to package.subscription.",
    )


class PayableAmountResponse(BaseModel):
    currency_name: str
    gross_amount: float
    gst_percentage: float
    gst_amount: float
    discount_amount: float
    total_amount: float
    coupon_applied: bool = False
    coupon_code: Optional[str] = None
    early_bird_applied: bool = False
    early_bird_percent: float = 0.0
    discount_percent_used: float = 0.0


class RegistrationInitRequest(BaseModel):
    batch_slug: str
    registration_type: str
    subscription: str
    title: str
    name: str
    email: str
    password: str
    contact_number: str
    country_id: int
    package_id: int
    hospital: Optional[str] = None
    qualification: Optional[str] = None
    speciality: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    pin_code: Optional[str] = None
    coupon_code: Optional[str] = None
    document_file: Optional[str] = None


class RegistrationInitResponse(BaseModel):
    registration_id: int
    request_id: str
    payment_status: str
    amount: PayableAmountResponse


class PaymentOrderRequest(BaseModel):
    request_id: str


class PaymentOrderResponse(BaseModel):
    request_id: str
    gateway: str
    order_id: str
    amount: float
    currency: str
    key_id: Optional[str] = None
    user_name: str
    user_email: str
    user_contact: Optional[str] = None


class PaymentFinalizeRequest(BaseModel):
    request_id: str
    order_id: str
    payment_id: str
    signature: str
    raw_payload: Optional[dict[str, Any]] = None


class PaymentFinalizeResponse(BaseModel):
    request_id: str
    status: str
    payment_status: str
    approve: str
    user_id: int
    message: str


class RegistrationStatusResponse(BaseModel):
    registration_id: int
    request_id: str
    payment_status: str
    approve: str
    email: str
    subscription: str


class ExtensionInitResponse(BaseModel):
    request_id: str
    amount: float
    currency: str
    extension_months: int = 2

