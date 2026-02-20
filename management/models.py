from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('ADMIN', 'Admin'),
        ('HR', 'HR Manager'),
        ('EMPLOYEE', 'Employee'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='EMPLOYEE')
    phone = models.CharField(max_length=15, blank=True, null=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    department = models.CharField(max_length=50, blank=True, null=True)
    date_of_joining = models.DateField(blank=True, null=True)

    def is_admin(self):
        return self.role == 'ADMIN' or self.is_superuser

    def is_hr(self):
        return self.role == 'HR'

    def is_employee(self):
        return self.role == 'EMPLOYEE' and not self.is_superuser and not self.role == 'HR'

class Project(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField()
    manager = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='managed_projects')
    team_members = models.ManyToManyField(CustomUser, related_name='projects')
    status = models.CharField(max_length=20, choices=(
        ('PLANNED', 'Planned'),
        ('ONGOING', 'Ongoing'),
        ('COMPLETED', 'Completed'),
        ('ONHOLD', 'On Hold'),
    ), default='PLANNED')

    def __str__(self):
        return self.name

    def calculate_progress(self):
        tasks = self.tasks.all()
        if not tasks:
            return 0
        total_progress = sum(t.progress for t in tasks)
        return round(total_progress / tasks.count(), 1)

class Task(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=200)
    description = models.TextField()
    assigned_to = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='assigned_tasks')
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=(
        ('TODO', 'To Do'),
        ('IN_PROGRESS', 'In Progress'),
        ('DONE', 'Done'),
    ), default='TODO')
    progress = models.IntegerField(default=0) # 0 to 100

    def __str__(self):
        return self.title

class Announcement(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    def __str__(self):
        return self.title

class JobOpening(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    requirements = models.TextField()
    posted_on = models.DateField(auto_now_add=True)
    closed_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title

class Candidate(models.Model):
    job = models.ForeignKey(JobOpening, on_delete=models.CASCADE, related_name='candidates')
    name = models.CharField(max_length=100)
    email = models.EmailField()
    resume = models.FileField(upload_to='resumes/')
    status = models.CharField(max_length=20, choices=(
        ('APPLIED', 'Applied'),
        ('INTERVIEW_SCHEDULED', 'Interview Scheduled'),
        ('HIRED', 'Hired'),
        ('REJECTED', 'Rejected'),
    ), default='APPLIED')
    interview_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} - {self.job.title}"

class LeaveRequest(models.Model):
    employee = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=(
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    ), default='PENDING')
    applied_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee.username} - {self.leave_type}"

class Attendance(models.Model):
    employee = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='attendance')
    date = models.DateField(default=timezone.now)
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('employee', 'date')

    def __str__(self):
        return f"{self.employee.username} - {self.date}"

    def work_hours(self):
        if self.check_in and self.check_out:
            duration = self.check_out - self.check_in
            return round(duration.total_seconds() / 3600, 2)
        return 0

class Shift(models.Model):
    SHIFT_TYPES = (
        ('DAY', 'Day Shift'),
        ('NIGHT', 'Night Shift'),
        ('OVERTIME', 'Overtime'),
    )
    employee = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='shifts')
    shift_type = models.CharField(max_length=20, choices=SHIFT_TYPES, default='DAY')
    start_time = models.TimeField()
    end_time = models.TimeField()
    day_of_week = models.IntegerField(choices=((0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')))

    def __str__(self):
        return f"{self.employee.username} - {self.get_shift_type_display()} - {self.get_day_of_week_display()}"

    def duration(self):
        from datetime import datetime, date, timedelta
        d1 = datetime.combine(date.today(), self.start_time)
        d2 = datetime.combine(date.today(), self.end_time)
        if d2 <= d1:
            d2 += timedelta(days=1)
        diff = d2 - d1
        return round(diff.total_seconds() / 3600, 1)

class Document(models.Model):
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='company_docs/')
    uploaded_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_policy = models.BooleanField(default=False)

    def __str__(self):
        return self.title

class PerformanceReview(models.Model):
    employee = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='performance_reviews')
    reviewer = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='given_reviews')
    review_date = models.DateField(auto_now_add=True)
    rating = models.IntegerField(choices=[(i, str(i)) for i in range(1, 6)]) # 1 to 5
    comments = models.TextField()
    productivity_score = models.FloatField(default=0.0)
    attendance_score = models.FloatField(default=0.0)

    def __str__(self):
        return f"Review for {self.employee.username} - {self.review_date}"

class SystemLog(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.action} at {self.timestamp}"

class Feedback(models.Model):
    employee = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='feedbacks')
    subject = models.CharField(max_length=200, blank=True, null=True)
    comment = models.TextField() # Changed from message to comment to match view
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback from {self.employee.username}"
