"""
URL Configuration for University Project Submission Platform
Demonstrates: Clean URL patterns, namespacing, RESTful design
"""

from django.urls import path, include
from django.contrib.auth.views import (
    PasswordChangeView, PasswordChangeDoneView,
    PasswordResetView, PasswordResetDoneView,
    PasswordResetConfirmView, PasswordResetCompleteView
)

from . import views


# =============================================================================
# AUTHENTICATION URLS
# =============================================================================

auth_urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),

    # Password change (for logged-in users)
    path('password/change/',
         PasswordChangeView.as_view(
             template_name='registration/password_change.html'),
         name='password_change'),
    path('password/change/done/',
         PasswordChangeDoneView.as_view(
             template_name='registration/password_change_done.html'),
         name='password_change_done'),

    # Password reset (for forgotten passwords)
    path('password/reset/',
         PasswordResetView.as_view(
             template_name='registration/password_reset.html'),
         name='password_reset'),
    path('password/reset/done/',
         PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html'),
         name='password_reset_done'),
    path('password/reset/<uidb64>/<token>/',
         PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html'),
         name='password_reset_confirm'),
    path('password/reset/complete/',
         PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html'),
         name='password_reset_complete'),
]


# =============================================================================
# CLASSROOM URLS
# =============================================================================

classroom_urlpatterns = [
    # List and create
    path('', views.ClassroomListView.as_view(), name='classroom_list'),
    path('create/', views.ClassroomCreateView.as_view(), name='classroom_create'),
    path('join/', views.JoinClassroomView.as_view(), name='classroom_join'),

    # Detail, update, delete
    path('<int:pk>/', views.ClassroomDetailView.as_view(), name='classroom_detail'),
    path('<int:pk>/edit/', views.ClassroomUpdateView.as_view(),
         name='classroom_update'),
    path('<int:pk>/delete/', views.ClassroomDeleteView.as_view(),
         name='classroom_delete'),
    path('<int:pk>/leave/', views.LeaveClassroomView.as_view(),
         name='classroom_leave'),
    path('<int:pk>/regenerate-code/', views.RegenerateJoinCodeView.as_view(),
         name='classroom_regenerate_code'),

    # Member management
    path('<int:classroom_pk>/members/',
         views.ClassroomMemberListView.as_view(), name='classroom_members'),
    path('<int:classroom_pk>/members/<int:student_pk>/remove/',
         views.RemoveMemberView.as_view(), name='classroom_remove_member'),

    # Classroom-specific submissions (for teachers)
    path('<int:classroom_pk>/submissions/',
         views.ClassroomSubmissionListView.as_view(), name='classroom_submissions'),

    # Create submission within classroom
    path('<int:classroom_pk>/submit/',
         views.SubmissionCreateView.as_view(), name='submission_create'),
]


# =============================================================================
# SUBMISSION URLS
# =============================================================================

submission_urlpatterns = [
    # List all submissions (role-aware)
    path('', views.SubmissionListView.as_view(), name='submission_list'),

    # Teacher-specific submission list with all classrooms
    path('teacher/', views.TeacherSubmissionListView.as_view(),
         name='teacher_submissions'),

    # Detail, update, delete
    path('<int:pk>/', views.SubmissionDetailView.as_view(),
         name='submission_detail'),
    path('<int:pk>/edit/', views.SubmissionUpdateView.as_view(),
         name='submission_update'),
    path('<int:pk>/delete/', views.SubmissionDeleteView.as_view(),
         name='submission_delete'),

    # Submit action (change status from DRAFT to SUBMITTED)
    path('<int:pk>/submit/', views.SubmissionSubmitView.as_view(),
         name='submission_submit'),

    # Grading (teacher only)
    path('<int:pk>/grade/', views.GradeSubmissionView.as_view(),
         name='submission_grade'),
]


# =============================================================================
# MAIN URL PATTERNS
# =============================================================================

urlpatterns = [
    # Dashboard (landing page after login)
    path('', views.DashboardView.as_view(), name='dashboard'),

    # Authentication
    path('auth/', include(auth_urlpatterns)),

    # Classrooms
    path('classrooms/', include(classroom_urlpatterns)),

    # Submissions
    path('submissions/', include(submission_urlpatterns)),
]
