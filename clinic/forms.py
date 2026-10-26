import os

from django import forms
from django.conf import settings

from .models import Order, Patient, Reading, Report

ALLOWED_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg", ".txt", ".csv", ".dcm"]


class ReadingForm(forms.ModelForm):
    class Meta:
        model = Reading
        fields = ["recorded_at", "heart_rate", "systolic", "diastolic", "temperature", "oxygen"]
        widgets = {"recorded_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}


class CsvUploadForm(forms.Form):
    file = forms.FileField(help_text="CSV exported from the device: recorded_at, heart_rate, systolic, diastolic, temperature, oxygen")


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["condition", "notes", "prescription"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3}), "prescription": forms.Textarea(attrs={"rows": 3})}


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["service", "notes"]


class ResultForm(forms.Form):
    result = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    file = forms.FileField(required=False, help_text="Optional: scan image or lab report")

    def clean_file(self):
        f = self.cleaned_data.get("file")
        return check_file(f) if f else f


class DocumentForm(forms.Form):
    title = forms.CharField(max_length=120)
    file = forms.FileField()

    def clean_file(self):
        return check_file(self.cleaned_data["file"])


class MessageForm(forms.Form):
    text = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), label="Message")


class EmergencyForm(forms.ModelForm):
    """Only the most important fields so a new patient can be added in seconds."""

    class Meta:
        model = Patient
        fields = ["full_name", "complaint", "priority", "gender", "allergies"]
        labels = {"full_name": "Name (or 'Unknown')", "complaint": "What happened?"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["complaint"].required = True
        self.fields["priority"].required = True


def check_file(f):
    extension = os.path.splitext(f.name)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise forms.ValidationError("Allowed file types: " + ", ".join(ALLOWED_EXTENSIONS))
    if f.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise forms.ValidationError(f"Maximum file size is {settings.MAX_UPLOAD_MB} MB.")
    return f
