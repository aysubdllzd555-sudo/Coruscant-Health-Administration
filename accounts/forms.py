from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class RegisterForm(UserCreationForm):
    """Registration for patients, doctors, department staff and emergency services."""

    role = forms.ChoiceField(choices=User.ROLE_CHOICES[:4])
    date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}),
                                    help_text="Patients only")

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "phone", "role",
                  "specialty", "license_number", "department"]
        help_texts = {
            "specialty": "Doctors only",
            "license_number": "Doctors only",
            "department": "Department staff only",
        }

    def clean(self):
        data = super().clean()
        role = data.get("role")
        if role == User.DOCTOR and not data.get("license_number"):
            self.add_error("license_number", "Doctors must enter a license number.")
        if role == User.DEPARTMENT and not data.get("department"):
            self.add_error("department", "Choose your department.")
        return data
