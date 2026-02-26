from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    BooleanField,
    HiddenField,
    RadioField,
    SelectField,
    IntegerField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3)])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember me")


class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField("Confirm Password", validators=[DataRequired(), Length(min=6)])


# settings-related forms
class AddSubForm(FlaskForm):
    intent = HiddenField(default="add")
    sub = StringField("Subreddit", validators=[Optional(), Length(min=1)])


class ReorderForm(FlaskForm):
    intent = HiddenField(default="reorder")
    order = HiddenField(validators=[DataRequired()])


class RemoveSubForm(FlaskForm):
    intent = HiddenField(default="remove")
    sub = HiddenField(validators=[DataRequired()])


class UnbanForm(FlaskForm):
    intent = HiddenField(default="unban")
    sub = HiddenField(validators=[DataRequired()])


class SidebarForm(FlaskForm):
    intent = HiddenField(default="save_sidebar")
    sidebar_position = RadioField(
        "Sidebar Position",
        choices=[("left", "Left"), ("right", "Right"), ("off", "Off")],
        default="left",
    )


class PlaybackForm(FlaskForm):
    intent = HiddenField(default="save_playback")
    default_volume = IntegerField("Default Volume", validators=[NumberRange(min=0, max=100)])
    default_speed = SelectField(
        "Default Speed",
        choices=[
            ("0.25", "0.25x"),
            ("0.5", "0.5x"),
            ("0.75", "0.75x"),
            ("1.0", "1x (Normal)"),
            ("1.25", "1.25x"),
            ("1.5", "1.5x"),
            ("1.75", "1.75x"),
            ("2.0", "2x"),
        ],
        default="1.0",
    )


class BehaviorForm(FlaskForm):
    intent = HiddenField(default="save_behavior")
    title_links = BooleanField("Make post titles clickable")


