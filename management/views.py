from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import CustomUser, Project, Task, Announcement, JobOpening, Candidate, LeaveRequest, Attendance, Shift, Document, Feedback, PerformanceReview, SystemLog
from .forms import UserForm, LeaveRequestForm, JobOpeningForm, AnnouncementForm, PerformanceReviewForm, TaskForm
from django.db.models import Count, Prefetch

def login_view(request):
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(username=u, password=p)
        if user:
            login(request, user)
            SystemLog.objects.create(user=user, action="Logged in")
            return redirect('dashboard')
        messages.error(request, "Invalid credentials")
    return render(request, 'login.html')

def logout_view(request):
    if request.user.is_authenticated:
        SystemLog.objects.create(user=request.user, action="Logged out")
    logout(request)
    return redirect('login')

@login_required
def dashboard(request):
    user = request.user
    if user.is_admin():
        context = {
            'employee_count': CustomUser.objects.filter(role='EMPLOYEE').count(),
            'hr_count': CustomUser.objects.filter(role='HR').count(),
            'total_projects': Project.objects.count(),
        }
        return render(request, 'dashboards/admin.html', context)
    elif user.is_hr():
        context = {
            'active_projects': Project.objects.filter(status='ONGOING').count(),
            'pending_leaves': LeaveRequest.objects.filter(status='PENDING').count(),
            'open_jobs': JobOpening.objects.filter(is_active=True).count(),
        }
        return render(request, 'dashboards/hr.html', context)
    else:
        context = {
            'my_projects': user.projects.count(),
            'my_tasks': user.assigned_tasks.filter(status__in=['TODO', 'IN_PROGRESS']).count(),
            'my_leaves': user.leave_requests.count(),
        }
        return render(request, 'dashboards/employee.html', context)

# Admin Views
@login_required
def manage_users(request):
    if not request.user.is_admin(): return redirect('dashboard')
    users = CustomUser.objects.all().order_by('-date_joined')
    return render(request, 'admin/manage_users.html', {'users': users})

@login_required
def add_user(request):
    if not request.user.is_admin(): return redirect('dashboard')
    if request.method == 'POST':
        form = UserForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Employee added successfully!")
            return redirect('manage_users')
    else:
        form = UserForm()
    return render(request, 'admin/add_user.html', {'form': form})

@login_required
def edit_user(request, user_id):
    if not request.user.is_admin(): return redirect('dashboard')
    u = get_object_or_404(CustomUser, id=user_id)
    if request.method == 'POST':
        form = UserForm(request.POST, request.FILES, instance=u)
        if form.is_valid():
            form.save()
            messages.success(request, f"User {u.username} updated!")
            return redirect('manage_users')
    else:
        form = UserForm(instance=u)
    return render(request, 'admin/edit_user.html', {'form': form, 'edit_user': u})

@login_required
def delete_user(request, user_id):
    if not request.user.is_admin(): return redirect('dashboard')
    u = get_object_or_404(CustomUser, id=user_id)
    u.delete()
    messages.success(request, "User deleted!")
    return redirect('manage_users')

@login_required
def admin_roles(request):
    if not request.user.is_admin(): return redirect('dashboard')
    
    context = {
        'admin_count': CustomUser.objects.filter(role='ADMIN').count(),
        'hr_count': CustomUser.objects.filter(role='HR').count(),
        'employee_count': CustomUser.objects.filter(role='EMPLOYEE').count(),
    }
    return render(request, 'admin/roles.html', context)

@login_required
def admin_monitor(request):
    if not (request.user.is_admin() or request.user.is_hr()): return redirect('dashboard')
    logs = SystemLog.objects.all().order_by('-timestamp')[:50]
    return render(request, 'admin/monitor.html', {'logs': logs})

@login_required
def admin_reports(request):
    if not (request.user.is_admin() or request.user.is_hr()): return redirect('dashboard')
    dept_stats = CustomUser.objects.values('department').annotate(count=Count('id'))
    return render(request, 'admin/reports.html', {'dept_stats': dept_stats})

# HR Views
@login_required
def hr_track_projects(request):
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    projects = Project.objects.all()
    return render(request, 'hr/track_projects.html', {'projects': projects})

@login_required
def hr_announcements(request):
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    if request.method == 'POST':
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            ann = form.save(commit=False)
            ann.author = request.user
            ann.save()
            messages.success(request, "Announcement sent!")
    else:
        form = AnnouncementForm()
    announcements = Announcement.objects.all().order_by('-created_at')
    return render(request, 'hr/announcements.html', {'announcements': announcements, 'form': form})

@login_required
def hr_monitor(request):
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    from django.utils import timezone
    today = timezone.now().date()
    employees = CustomUser.objects.filter(role='EMPLOYEE').prefetch_related(
        Prefetch('attendance', queryset=Attendance.objects.filter(date=today), to_attr='today_attendance')
    )
    return render(request, 'hr/monitor.html', {'employees': employees})

@login_required
def hr_recruitment(request):
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    jobs = JobOpening.objects.all()
    if request.method == 'POST':
        form = JobOpeningForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Job posted!")
            return redirect('hr_recruitment')
    else:
        form = JobOpeningForm()
    return render(request, 'hr/recruitment.html', {'jobs': jobs, 'form': form})

@login_required
def hr_shifts(request):
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    if request.method == 'POST':
        emp_id = request.POST.get('employee_id')
        start = request.POST.get('start_time')
        end = request.POST.get('end_time')
        day = request.POST.get('day')
        s_type = request.POST.get('shift_type', 'DAY')
        emp = get_object_or_404(CustomUser, id=emp_id)
        Shift.objects.create(employee=emp, start_time=start, end_time=end, day_of_week=day, shift_type=s_type)
        messages.success(request, f"Shift assigned to {emp.username}")
        return redirect('hr_shifts')
    
    shifts = Shift.objects.all()
    employees = CustomUser.objects.filter(role='EMPLOYEE')
    return render(request, 'hr/shifts.html', {'shifts': shifts, 'employees': employees})

@login_required
def hr_documents(request):
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    if request.method == 'POST':
        title = request.POST.get('title')
        file = request.FILES.get('file')
        Document.objects.create(title=title, file=file, uploaded_by=request.user)
        messages.success(request, "Document uploaded!")
    docs = Document.objects.all()
    return render(request, 'hr/documents.html', {'docs': docs})

@login_required
def hr_leave_management(request):
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    leaves = LeaveRequest.objects.all().order_by('-applied_on')
    return render(request, 'hr/leave_management.html', {'leaves': leaves})

@login_required
def hr_approve_leave(request, leave_id):
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    leave.status = 'APPROVED'
    leave.save()
    messages.success(request, f"Leave for {leave.employee.username} approved!")
    return redirect('hr_leave_management')

@login_required
def hr_reject_leave(request, leave_id):
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    leave.status = 'REJECTED'
    leave.save()
    messages.warning(request, f"Leave for {leave.employee.username} rejected!")
    return redirect('hr_leave_management')

# Employee Views
@login_required
def employee_tasks(request):
    tasks = request.user.assigned_tasks.all()
    return render(request, 'employee/tasks.html', {'tasks': tasks})

@login_required
def update_task_progress(request, task_id):
    task = get_object_or_404(Task, id=task_id, assigned_to=request.user)
    if request.method == 'POST':
        task.progress = request.POST.get('progress', 0)
        task.status = request.POST.get('status', 'TODO')
        task.save()
        messages.success(request, "Task updated!")
    return redirect('employee_tasks')

@login_required
def attendance_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        today = timezone.now().date()
        att, _ = Attendance.objects.get_or_create(employee=request.user, date=today)
        if action == 'check_in' and not att.check_in:
            att.check_in = timezone.now()
            att.save()
        elif action == 'check_out' and not att.check_out:
            att.check_out = timezone.now()
            att.save()
    history = Attendance.objects.filter(employee=request.user).order_by('-date')
    return render(request, 'employee/attendance.html', {'history': history})

@login_required
def leave_application(request):
    if request.method == 'POST':
        form = LeaveRequestForm(request.POST)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.employee = request.user
            leave.save()
            messages.success(request, "Leave applied!")
            return redirect('leave_application')
    else:
        form = LeaveRequestForm()
    leaves = request.user.leave_requests.all().order_by('-applied_on')
    return render(request, 'employee/leave.html', {'leaves': leaves, 'form': form})

@login_required
def cancel_leave(request, leave_id):
    leave = get_object_or_404(LeaveRequest, id=leave_id, employee=request.user)
    if leave.status == 'PENDING':
        leave.status = 'CANCELLED'
        leave.save()
        messages.success(request, "Leave cancelled")
    return redirect('leave_application')

@login_required
def employee_performance(request):
    reviews = request.user.performance_reviews.all().order_by('-review_date')
    return render(request, 'employee/performance.html', {'reviews': reviews})

@login_required
def employee_profile(request):
    if request.method == 'POST':
        u = request.user
        u.first_name = request.POST.get('first_name')
        u.last_name = request.POST.get('last_name')
        u.email = request.POST.get('email')
        u.phone = request.POST.get('phone')
        if request.FILES.get('profile_pic'):
            u.profile_pic = request.FILES.get('profile_pic')
        u.save()
        messages.success(request, "Profile updated!")
    return render(request, 'employee/profile.html')

@login_required
def employee_feedback(request):
    if request.method == 'POST':
        subj = request.POST.get('subject')
        comm = request.POST.get('comment')
        Feedback.objects.create(employee=request.user, subject=subj, comment=comm)
        messages.success(request, "Feedback sent!")
    return render(request, 'employee/feedback.html')

@login_required
def report_preview(request, report_type):
    if not (request.user.is_admin() or request.user.is_hr()): return redirect('dashboard')
    
    context = {'report_type': report_type.title().replace('_', ' '), 'timestamp': timezone.now()}
    
    if report_type == 'attendance':
        context['records'] = Attendance.objects.all().order_by('-date')
        context['headers'] = ['Date', 'Employee', 'In', 'Out']
    elif report_type == 'projects':
        context['records'] = Project.objects.all()
        context['headers'] = ['Project Name', 'Start Date', 'End Date', 'Status']
        
    return render(request, 'admin/report_preview.html', context)
