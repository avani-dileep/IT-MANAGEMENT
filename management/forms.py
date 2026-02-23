from django import forms
from django.core.validators import RegexValidator
from django.utils import timezone
from .models import CustomUser, LeaveRequest, JobOpening, Announcement, PerformanceReview, Task, Project, Feedback
import re


# ─────────────────────────── USER FORM ────────────────────────────────────────
class UserForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(),
        required=False,
        min_length=8,
        error_messages={'min_length': 'Password must be at least 8 characters.'}
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password', 'first_name', 'last_name',
                  'role', 'department', 'designation', 'level', 'date_of_joining',
                  'phone', 'profile_pic']
        widgets = {
            'date_of_joining': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if not username:
            raise forms.ValidationError("Username is required.")
        if len(username) < 3:
            raise forms.ValidationError("Username must be at least 3 characters.")
        if not re.match(r'^[\w.@+\-]+$', username):
            raise forms.ValidationError("Username may only contain letters, digits, and @/./+/-/_")
        # Uniqueness check (skip own record when editing)
        qs = CustomUser.objects.filter(username=username)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A user with this username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if email:
            # Uniqueness check
            qs = CustomUser.objects.filter(email=email)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("This email address is already registered.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if phone:
            cleaned = re.sub(r'[\s\-\(\)\+]', '', phone)
            if not cleaned.isdigit():
                raise forms.ValidationError("Phone number must contain only digits (spaces, dashes, and + are allowed).")
            if not (7 <= len(cleaned) <= 15):
                raise forms.ValidationError("Phone number must be between 7 and 15 digits.")
        return phone

    def clean_first_name(self):
        name = self.cleaned_data.get('first_name', '').strip()
        if name and not re.match(r"^[a-zA-Z\s'\-]+$", name):
            raise forms.ValidationError("First name may only contain letters, spaces, apostrophes, and hyphens.")
        return name

    def clean_last_name(self):
        name = self.cleaned_data.get('last_name', '').strip()
        if name and not re.match(r"^[a-zA-Z\s'\-]+$", name):
            raise forms.ValidationError("Last name may only contain letters, spaces, apostrophes, and hyphens.")
        return name

    def clean_profile_pic(self):
        pic = self.cleaned_data.get('profile_pic')
        if pic and hasattr(pic, 'size'):
            if pic.size > 5 * 1024 * 1024:  # 5 MB
                raise forms.ValidationError("Profile picture must be smaller than 5 MB.")
            valid_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if hasattr(pic, 'content_type') and pic.content_type not in valid_types:
                raise forms.ValidationError("Only JPEG, PNG, GIF, and WebP images are accepted.")
        return pic

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("password"):
            user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


# ─────────────────────────── LEAVE REQUEST FORM ───────────────────────────────
class LeaveRequestForm(forms.ModelForm):
    LEAVE_CHOICES = [
        ('SICK', 'Sick Leave'),
        ('CASUAL', 'Casual Leave'),
        ('ANNUAL', 'Annual / Earned Leave'),
        ('MATERNITY', 'Maternity Leave'),
        ('PATERNITY', 'Paternity Leave'),
        ('COMPENSATORY', 'Compensatory Off'),
        ('OTHER', 'Other / Special Leave'),
    ]
    leave_type = forms.ChoiceField(
        choices=LEAVE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        error_messages={'required': 'Please select a leave type.'}
    )

    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'start_date', 'end_date', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'reason': forms.Textarea(attrs={
                'rows': 3, 'class': 'form-control',
                'placeholder': 'Provide a brief reason for your leave...'
            }),
        }
        error_messages = {
            'start_date': {'required': 'Start date is required.'},
            'end_date': {'required': 'End date is required.'},
            'reason': {'required': 'Please provide a reason for your leave request.'},
        }

    def clean_reason(self):
        reason = self.cleaned_data.get('reason', '').strip()
        if not reason:
            raise forms.ValidationError("Please provide a reason for your leave request.")
        if len(reason) < 10:
            raise forms.ValidationError("Reason must be at least 10 characters long.")
        if len(reason) > 500:
            raise forms.ValidationError("Reason cannot exceed 500 characters.")
        return reason

    def clean_start_date(self):
        from django.utils import timezone
        start_date = self.cleaned_data.get('start_date')
        if not start_date:
            raise forms.ValidationError("Start date is required.")
        if start_date < timezone.now().date():
            raise forms.ValidationError("You cannot apply for leave in the past.")
        return start_date

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date:
            if end_date < start_date:
                raise forms.ValidationError("End date cannot be earlier than the start date.")
            # Maximum 30 days at once
            delta = (end_date - start_date).days + 1
            if delta > 31:
                raise forms.ValidationError(
                    f"Leave duration cannot exceed 31 consecutive days. "
                    f"You selected {delta} days."
                )
        return cleaned_data


# ─────────────────────────── JOB OPENING FORM ─────────────────────────────────
class JobOpeningForm(forms.ModelForm):
    class Meta:
        model = JobOpening
        fields = ['title', 'description', 'requirements', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Senior Python Developer'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4,
                'placeholder': 'Describe the role, responsibilities, and team...'
            }),
            'requirements': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'List key skills, qualifications, and experience required...'
            }),
        }
        error_messages = {
            'title': {'required': 'Job title is required.'},
            'description': {'required': 'Job description is required.'},
        }

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if not title:
            raise forms.ValidationError("Job title is required.")
        if len(title) < 3:
            raise forms.ValidationError("Job title must be at least 3 characters.")
        if len(title) > 200:
            raise forms.ValidationError("Job title cannot exceed 200 characters.")
        return title

    def clean_description(self):
        desc = self.cleaned_data.get('description', '').strip()
        if not desc:
            raise forms.ValidationError("Job description is required.")
        if len(desc) < 20:
            raise forms.ValidationError("Description must be at least 20 characters.")
        return desc

    def clean_requirements(self):
        req = self.cleaned_data.get('requirements', '').strip()
        if req and len(req) < 10:
            raise forms.ValidationError("Requirements must be at least 10 characters if provided.")
        return req


# ─────────────────────────── ANNOUNCEMENT FORM ────────────────────────────────
class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'content', 'category']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Announcement headline...'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Write announcement details here...'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
        }
        error_messages = {
            'title': {'required': 'Announcement title is required.'},
            'content': {'required': 'Announcement content cannot be empty.'},
            'category': {'required': 'Please select a category.'},
        }

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if not title:
            raise forms.ValidationError("Announcement title is required.")
        if len(title) < 5:
            raise forms.ValidationError("Title must be at least 5 characters.")
        if len(title) > 200:
            raise forms.ValidationError("Title cannot exceed 200 characters.")
        return title

    def clean_content(self):
        content = self.cleaned_data.get('content', '').strip()
        if not content:
            raise forms.ValidationError("Announcement content cannot be empty.")
        if len(content) < 10:
            raise forms.ValidationError("Content must be at least 10 characters.")
        return content


# ─────────────────────────── FEEDBACK FORM ────────────────────────────────────
class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['subject', 'message']
        widgets = {
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'E.g. Cafeteria Improvement'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4,
                'placeholder': 'Describe your feedback or suggestion...'
            }),
        }
        error_messages = {
            'subject': {'required': 'Please enter a subject for your feedback.'},
            'message': {'required': 'Please enter your feedback message.'},
        }

    def clean_subject(self):
        subject = self.cleaned_data.get('subject', '').strip()
        if not subject:
            raise forms.ValidationError("Please enter a subject for your feedback.")
        if len(subject) < 3:
            raise forms.ValidationError("Subject must be at least 3 characters.")
        if len(subject) > 200:
            raise forms.ValidationError("Subject cannot exceed 200 characters.")
        return subject

    def clean_message(self):
        message = self.cleaned_data.get('message', '').strip()
        if not message:
            raise forms.ValidationError("Please enter your feedback message.")
        if len(message) < 10:
            raise forms.ValidationError("Message must be at least 10 characters.")
        if len(message) > 1000:
            raise forms.ValidationError("Message cannot exceed 1000 characters.")
        return message


# ─────────────────────────── PERFORMANCE REVIEW FORM ─────────────────────────
class PerformanceReviewForm(forms.ModelForm):
    class Meta:
        model = PerformanceReview
        fields = ['employee', 'rating', 'comments', 'productivity_score', 'attendance_score']
        error_messages = {
            'employee': {'required': 'Please select an employee to review.'},
            'rating': {'required': 'Please provide a star rating (1–5).'},
            'comments': {'required': 'Manager comments are required.'},
        }

    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        if rating is None:
            raise forms.ValidationError("Please select a star rating (1–5).")
        if not (1 <= int(rating) <= 5):
            raise forms.ValidationError("Rating must be between 1 and 5 stars.")
        return rating

    def clean_productivity_score(self):
        score = self.cleaned_data.get('productivity_score')
        if score is None:
            raise forms.ValidationError("Productivity score is required.")
        if not (0 <= float(score) <= 100):
            raise forms.ValidationError("Productivity score must be between 0 and 100.")
        return score

    def clean_attendance_score(self):
        score = self.cleaned_data.get('attendance_score')
        if score is None:
            raise forms.ValidationError("Attendance score is required.")
        if not (0 <= float(score) <= 100):
            raise forms.ValidationError("Attendance score must be between 0 and 100.")
        return score

    def clean_comments(self):
        comments = self.cleaned_data.get('comments', '').strip()
        if not comments:
            raise forms.ValidationError("Manager comments are required.")
        if len(comments) < 10:
            raise forms.ValidationError("Comments must be at least 10 characters.")
        if len(comments) > 2000:
            raise forms.ValidationError("Comments cannot exceed 2000 characters.")
        return comments


# ─────────────────────────── PROJECT FORM ─────────────────────────────────────
class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description', 'start_date', 'end_date', 'manager', 'team_members', 'status']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Describe the project scope and goals...'}),
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Customer Portal v2.0'}),
        }
        error_messages = {
            'name': {'required': 'Project name is required.'},
            'description': {'required': 'Project description is required.'},
            'start_date': {'required': 'Start date is required.'},
            'end_date': {'required': 'End date is required.'},
            'manager': {'required': 'Please assign a project manager.'},
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Project name is required.")
        if len(name) < 3:
            raise forms.ValidationError("Project name must be at least 3 characters.")
        if len(name) > 200:
            raise forms.ValidationError("Project name cannot exceed 200 characters.")
        return name

    def clean_description(self):
        desc = self.cleaned_data.get('description', '').strip()
        if not desc:
            raise forms.ValidationError("Project description is required.")
        if len(desc) < 10:
            raise forms.ValidationError("Description must be at least 10 characters.")
        return desc

    def clean_start_date(self):
        from django.utils import timezone
        start_date = self.cleaned_data.get('start_date')
        if not start_date:
            raise forms.ValidationError("Start date is required.")
        # Allow past dates when editing an existing project
        if not self.instance.pk and start_date < timezone.now().date():
            raise forms.ValidationError("Project start date cannot be set in the past.")
        return start_date

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date:
            if end_date < start_date:
                raise forms.ValidationError("Project end date cannot be earlier than its start date.")
            if (end_date - start_date).days > 730:  # 2 years
                raise forms.ValidationError("Project duration cannot exceed 2 years (730 days).")
        return cleaned_data


# ─────────────────────────── TASK FORM ────────────────────────────────────────
class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['project', 'title', 'description', 'assigned_to', 'due_date', 'status']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Describe what needs to be done...'}),
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Implement login API endpoint'}),
        }
        error_messages = {
            'title': {'required': 'Task title is required.'},
            'description': {'required': 'Task description is required.'},
            'assigned_to': {'required': 'Please assign this task to a team member.'},
            'due_date': {'required': 'Due date is required.'},
        }

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if not title:
            raise forms.ValidationError("Task title is required.")
        if len(title) < 3:
            raise forms.ValidationError("Task title must be at least 3 characters.")
        if len(title) > 200:
            raise forms.ValidationError("Task title cannot exceed 200 characters.")
        return title

    def clean_description(self):
        desc = self.cleaned_data.get('description', '').strip()
        if not desc:
            raise forms.ValidationError("Task description is required.")
        if len(desc) < 5:
            raise forms.ValidationError("Description must be at least 5 characters.")
        return desc

    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        if not due_date:
            raise forms.ValidationError("Due date is required.")
        if due_date < timezone.now().date():
            raise forms.ValidationError("Due date cannot be in the past.")
        return due_date
