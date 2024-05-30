from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length


class RegistrationForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(message="Please enter your name.")])
    email = StringField('Email', validators=[DataRequired(message="Please enter your email address."), Email(message="Invalid email address.")])
    password = PasswordField('Password', validators=[DataRequired(message="Please enter a password."), Length(min=6, message="Password must be at least 6 characters long.")])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(message="Please confirm your password."), EqualTo('password', message="Passwords must match.")])
    submit = SubmitField('Sign Up')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(message="Please enter your email address")])
    password = PasswordField('Password', validators=[DataRequired(message="Password kalay??")])
    submit = SubmitField('Log In')
