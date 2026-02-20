from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('manage-users/', views.manage_users, name='manage_users'),
    path('add-user/', views.add_user, name='add_user'),
    path('edit-user/<int:user_id>/', views.edit_user, name='edit_user'),
    path('delete-user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('company-admin/roles/', views.admin_roles, name='admin_roles'),
    path('company-admin/monitor/', views.admin_monitor, name='admin_monitor'),
    path('company-admin/reports/', views.admin_reports, name='admin_reports'),
    path('company-admin/reports/preview/<str:report_type>/', views.report_preview, name='report_preview'),
    # HR
    path('hr/projects/', views.hr_track_projects, name='hr_track_projects'),
    path('hr/announcements/', views.hr_announcements, name='hr_announcements'),
    path('hr/monitor/', views.hr_monitor, name='hr_monitor'),
    path('hr/recruitment/', views.hr_recruitment, name='hr_recruitment'),
    path('hr/shifts/', views.hr_shifts, name='hr_shifts'),
    path('hr/documents/', views.hr_documents, name='hr_documents'),
    path('hr/leaves/', views.hr_leave_management, name='hr_leave_management'),
    path('hr/leaves/approve/<int:leave_id>/', views.hr_approve_leave, name='hr_approve_leave'),
    path('hr/leaves/reject/<int:leave_id>/', views.hr_reject_leave, name='hr_reject_leave'),
    # Employee
    path('employee/tasks/', views.employee_tasks, name='employee_tasks'),
    path('employee/tasks/update/<int:task_id>/', views.update_task_progress, name='update_task_progress'),
    path('employee/attendance/', views.attendance_view, name='attendance'),
    path('employee/leave/', views.leave_application, name='leave_application'),
    path('employee/leave/cancel/<int:leave_id>/', views.cancel_leave, name='cancel_leave'),
    path('employee/performance/', views.employee_performance, name='employee_performance'),
    path('employee/profile/', views.employee_profile, name='employee_profile'),
    path('employee/feedback/', views.employee_feedback, name='employee_feedback'),
]
