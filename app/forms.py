from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    HiddenField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.fields import DateField, TimeField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional, Regexp, ValidationError


BUILDING_RULES = {
    "301": {"max_floor": 27, "max_line": 3},
    "302": {"max_floor": 27, "max_line": 3},
    "303": {"max_floor": 28, "max_line": 3},
    "304": {"max_floor": 27, "max_line": 4},
    "305": {"max_floor": 22, "max_line": 2},
}


def _validate_dong_value(value):
    dong = str(value or "").strip()
    if dong not in BUILDING_RULES:
        raise ValidationError("동은 301, 302, 303, 304, 305 중에서만 입력 가능합니다.")
    return dong


def _validate_ho_value(dong, value):
    ho = str(value or "").strip()
    if not ho.isdigit() or len(ho) < 3:
        raise ValidationError("호수는 예: 2303 형식의 숫자로 입력해주세요.")

    floor = int(ho[:-2])
    line = int(ho[-2:])
    rule = BUILDING_RULES.get(dong)
    if not rule:
        raise ValidationError("유효한 동 정보를 먼저 입력해주세요.")

    if floor < 1 or floor > rule["max_floor"]:
        raise ValidationError(f"{dong}동은 1층부터 {rule['max_floor']}층까지만 가능합니다.")
    if line < 1 or line > rule["max_line"]:
        raise ValidationError(f"{dong}동은 각 층 {rule['max_line']}호까지만 가능합니다.")


class ApartmentValidationMixin:
    def validate_apt_dong(self, field):
        _validate_dong_value(field.data)

    def validate_apt_ho(self, field):
        dong = _validate_dong_value(getattr(self, "apt_dong").data)
        _validate_ho_value(dong, field.data)


class ReservationForm(ApartmentValidationMixin, FlaskForm):
    month_id = HiddenField(validators=[DataRequired()])
    slot_id = HiddenField()
    name = StringField("이름", validators=[DataRequired(), Length(max=50)])
    apt_dong = StringField("동", validators=[DataRequired(), Length(max=10)])
    apt_ho = StringField("호수", validators=[DataRequired(), Length(max=10)])
    phone = StringField(
        "휴대폰번호",
        validators=[
            DataRequired(),
            Length(max=20),
            Regexp(r"^010-\d{4}-\d{4}$", message="휴대폰번호는 010-1234-5678 형식으로 입력해주세요."),
        ],
    )
    children_count = IntegerField(
        "아이 인원수", validators=[DataRequired(), NumberRange(min=1, max=20)]
    )
    consent_agreed = BooleanField("개인정보 수집 및 이용 동의", validators=[DataRequired()])
    submit = SubmitField("해당 월 이용 신청하기")


class LoginForm(FlaskForm):
    username = StringField("아이디", validators=[DataRequired()])
    password = PasswordField("비밀번호", validators=[DataRequired()])
    submit = SubmitField("로그인")


class NoticeForm(FlaskForm):
    notice_text = TextAreaField("공지사항", validators=[DataRequired()])
    submit = SubmitField("저장")


class MonthForm(FlaskForm):
    target_year = SelectField("년도", coerce=int, validators=[DataRequired()])
    target_month_num = SelectField("월", coerce=int, validators=[DataRequired()])
    title = StringField("제목", validators=[Length(max=100)])
    open_date = DateField("오픈 날짜", validators=[DataRequired()])
    close_date = DateField("마감 날짜", validators=[DataRequired()])
    payment_amount = IntegerField(
        "이용금액(원)", validators=[Optional(), NumberRange(min=0, max=10000000)], default=5000
    )
    capacity = IntegerField(
        "월별 신청 정원", validators=[DataRequired(), NumberRange(min=1, max=9999)], default=100
    )
    submit = SubmitField("생성")


class SlotForm(FlaskForm):
    month_id = SelectField("예약 월", coerce=int, validators=[DataRequired()])
    play_date = DateField("이용일", validators=[DataRequired()])
    start_time = TimeField("시작 시간", validators=[DataRequired()])
    end_time = TimeField("종료 시간", validators=[DataRequired()])
    capacity = IntegerField("정원", validators=[DataRequired(), NumberRange(min=1, max=200)])
    submit = SubmitField("슬롯 저장")


class ReservationStatusForm(FlaskForm):
    status = SelectField(
        "상태",
        choices=[
            ("PENDING_PAYMENT", "입금대기"),
            ("PAYMENT_CONFIRMED", "입금확인"),
            ("CANCELLED", "취소"),
        ],
        validators=[DataRequired()],
    )
    submit = SubmitField("상태 변경")


class ReservationLookupForm(ApartmentValidationMixin, FlaskForm):
    name = StringField("이름", validators=[DataRequired(), Length(max=50)])
    phone = StringField(
        "휴대폰번호",
        validators=[
            DataRequired(),
            Length(max=20),
            Regexp(r"^010-\d{4}-\d{4}$", message="휴대폰번호는 010-1234-5678 형식으로 입력해주세요."),
        ],
    )
    apt_dong = StringField("동", validators=[DataRequired(), Length(max=10)])
    apt_ho = StringField("호수", validators=[DataRequired(), Length(max=10)])
    submit = SubmitField("비밀번호조회")


class PaymentRequestForm(ApartmentValidationMixin, FlaskForm):
    name = StringField("이름", validators=[DataRequired(), Length(max=50)])
    phone = StringField(
        "휴대폰번호",
        validators=[
            DataRequired(),
            Length(max=20),
            Regexp(r"^010-\d{4}-\d{4}$", message="휴대폰번호는 010-1234-5678 형식으로 입력해주세요."),
        ],
    )
    apt_dong = StringField("동", validators=[DataRequired(), Length(max=10)])
    apt_ho = StringField("호수", validators=[DataRequired(), Length(max=10)])
    content = TextAreaField("내용", validators=[Length(max=1000)])
    consent_agreed = BooleanField("개인정보 수집 및 이용 동의", validators=[DataRequired()])
    submit = SubmitField("입금확인요청")


class PaymentRequestReplyForm(FlaskForm):
    thread_id = HiddenField(validators=[DataRequired()])
    content = TextAreaField("답변 내용", validators=[DataRequired(), Length(max=1000)])
    submit = SubmitField("답변 등록")


class TickerMessageForm(FlaskForm):
    content = TextAreaField("전광판 문구", validators=[DataRequired(), Length(max=300)])
    display_seconds = IntegerField("노출시간(초)", validators=[InputRequired(), NumberRange(min=1, max=30)], default=3)
    sort_order = IntegerField("정렬순서", validators=[InputRequired(), NumberRange(min=0, max=999)], default=0)
    submit = SubmitField("전광판 저장")


class BankSettingsForm(FlaskForm):
    bank_code = SelectField(
        "은행",
        choices=[
            ("NH", "농협은행 (NH)"),
            ("KB", "KB국민은행 (KB)"),
            ("WR", "우리은행 (WR)"),
            ("SH", "신한은행 (SH)"),
            ("HN", "하나은행 (HN)"),
            ("IBK", "IBK기업은행 (IBK)"),
        ],
        validators=[DataRequired()],
    )
    account_holder_name = StringField("예금주명", validators=[Length(max=100)])
    account_number = StringField(
        "계좌번호",
        validators=[Optional(), Length(max=30), Regexp(r"^[0-9-]+$", message="계좌번호는 숫자와 하이픈만 입력해주세요.")],
    )
    account_password = PasswordField("계좌 비밀번호", validators=[Optional(), Length(max=20)])
    resident_number = StringField(
        "생년월일/사업자번호",
        validators=[Optional(), Length(min=6, max=10), Regexp(r"^[0-9]+$", message="숫자만 입력해주세요.")],
    )
    payment_amount = IntegerField(
        "예약금액(원)", validators=[InputRequired(), NumberRange(min=0, max=10000000)], default=5000
    )
    is_active = BooleanField("자동 입금 확인 활성화", default=True)
    submit = SubmitField("은행 연동 저장")


class BankSyncForm(FlaskForm):
    lookback_days = IntegerField(
        "최초 조회기간(일)", validators=[InputRequired(), NumberRange(min=1, max=365)], default=30
    )
    submit = SubmitField("지금 동기화")