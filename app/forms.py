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
from wtforms.validators import DataRequired, Length, NumberRange, Regexp


class ReservationForm(FlaskForm):
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
    capacity = IntegerField(
        "월별 신청 정원", validators=[DataRequired(), NumberRange(min=1, max=9999)], default=100
    )
    access_password = StringField("입장 비밀번호", validators=[Length(max=50)])
    submit = SubmitField("월 저장")


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


class ReservationLookupForm(FlaskForm):
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
    submit = SubmitField("내 신청 조회")