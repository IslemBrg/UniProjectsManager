"""
Views for University Project Submission Platform
Demonstrates: Class-Based Views, Mixins, Permission enforcement, Pagination, Filtering
"""

from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, FormView, TemplateView
)
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.http import HttpResponseForbidden, Http404
from django.db.models import Count, Avg, Q

from .models import User, Classroom, ClassroomMembership, ProjectSubmission
from .forms import (
    CustomUserCreationForm, CustomAuthenticationForm,
    ClassroomCreateForm, ClassroomUpdateForm, JoinClassroomForm,
    ProjectSubmissionCreateForm, ProjectSubmissionUpdateForm,
    ProjectSubmitForm, GradeSubmissionForm,
    SubmissionFilterForm, ClassroomFilterForm
)


# =============================================================================
# MIXINS FOR PERMISSION CONTROL
# =============================================================================

class TeacherRequiredMixin(UserPassesTestMixin):
    """Mixin that requires the user to be a teacher"""

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_teacher

    def handle_no_permission(self):
        messages.error(
            self.request, 'You must be a teacher to access this page.')
        return redirect('dashboard')


class StudentRequiredMixin(UserPassesTestMixin):
    """Mixin that requires the user to be a student (not a teacher)"""

    def test_func(self):
        return self.request.user.is_authenticated and not self.request.user.is_teacher

    def handle_no_permission(self):
        messages.error(
            self.request, 'This page is only accessible to students.')
        return redirect('dashboard')


class ClassroomOwnerMixin(UserPassesTestMixin):
    """Mixin that requires the user to be the owner of the classroom"""

    def test_func(self):
        classroom = self.get_object()
        return self.request.user == classroom.teacher

    def handle_no_permission(self):
        messages.error(
            self.request, 'You do not have permission to modify this classroom.')
        return redirect('classroom_list')


class ClassroomMemberMixin(UserPassesTestMixin):
    """Mixin that requires the user to be a member of the classroom"""

    def get_classroom(self):
        """Override this method to get the classroom object"""
        raise NotImplementedError

    def test_func(self):
        classroom = self.get_classroom()
        user = self.request.user

        # Teachers who own the classroom have access
        if user.is_teacher and classroom.teacher == user:
            return True

        # Students who are members have access
        return classroom.is_student_member(user)

    def handle_no_permission(self):
        messages.error(self.request, 'You are not a member of this classroom.')
        return redirect('classroom_list')


class SubmissionAccessMixin(UserPassesTestMixin):
    """Mixin that controls access to project submissions"""

    def test_func(self):
        submission = self.get_object()
        return submission.can_user_view(self.request.user)

    def handle_no_permission(self):
        messages.error(
            self.request, 'You do not have permission to view this submission.')
        return redirect('dashboard')


class SubmissionEditMixin(UserPassesTestMixin):
    """Mixin that controls edit access to project submissions"""

    def test_func(self):
        submission = self.get_object()
        return submission.can_user_edit(self.request.user)

    def handle_no_permission(self):
        if not self.get_object().is_draft:
            messages.error(
                self.request, 'This submission has been submitted and cannot be edited.')
        else:
            messages.error(
                self.request, 'You do not have permission to edit this submission.')
        return redirect('submission_detail', pk=self.get_object().pk)


# =============================================================================
# AUTHENTICATION VIEWS
# =============================================================================

class RegisterView(SuccessMessageMixin, CreateView):
    """User registration view for both students and teachers"""
    model = User
    form_class = CustomUserCreationForm
    template_name = 'registration/register.html'
    success_url = reverse_lazy('login')
    success_message = 'Account created successfully! Please log in.'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)


class CustomLoginView(LoginView):
    """Custom login view with Bootstrap styling"""
    form_class = CustomAuthenticationForm
    template_name = 'registration/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy('dashboard')

    def form_valid(self, form):
        messages.success(
            self.request, f'Welcome back, {form.get_user().get_full_name() or form.get_user().username}!')
        return super().form_valid(form)


class CustomLogoutView(LogoutView):
    """Custom logout view"""
    next_page = reverse_lazy('login')

    def dispatch(self, request, *args, **kwargs):
        messages.info(request, 'You have been logged out.')
        return super().dispatch(request, *args, **kwargs)


# =============================================================================
# DASHBOARD VIEWS
# =============================================================================

class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Role-aware dashboard that shows different content for teachers and students.
    """
    template_name = 'dashboard.html'

    def get_template_names(self):
        if self.request.user.is_teacher:
            return ['dashboard_teacher.html']
        return ['dashboard_student.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.is_teacher:
            # Teacher dashboard context
            classrooms = Classroom.objects.for_teacher(user).annotate(
                student_count=Count('memberships', distinct=True),
                drafts_count=Count('submissions', filter=Q(
                    submissions__status=ProjectSubmission.Status.DRAFT), distinct=True),
                submitted_count=Count('submissions', filter=Q(
                    submissions__status=ProjectSubmission.Status.SUBMITTED), distinct=True),
            )
            context['classrooms'] = classrooms[:5]
            context['total_classrooms'] = classrooms.count()
            context['total_students'] = ClassroomMembership.objects.filter(
                classroom__teacher=user
            ).values('student').distinct().count()
        else:
            # Student dashboard context
            memberships = ClassroomMembership.objects.filter(
                student=user).select_related('classroom')
            context['memberships'] = memberships[:5]
            context['total_classrooms'] = memberships.count()

            submissions = ProjectSubmission.objects.for_student(user)
            context['submissions'] = submissions[:5]
            context['draft_count'] = submissions.filter(
                status=ProjectSubmission.Status.DRAFT).count()
            context['submitted_count'] = submissions.filter(
                status=ProjectSubmission.Status.SUBMITTED).count()
            context['graded_count'] = submissions.exclude(
                grade__isnull=True).count()

            # Calculate average grade
            avg_grade = submissions.exclude(
                grade__isnull=True).aggregate(avg=Avg('grade'))
            context['average_grade'] = avg_grade['avg']

        return context


# =============================================================================
# CLASSROOM VIEWS
# =============================================================================

class ClassroomListView(LoginRequiredMixin, ListView):
    """
    List classrooms based on user role.
    Teachers see their owned classrooms.
    Students see classrooms they've joined.
    """
    model = Classroom
    template_name = 'classrooms/classroom_list.html'
    context_object_name = 'classrooms'
    paginate_by = 12

    def get_queryset(self):
        user = self.request.user

        if user.is_teacher:
            queryset = Classroom.objects.for_teacher(user)
        else:
            queryset = Classroom.objects.for_student(user)

        # Apply filters
        self.filter_form = ClassroomFilterForm(self.request.GET)
        queryset = self.filter_form.filter_queryset(queryset)

        # Annotate with counts
        queryset = queryset.annotate(
            student_count=Count('memberships', distinct=True),
            submission_count=Count('submissions', filter=Q(
                submissions__status=ProjectSubmission.Status.SUBMITTED), distinct=True)
        )

        return queryset.select_related('teacher')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        context['is_teacher'] = self.request.user.is_teacher
        return context


class ClassroomDetailView(LoginRequiredMixin, ClassroomMemberMixin, DetailView):
    """
    Detailed view of a classroom.
    Shows different information based on user role.
    """
    model = Classroom
    template_name = 'classrooms/classroom_detail.html'
    context_object_name = 'classroom'

    def get_classroom(self):
        return self.get_object()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        classroom = self.get_object()
        user = self.request.user

        context['is_owner'] = user.is_teacher and classroom.teacher == user
        context['is_member'] = classroom.is_student_member(user)

        # Get members
        context['members'] = ClassroomMembership.objects.filter(
            classroom=classroom
        ).select_related('student')[:10]
        context['member_count'] = classroom.get_student_count()

        if user.is_teacher and classroom.teacher == user:
            # Teacher sees all submissions
            context['submissions'] = ProjectSubmission.objects.for_classroom(
                classroom, user).select_related('created_by').prefetch_related('collaborators')[:10]
        else:
            # Student sees only their own submission
            context['my_submission'] = ProjectSubmission.objects.filter(
                classroom=classroom,
                collaborators=user
            ).first()

        return context


class ClassroomCreateView(LoginRequiredMixin, TeacherRequiredMixin, SuccessMessageMixin, CreateView):
    """Create a new classroom (teachers only)"""
    model = Classroom
    form_class = ClassroomCreateForm
    template_name = 'classrooms/classroom_form.html'
    success_message = 'Classroom "%(title)s" created successfully!'

    def form_valid(self, form):
        form.instance.teacher = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create New Classroom'
        context['submit_text'] = 'Create Classroom'
        return context


class ClassroomUpdateView(LoginRequiredMixin, ClassroomOwnerMixin, SuccessMessageMixin, UpdateView):
    """Update classroom details (owner only)"""
    model = Classroom
    form_class = ClassroomUpdateForm
    template_name = 'classrooms/classroom_form.html'
    success_message = 'Classroom updated successfully!'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Classroom'
        context['submit_text'] = 'Save Changes'
        return context


class ClassroomDeleteView(LoginRequiredMixin, ClassroomOwnerMixin, SuccessMessageMixin, DeleteView):
    """Delete a classroom (owner only)"""
    model = Classroom
    template_name = 'classrooms/classroom_confirm_delete.html'
    success_url = reverse_lazy('classroom_list')
    success_message = 'Classroom deleted successfully!'

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)


class JoinClassroomView(LoginRequiredMixin, StudentRequiredMixin, SuccessMessageMixin, FormView):
    """Join a classroom using a join code (students only)"""
    form_class = JoinClassroomForm
    template_name = 'classrooms/join_classroom.html'
    success_message = 'Successfully joined "%(classroom)s"!'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        membership = form.save()
        self.classroom = membership.classroom
        return super().form_valid(form)

    def get_success_message(self, cleaned_data):
        return self.success_message % {'classroom': self.classroom.title}

    def get_success_url(self):
        return reverse('classroom_detail', kwargs={'pk': self.classroom.pk})


class LeaveClassroomView(LoginRequiredMixin, StudentRequiredMixin, DeleteView):
    """Leave a classroom (students only)"""
    model = ClassroomMembership
    template_name = 'classrooms/leave_classroom_confirm.html'

    def get_object(self, queryset=None):
        return get_object_or_404(
            ClassroomMembership,
            classroom_id=self.kwargs['pk'],
            student=self.request.user
        )

    def get_success_url(self):
        messages.success(self.request, 'You have left the classroom.')
        return reverse_lazy('classroom_list')


class RegenerateJoinCodeView(LoginRequiredMixin, ClassroomOwnerMixin, UpdateView):
    """Regenerate the join code for a classroom (owner only)"""
    model = Classroom
    fields = []

    def form_valid(self, form):
        self.object.regenerate_join_code()
        messages.success(
            self.request, f'New join code generated: {self.object.join_code}')
        return redirect('classroom_detail', pk=self.object.pk)


# =============================================================================
# PROJECT SUBMISSION VIEWS
# =============================================================================

class SubmissionListView(LoginRequiredMixin, ListView):
    """
    List project submissions based on user role.
    Supports filtering and pagination.
    """
    model = ProjectSubmission
    template_name = 'submissions/submission_list.html'
    context_object_name = 'submissions'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user

        if user.is_teacher:
            queryset = ProjectSubmission.objects.for_teacher(user)
        else:
            queryset = ProjectSubmission.objects.for_student(user)

        # Apply filters
        self.filter_form = SubmissionFilterForm(self.request.GET, user=user)
        queryset = self.filter_form.filter_queryset(queryset)

        return queryset.select_related('classroom', 'created_by').prefetch_related('collaborators')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        context['is_teacher'] = self.request.user.is_teacher
        return context


class SubmissionDetailView(LoginRequiredMixin, SubmissionAccessMixin, DetailView):
    """View submission details"""
    model = ProjectSubmission
    template_name = 'submissions/submission_detail.html'
    context_object_name = 'submission'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        submission = self.get_object()
        user = self.request.user

        context['can_edit'] = submission.can_user_edit(user)
        context['can_grade'] = (
            user.is_teacher and
            submission.classroom.teacher == user and
            submission.is_submitted
        )
        context['is_collaborator'] = submission.collaborators.filter(
            pk=user.pk).exists()

        return context


class SubmissionCreateView(LoginRequiredMixin, StudentRequiredMixin, SuccessMessageMixin, CreateView):
    """Create a new project submission"""
    model = ProjectSubmission
    form_class = ProjectSubmissionCreateForm
    template_name = 'submissions/submission_form.html'
    success_message = 'Project submission created successfully!'

    def dispatch(self, request, *args, **kwargs):
        self.classroom = get_object_or_404(
            Classroom, pk=kwargs['classroom_pk'])

        # Check if user is a member of the classroom
        if not self.classroom.is_student_member(request.user):
            messages.error(
                request, 'You must be a member of this classroom to submit a project.')
            return redirect('classroom_detail', pk=self.classroom.pk)

        # Check if user already has a submission
        if ProjectSubmission.objects.filter(
            classroom=self.classroom,
            created_by=request.user
        ).exists():
            messages.error(
                request, 'You already have a submission in this classroom.')
            return redirect('classroom_detail', pk=self.classroom.pk)

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['classroom'] = self.classroom
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['classroom'] = self.classroom
        context['title'] = 'Create Project Submission'
        context['submit_text'] = 'Save as Draft'
        return context

    def get_success_url(self):
        return reverse('submission_detail', kwargs={'pk': self.object.pk})


class SubmissionUpdateView(LoginRequiredMixin, SubmissionEditMixin, SuccessMessageMixin, UpdateView):
    """Update a draft submission"""
    model = ProjectSubmission
    form_class = ProjectSubmissionUpdateForm
    template_name = 'submissions/submission_form.html'
    success_message = 'Project submission updated successfully!'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['classroom'] = self.object.classroom
        context['title'] = 'Edit Project Submission'
        context['submit_text'] = 'Save Changes'
        return context

    def get_success_url(self):
        return reverse('submission_detail', kwargs={'pk': self.object.pk})


class SubmissionDeleteView(LoginRequiredMixin, SubmissionEditMixin, SuccessMessageMixin, DeleteView):
    """Delete a draft submission"""
    model = ProjectSubmission
    template_name = 'submissions/submission_confirm_delete.html'
    success_message = 'Project submission deleted successfully!'

    def get_success_url(self):
        return reverse('classroom_detail', kwargs={'pk': self.object.classroom.pk})

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)


class SubmissionSubmitView(LoginRequiredMixin, SubmissionEditMixin, FormView):
    """Submit a project (changes status from DRAFT to SUBMITTED)"""
    form_class = ProjectSubmitForm
    template_name = 'submissions/submission_submit_confirm.html'

    def dispatch(self, request, *args, **kwargs):
        self.submission = get_object_or_404(ProjectSubmission, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_object(self):
        return self.submission

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['submission'] = self.submission
        return context

    def form_valid(self, form):
        if self.submission.submit():
            messages.success(
                self.request, 'Project submitted successfully! It is now visible to your teacher.')
        else:
            messages.error(
                self.request, 'Unable to submit project. It may have already been submitted.')
        return redirect('submission_detail', pk=self.submission.pk)


# =============================================================================
# GRADING VIEWS (TEACHER ONLY)
# =============================================================================

class TeacherSubmissionListView(LoginRequiredMixin, TeacherRequiredMixin, ListView):
    """
    List all submissions for a teacher's classrooms.
    Supports filtering and pagination.
    """
    model = ProjectSubmission
    template_name = 'submissions/teacher_submission_list.html'
    context_object_name = 'submissions'
    paginate_by = 20

    def get_queryset(self):
        queryset = ProjectSubmission.objects.for_teacher(self.request.user)

        # Apply filters
        self.filter_form = SubmissionFilterForm(
            self.request.GET, user=self.request.user)
        queryset = self.filter_form.filter_queryset(queryset)

        return queryset.select_related('classroom', 'created_by').prefetch_related('collaborators')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form

        # Statistics
        all_submissions = ProjectSubmission.objects.for_teacher(
            self.request.user)
        context['total_submissions'] = all_submissions.count()
        context['pending_count'] = all_submissions.filter(
            status=ProjectSubmission.Status.SUBMITTED,
            grade__isnull=True
        ).count()
        context['graded_count'] = all_submissions.exclude(
            grade__isnull=True).count()

        return context


class ClassroomSubmissionListView(LoginRequiredMixin, TeacherRequiredMixin, ListView):
    """
    List submissions for a specific classroom.
    Supports filtering and pagination.
    """
    model = ProjectSubmission
    template_name = 'submissions/classroom_submission_list.html'
    context_object_name = 'submissions'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        self.classroom = get_object_or_404(
            Classroom,
            pk=kwargs['classroom_pk'],
            teacher=request.user
        )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = ProjectSubmission.objects.filter(classroom=self.classroom)

        # Apply filters
        self.filter_form = SubmissionFilterForm(
            self.request.GET, user=self.request.user)
        queryset = self.filter_form.filter_queryset(queryset)

        return queryset.select_related('created_by').prefetch_related('collaborators')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['classroom'] = self.classroom
        context['filter_form'] = self.filter_form

        # Statistics for this classroom
        all_submissions = ProjectSubmission.objects.filter(
            classroom=self.classroom)
        context['total_submissions'] = all_submissions.count()
        context['pending_count'] = all_submissions.filter(
            status=ProjectSubmission.Status.SUBMITTED,
            grade__isnull=True
        ).count()
        context['graded_count'] = all_submissions.exclude(
            grade__isnull=True).count()

        return context


class GradeSubmissionView(LoginRequiredMixin, TeacherRequiredMixin, SuccessMessageMixin, UpdateView):
    """Grade a submitted project"""
    model = ProjectSubmission
    form_class = GradeSubmissionForm
    template_name = 'submissions/grade_form.html'
    success_message = 'Grade assigned successfully!'

    def dispatch(self, request, *args, **kwargs):
        submission = self.get_object()

        # Verify teacher owns the classroom
        if submission.classroom.teacher != request.user:
            messages.error(
                request, 'You can only grade submissions in your own classrooms.')
            return redirect('teacher_submissions')

        # Verify submission is submitted
        if not submission.is_submitted:
            messages.error(request, 'Cannot grade a draft submission.')
            return redirect('submission_detail', pk=submission.pk)

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['submission'] = self.get_object()
        return context

    def get_success_url(self):
        # Check if there's a 'next' parameter to return to
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        return reverse('submission_detail', kwargs={'pk': self.object.pk})


# =============================================================================
# MEMBER MANAGEMENT VIEWS
# =============================================================================

class ClassroomMemberListView(LoginRequiredMixin, ClassroomMemberMixin, ListView):
    """List all members of a classroom"""
    model = ClassroomMembership
    template_name = 'classrooms/member_list.html'
    context_object_name = 'memberships'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        self.classroom = get_object_or_404(
            Classroom, pk=kwargs['classroom_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_classroom(self):
        return self.classroom

    def get_queryset(self):
        return ClassroomMembership.objects.filter(
            classroom=self.classroom
        ).select_related('student').order_by('student__last_name', 'student__first_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['classroom'] = self.classroom
        context['is_owner'] = self.request.user == self.classroom.teacher
        return context


class RemoveMemberView(LoginRequiredMixin, ClassroomOwnerMixin, DeleteView):
    """Remove a student from a classroom (teacher only)"""
    model = ClassroomMembership
    template_name = 'classrooms/remove_member_confirm.html'

    def get_object(self, queryset=None):
        classroom = get_object_or_404(
            Classroom, pk=self.kwargs['classroom_pk'])
        return get_object_or_404(
            ClassroomMembership,
            classroom=classroom,
            student_id=self.kwargs['student_pk']
        )

    def get_success_url(self):
        messages.success(self.request, 'Student removed from classroom.')
        return reverse('classroom_members', kwargs={'classroom_pk': self.kwargs['classroom_pk']})
