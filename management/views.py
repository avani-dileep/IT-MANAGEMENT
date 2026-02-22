from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import login, authenticate, logout
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import CustomUser, Project, Task, Announcement, JobOpening, Candidate, LeaveRequest, Attendance, Shift, Document, Feedback, PerformanceReview, SystemLog
from .forms import UserForm, LeaveRequestForm, JobOpeningForm, AnnouncementForm, PerformanceReviewForm, TaskForm, ProjectForm, FeedbackForm
from django.db.models import Count, Prefetch, Q

def login_view(request):
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(username=u, password=p)
        if user:
            login(request, user)
            # Capture IP address
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')
            
            SystemLog.objects.create(user=user, action="Logged in", ip_address=ip)
            return redirect('dashboard')
        messages.error(request, "Invalid credentials")
    return render(request, 'login.html')

def guest_page(request):
    """Public-facing company landing page — no login required."""
    job_openings = JobOpening.objects.filter(is_active=True).order_by('-posted_on')
    return render(request, 'guest.html', {'job_openings': job_openings})

def apply_job(request):
    """AJAX endpoint — handle job application form submission from guest page."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        job_id = request.POST.get('job_id', '').strip()
        resume = request.FILES.get('resume')

        if not name or not email or not resume:
            return JsonResponse({'success': False, 'error': 'Name, email, and resume are required.'})

        try:
            if job_id:
                job = get_object_or_404(JobOpening, id=job_id, is_active=True)
            else:
                # General application — attach to the first open job or create a generic one
                job = JobOpening.objects.filter(is_active=True).first()
                if not job:
                    return JsonResponse({'success': False, 'error': 'No open positions available right now.'})

            Candidate.objects.create(job=job, name=name, email=email, resume=resume)
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request.'})


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
            'recent_completed': Project.objects.filter(status='COMPLETED').order_by('-id')[:5],
            'recent_logs': SystemLog.objects.all().order_by('-timestamp')[:5],
        }
        return render(request, 'dashboards/admin.html', context)
    elif user.is_hr():
        projects = Project.objects.all()
        leaves = LeaveRequest.objects.all()
        
        if user.department:
            projects = projects.filter(team_members__department=user.department).distinct()
            leaves = leaves.filter(employee__department=user.department)

        context = {
            'active_projects': projects.filter(status='ONGOING').count(),
            'pending_leaves': leaves.filter(status='PENDING').count(),
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
    dept_filter = request.GET.get('dept')
    users = CustomUser.objects.all().order_by('-date_joined')
    if dept_filter:
        users = users.filter(department=dept_filter)
    
    context = {
        'users': users,
        'depts': CustomUser.DEPT_CHOICES,
        'selected_dept': dept_filter
    }
    return render(request, 'admin/manage_users.html', context)

@login_required
def add_user(request):
    if not request.user.is_admin(): return redirect('dashboard')
    if request.method == 'POST':
        form = UserForm(request.POST, request.FILES)
        if form.is_valid():
            raw_password = form.cleaned_data.get('password')
            user = form.save(commit=False)
            
            # Enforce HR Designation Format
            if user.role == 'HR' and user.department:
                user.designation = f"{user.get_department_display()} HR"
            
            # user.date_of_joining = timezone.now().date()
            
            user.save()
            
            # Send Premium Onboarding Email
            if raw_password and user.email:
                subject = f"Welcome to the Team, {user.first_name or user.username}! | Official Login Credentials"
                
                context = {
                    'user': user,
                    'password': raw_password,
                    'login_url': request.build_absolute_uri('/login/')
                }
                
                html_message = render_to_string('emails/welcome_email.html', context)
                plain_message = strip_tags(html_message)
                
                try:
                    send_mail(
                        subject,
                        plain_message,
                        'gouriks269@gmail.com',
                        [user.email],
                        html_message=html_message
                    )
                    messages.success(request, f"Premium Welcome Email sent to {user.email}!")
                except Exception as e:
                    messages.warning(request, f"Employee added, but email failed. Error: {str(e)}")
            else:
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
            user = form.save(commit=False)
            if user.role == 'HR' and user.department:
                user.designation = f"{user.get_department_display()} HR"
            user.save()
            messages.success(request, f"User {user.username} updated!")
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
def admin_monitor(request):
    if not (request.user.is_admin() or request.user.is_hr()): return redirect('dashboard')
    logs = SystemLog.objects.all().order_by('-timestamp')[:50]
    return render(request, 'admin/monitor.html', {'logs': logs})

@login_required
def admin_project_status(request):
    if not request.user.is_admin(): return redirect('dashboard')
    employees = CustomUser.objects.filter(role='EMPLOYEE').prefetch_related('projects', 'assigned_tasks')
    # Attach display label to each employee for reliable template rendering
    for emp in employees:
        emp.department_label = emp.get_department_display() if emp.department else 'No Department'
    return render(request, 'admin/project_status.html', {'employees': employees})

@login_required
def admin_reports(request):
    if not (request.user.is_admin() or request.user.is_hr()): return redirect('dashboard')
    dept_stats = CustomUser.objects.values('department').annotate(count=Count('id'))
    return render(request, 'admin/reports.html', {'dept_stats': dept_stats})

# HR Views
@login_required
def hr_track_projects(request):
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    projects = Project.objects.all().prefetch_related('tasks', 'team_members')
    if not request.user.is_admin():
        projects = projects.filter(team_members__department=request.user.department).distinct()
    return render(request, 'hr/track_projects.html', {'projects': projects})

@login_required
def add_project(request):
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save()
            messages.success(request, f"Project '{project.name}' has been scheduled successfully.")
            return redirect('hr_track_projects')
    else:
        form = ProjectForm()
    
    # Filter selection lists for HR
    if not request.user.is_admin() and request.user.is_hr():
        if 'team_members' in form.fields:
            form.fields['team_members'].queryset = CustomUser.objects.filter(department=request.user.department, role='EMPLOYEE')
        if 'manager' in form.fields:
            form.fields['manager'].queryset = CustomUser.objects.filter(department=request.user.department).exclude(role='ADMIN')

    return render(request, 'hr/add_project.html', {'form': form})

@login_required
def edit_project(request, project_id):
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    project = get_object_or_404(Project, id=project_id)
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, f"Project '{project.name}' updated.")
            return redirect('hr_track_projects')
    else:
        form = ProjectForm(instance=project)
    
    # Filter selection lists for HR
    if not request.user.is_admin() and request.user.is_hr():
        if 'team_members' in form.fields:
            form.fields['team_members'].queryset = CustomUser.objects.filter(department=request.user.department, role='EMPLOYEE')
        if 'manager' in form.fields:
            form.fields['manager'].queryset = CustomUser.objects.filter(department=request.user.department).exclude(role='ADMIN')

    return render(request, 'hr/add_project.html', {'form': form, 'project': project, 'is_edit': True})

@login_required
def complete_project(request, project_id):
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    project = get_object_or_404(Project, id=project_id)
    project.status = 'COMPLETED'
    project.save()
    messages.success(request, f"Project '{project.name}' marked as completed. Admin has been notified.")
    # In a real system you might send an email or internal notification here
    SystemLog.objects.create(user=request.user, action=f"Marked project {project.name} as COMPLETED")
    return redirect('hr_track_projects')

@login_required
def add_task(request, project_id):
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    project = get_object_or_404(Project, id=project_id)
    if request.method == 'POST':
        form = TaskForm(request.POST)
        # Make project field not required since we set it manually
        if 'project' in form.fields:
            form.fields['project'].required = False
        
        if form.is_valid():
            task = form.save(commit=False)
            task.project = project
            task.save()
            messages.success(request, f"Task '{task.title}' assigned to {task.assigned_to.get_full_name()}.")
            return redirect('hr_track_projects')
    else:
        form = TaskForm()
        if 'project' in form.fields: del form.fields['project']
    
    # Always filter assignees to project members
    if 'assigned_to' in form.fields:
        form.fields['assigned_to'].queryset = project.team_members.all()
        if not project.team_members.exists():
            messages.warning(request, "This project has no team members assigned. Please add team members first.")

    return render(request, 'hr/add_task.html', {'form': form, 'project': project})

@login_required
def hr_announcements(request):
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    if request.method == 'POST':
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.author = request.user
            announcement.save()
            messages.success(request, "Official announcement broadcast successfully!")
            return redirect('hr_announcements')
    else:
        form = AnnouncementForm()
    
    announcements = Announcement.objects.all().order_by('-created_at')
    return render(request, 'hr/announcements.html', {'form': form, 'announcements': announcements})

@login_required
def edit_announcement(request, ann_id):
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    ann = get_object_or_404(Announcement, id=ann_id)
    if request.method == 'POST':
        form = AnnouncementForm(request.POST, instance=ann)
        if form.is_valid():
            form.save()
            messages.success(request, "Announcement updated successfully.")
            return redirect('hr_announcements')
    else:
        form = AnnouncementForm(instance=ann)
    return render(request, 'hr/edit_announcement.html', {'form': form, 'announcement': ann})

@login_required
def hr_monitor(request):
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    from django.utils import timezone
    today = timezone.now().date()
    employees = CustomUser.objects.filter(role='EMPLOYEE')
    
    if not request.user.is_admin():
        employees = employees.filter(department=request.user.department)
        
    employees = employees.prefetch_related(
        Prefetch('attendance', queryset=Attendance.objects.filter(date=today), to_attr='today_attendance'),
        Prefetch('shifts', queryset=Shift.objects.filter(day_of_week=today.weekday()), to_attr='today_shift'),
        'projects',
        'assigned_tasks__project'
    )
    return render(request, 'hr/monitor.html', {'employees': employees})

@login_required
def hr_recruitment(request):
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')

    if request.method == 'POST':
        form = JobOpeningForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Job posted successfully!")
            return redirect('hr_recruitment')
    else:
        form = JobOpeningForm()

    # Fetch all jobs with candidates prefetched in one query
    jobs = list(JobOpening.objects.prefetch_related('candidates').order_by('-posted_on'))

    # Compute counts in Python from the prefetch cache (list() forces cache evaluation)
    for job in jobs:
        cands = list(job.candidates.all())   # reads from prefetch cache — no extra DB hits
        job.total_count     = len(cands)
        job.applied_count   = sum(1 for c in cands if c.status == 'APPLIED')
        job.interview_count = sum(1 for c in cands if c.status == 'INTERVIEW_SCHEDULED')
        job.hired_count     = sum(1 for c in cands if c.status == 'HIRED')
        job.rejected_count  = sum(1 for c in cands if c.status == 'REJECTED')

    return render(request, 'hr/recruitment.html', {
        'jobs': jobs,
        'form': form,
        'status_choices': [
            ('APPLIED', 'Applied'),
            ('INTERVIEW_SCHEDULED', 'Interview Scheduled'),
            ('HIRED', 'Hired'),
            ('REJECTED', 'Rejected'),
        ],
    })

@login_required
def update_candidate_status(request, candidate_id):
    """HR updates the status of an applicant. Returns JSON for AJAX calls."""
    if not (request.user.is_hr() or request.user.is_admin()):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
    if request.method == 'POST':
        candidate = get_object_or_404(Candidate, id=candidate_id)
        new_status = request.POST.get('status')
        valid = ['APPLIED', 'INTERVIEW_SCHEDULED', 'HIRED', 'REJECTED']
        if new_status in valid:
            candidate.status = new_status
            candidate.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'status': new_status, 'label': candidate.get_status_display()})
            messages.success(request, f"Status for {candidate.name} updated.")
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Invalid status.'})
    return redirect('hr_recruitment')

@login_required
def edit_job(request, job_id):
    """Edit an existing job opening (title, description, requirements, active status)."""
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    job = get_object_or_404(JobOpening, id=job_id)
    if request.method == 'POST':
        form = JobOpeningForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            messages.success(request, f"Job '{job.title}' updated successfully.")
        else:
            messages.error(request, "Please fix the errors below.")
    return redirect('hr_recruitment')

@login_required
def toggle_job_status(request, job_id):
    """Close (deactivate) or reopen a job opening via POST."""
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    if request.method == 'POST':
        job = get_object_or_404(JobOpening, id=job_id)
        job.is_active = not job.is_active
        job.save()
        state = "reopened" if job.is_active else "closed"
        messages.success(request, f"Job '{job.title}' has been {state}.")
    return redirect('hr_recruitment')

@login_required
def delete_job(request, job_id):
    """Permanently delete a job opening and all its candidates."""
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    if request.method == 'POST':
        job = get_object_or_404(JobOpening, id=job_id)
        title = job.title
        job.delete()
        messages.success(request, f"Job '{title}' and all its applications have been deleted.")
    return redirect('hr_recruitment')



@login_required
def hr_shifts(request):
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    if request.method == 'POST':
        # ... POST handling ...
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
    
    if not request.user.is_admin():
        shifts = shifts.filter(employee__department=request.user.department)
        employees = employees.filter(department=request.user.department)
        
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
    if not (request.user.is_hr() or request.user.is_admin()):
        return redirect('dashboard')
    
    leaves = LeaveRequest.objects.select_related('employee').all().order_by('-applied_on')
    
    if not request.user.is_admin():
        leaves = leaves.filter(employee__department=request.user.department)
        
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
    tasks = request.user.assigned_tasks.all().select_related('project')
    return render(request, 'employee/tasks.html', {'tasks': tasks})

@login_required
def update_task_progress(request, task_id):
    task = get_object_or_404(Task, id=task_id, assigned_to=request.user)
    if request.method == 'POST':
        try:
            task.progress = int(request.POST.get('progress', 0))
        except (ValueError, TypeError):
            task.progress = 0
        task.status = request.POST.get('status', 'TODO')
        if 'report' in request.FILES:
            task.report = request.FILES['report']
        if task.status == 'DONE':
            task.progress = 100
        task.save()
        
        # Check if all tasks in the project are done
        project = task.project
        all_tasks_done = not project.tasks.exclude(status='DONE').exists()
        if all_tasks_done:
            messages.info(request, f"All tasks for project '{project.name}' are completed! Management has been notified.")
        
        messages.success(request, f"Progress for '{task.title}' updated to {task.progress}%")
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
    # Try to get the shift for today's weekday first, then fall back to any assigned shift
    today_shift = request.user.shifts.filter(day_of_week=timezone.now().weekday()).first()
    if not today_shift:
        today_shift = request.user.shifts.first()
    return render(request, 'employee/attendance.html', {'history': history, 'today_shift': today_shift})

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

# Announcement Views
@login_required
def employee_announcements(request):
    announcements = Announcement.objects.all().order_by('-created_at')
    return render(request, 'employee/announcements.html', {'announcements': announcements})

# Feedback Views
@login_required
def employee_feedback(request):
    if request.method == 'POST':
        form = FeedbackForm(request.POST)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.employee = request.user
            feedback.save()
            messages.success(request, "Your feedback has been submitted to your HR manager.")
            return redirect('employee_feedback')
    else:
        form = FeedbackForm()
    
    feedbacks = Feedback.objects.filter(employee=request.user).order_by('-created_at')
    return render(request, 'employee/feedback.html', {'form': form, 'feedbacks': feedbacks})

@login_required
def hr_manage_feedback(request):
    if not (request.user.is_hr() or request.user.is_admin()): return redirect('dashboard')
    
    feedbacks = Feedback.objects.select_related('employee').all()
    if not request.user.is_admin():
        feedbacks = feedbacks.filter(employee__department=request.user.department)
    
    feedbacks = feedbacks.order_by('is_resolved', '-created_at')
    
    if request.method == 'POST':
        fid = request.POST.get('feedback_id')
        response = request.POST.get('hr_response')
        feedback = get_object_or_404(Feedback, id=fid)
        feedback.hr_response = response
        feedback.responded_by = request.user
        feedback.is_resolved = True
        feedback.save()
        messages.success(request, f"Responded to feedback from {feedback.employee.username}")
        return redirect('hr_manage_feedback')
        
    return render(request, 'hr/feedback_management.html', {'feedbacks': feedbacks})

@login_required
def admin_feedback_view(request):
    if not request.user.is_admin(): return redirect('dashboard')
    feedbacks = Feedback.objects.all().order_by('-created_at')
    return render(request, 'admin/feedback_list.html', {'feedbacks': feedbacks})
