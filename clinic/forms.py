from django import forms
from django.conf import settings

from .models import Device, Document, Order, Patient, Reading, Report, ServiceType

ALLOWED_DOC_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/dicom": ".dcm",
    "application/dicom": ".dcm",
    "text/plain": ".txt",
    "text/csv": ".csv",
}
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".dcm", ".txt", ".csv"}
MAGIC = {".pdf": b"%PDF", ".png": b"\x89PNG", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff"}


class ManualReadingForm(forms.ModelForm):
    class Meta:
        model = Reading
        fields = ["recorded_at", "heart_rate", "spo2", "temperature_c", "systolic", "diastolic", "resp_rate", "glucose", "steps"]
        widgets = {"recorded_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def clean(self):
        data = super().clean()
        measures = [f for f in self.Meta.fields if f != "recorded_at" and data.get(f) is not None]
        if not measures:
            raise forms.ValidationError("Enter at least one measurement.")
        return data


class ReadingUploadForm(forms.Form):
    file = forms.FileField(help_text="CSV or JSON export from your device (max 5,000 rows).")

    def clean_file(self):
        f = self.cleaned_data["file"]
        if not f.name.lower().endswith((".csv", ".json")):
            raise forms.ValidationError("Upload a .csv or .json file.")
        if f.size > 2 * 1024 * 1024:
            raise forms.ValidationError("Device exports are limited to 2 MB.")
        return f


class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ["label", "kind", "serial"]


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["title", "condition", "assessment", "suggestions", "follow_up_on"]
        widgets = {
            "assessment": forms.Textarea(attrs={"rows": 5}),
            "suggestions": forms.Textarea(attrs={"rows": 5}),
            "follow_up_on": forms.DateInput(attrs={"type": "date"}),
            "condition": forms.RadioSelect,
        }
        labels = {"condition": "Patient's condition", "suggestions": "Prescription & suggestions"}


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["service", "priority", "indication"]
        widgets = {"priority": forms.RadioSelect}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["service"].queryset = ServiceType.objects.select_related("department")
        self.fields["service"].label_from_instance = lambda s: f"{s.department.name} — {s.name}"


class ResultForm(forms.Form):
    result_flag = forms.ChoiceField(choices=Order.Flag.choices, widget=forms.RadioSelect, initial="normal", label="Result")
    result_summary = forms.CharField(widget=forms.Textarea(attrs={"rows": 5}), label="Findings / report")
    file = forms.FileField(required=False, label="Attach result file (encrypted at rest)")

    def clean_file(self):
        f = self.cleaned_data.get("file")
        return validate_document(f) if f else f


def validate_document(f):
    import os

    ext = os.path.splitext(f.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise forms.ValidationError("Allowed types: PDF, PNG, JPEG, DICOM, TXT, CSV.")
    if f.size > settings.MAX_UPLOAD_BYTES:
        raise forms.ValidationError(f"Files are limited to {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    head = f.read(8)
    f.seek(0)
    if ext in MAGIC and not head.startswith(MAGIC[ext]):
        raise forms.ValidationError("The file content does not match its extension.")
    return f


class DocumentForm(forms.Form):
    title = forms.CharField(max_length=120)
    category = forms.ChoiceField(choices=Document.Category.choices)
    file = forms.FileField()

    def clean_file(self):
        return validate_document(self.cleaned_data["file"])


class MessageForm(forms.Form):
    body = forms.CharField(widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Write a message to the care team…"}), max_length=4000, label="")


ARRIVAL_CHOICES = [("walk_in", "Walk-in"), ("ambulance", "Ambulance"), ("speeder", "Air speeder"), ("police", "CSF / police"), ("transfer", "Transfer")]


class EmergencyIntakeForm(forms.Form):
    """Deliberately minimal: two required fields, everything else optional."""

    chief_complaint = forms.CharField(max_length=120, widget=forms.TextInput(attrs={"autofocus": True, "placeholder": "e.g. Chest pain, fever after Manarai Heights visit"}))
    acuity = forms.TypedChoiceField(choices=Patient.Acuity.choices, coerce=int, widget=forms.RadioSelect, initial=3)
    first_name = forms.CharField(max_length=60, required=False)
    last_name = forms.CharField(max_length=60, required=False)
    approx_age = forms.IntegerField(min_value=0, max_value=1000, required=False, label="Age (approx.)")
    sex = forms.ChoiceField(choices=Patient.Sex.choices, initial=Patient.Sex.OTHER)
    species = forms.CharField(max_length=40, initial="Human")
    arrival_mode = forms.ChoiceField(choices=ARRIVAL_CHOICES, initial="walk_in")
    bay = forms.CharField(max_length=8, required=False, help_text="Leave empty to add to the waiting room")
    allergies = forms.CharField(max_length=200, required=False)
    heart_rate = forms.IntegerField(min_value=20, max_value=260, required=False, label="HR")
    spo2 = forms.IntegerField(min_value=50, max_value=100, required=False, label="SpO₂")
    systolic = forms.IntegerField(min_value=50, max_value=260, required=False, label="Sys BP")
    resp_rate = forms.IntegerField(min_value=4, max_value=70, required=False, label="RR")
    temperature_c = forms.DecimalField(min_value=30, max_value=45, decimal_places=1, required=False, label="Temp °C")
    brainworm_screened = forms.BooleanField(required=False, label="Brainworm Rot type A screened")


class BedUpdateForm(forms.Form):
    ed_status = forms.ChoiceField(choices=[c for c in Patient.EDStatus.choices if c[0] != "none"])
    bay = forms.CharField(max_length=8, required=False)
    acuity = forms.TypedChoiceField(choices=Patient.Acuity.choices, coerce=int)
