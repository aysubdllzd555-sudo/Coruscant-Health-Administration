from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from clinic.models import DISTRICTS, Department, Patient

from .models import User


class LoginForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        # Unapproved users may log in so they can see their pending status;
        # every protected view enforces approval.
        if not user.is_active:
            raise forms.ValidationError("This account has been deactivated.", code="inactive")


class RegistrationForm(UserCreationForm):
    ROLE_CHOICES = [
        (User.Role.PATIENT, "Patient"),
        (User.Role.DOCTOR, "Doctor"),
        (User.Role.DEPARTMENT, "Department staff"),
        (User.Role.EMERGENCY, "Emergency services"),
    ]
    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.RadioSelect, initial=User.Role.PATIENT)
    first_name = forms.CharField(max_length=60)
    last_name = forms.CharField(max_length=60)
    email = forms.EmailField()
    phone = forms.CharField(max_length=32, required=False)

    # patient fields
    date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    sex = forms.ChoiceField(choices=Patient.Sex.choices, required=False)
    district = forms.ChoiceField(choices=[("", "Select district")] + DISTRICTS, required=False)
    allergies = forms.CharField(max_length=200, required=False)

    # doctor fields
    specialty = forms.CharField(max_length=80, required=False)
    license_number = forms.CharField(max_length=40, required=False, label="Medical licence no.")

    # department staff
    department = forms.ModelChoiceField(queryset=Department.objects.all(), required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        data = super().clean()
        role = data.get("role")
        if role == User.Role.PATIENT and not data.get("date_of_birth"):
            self.add_error("date_of_birth", "Date of birth is required for patients.")
        if role == User.Role.DOCTOR and not data.get("license_number"):
            self.add_error("license_number", "A licence number is required so the administrator can verify you.")
        if role == User.Role.DEPARTMENT and not data.get("department"):
            self.add_error("department", "Choose the department you work in.")
        return data
