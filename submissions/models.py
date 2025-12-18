"""
Models for University Project Submission Platform
Demonstrates: Model relationships, custom managers, model methods, validators
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
from django.utils import timezone
import secrets
import string


def generate_join_code():
    """Generate a unique 8-character alphanumeric join code for classrooms"""
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))


class User(AbstractUser):
    """
    Extended User model with role flag.
    is_teacher determines elevated permissions.
    Default users are students.
    """
    is_teacher = models.BooleanField(default=False, help_text="Designates whether this user is a teacher.")
    
    class Meta:
        db_table = 'auth_user'
    
    def __str__(self):
        return f"{self.get_full_name() or self.username} ({'Teacher' if self.is_teacher else 'Student'})"


class ClassroomManager(models.Manager):
    """Custom manager for Classroom with common querysets"""
    
    def for_teacher(self, teacher):
        """Get all classrooms owned by a teacher"""
        return self.filter(teacher=teacher)
    
    def for_student(self, student):
        """Get all classrooms a student has joined"""
        return self.filter(memberships__student=student)


class Classroom(models.Model):
    """
    Represents a project assignment tied to a teacher and subject.
    Each classroom represents exactly one project assignment.
    """
    title = models.CharField(max_length=200)
    description = models.TextField(help_text="Detailed description of the project requirements")
    requirements_file = models.FileField(
        upload_to='classroom_requirements/',
        blank=True,
        null=True,
        help_text="Optional: Upload project requirements document (PDF, DOCX)"
    )
    join_code = models.CharField(
        max_length=8,
        unique=True,
        default=generate_join_code,
        editable=False,
        help_text="Unique code for students to join this classroom"
    )
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='owned_classrooms',
        limit_choices_to={'is_teacher': True}
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = ClassroomManager()
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Classroom'
        verbose_name_plural = 'Classrooms'
    
    def __str__(self):
        return f"{self.title} - {self.teacher.get_full_name() or self.teacher.username}"
    
    def get_absolute_url(self):
        return reverse('classroom_detail', kwargs={'pk': self.pk})
    
    def get_student_count(self):
        """Returns the number of students enrolled in this classroom"""
        return self.memberships.count()
    
    def get_submission_count(self):
        """Returns the number of project submissions in this classroom"""
        return self.submissions.count()
    
    def get_submitted_count(self):
        """Returns the number of submitted (non-draft) projects"""
        return self.submissions.filter(status=ProjectSubmission.Status.SUBMITTED).count()
    
    def get_graded_count(self):
        """Returns the number of graded projects"""
        return self.submissions.exclude(grade__isnull=True).count()
    
    def is_student_member(self, user):
        """Check if a user is a member of this classroom"""
        return self.memberships.filter(student=user).exists()
    
    def regenerate_join_code(self):
        """Generate a new join code for this classroom"""
        self.join_code = generate_join_code()
        self.save(update_fields=['join_code'])
        return self.join_code


class ClassroomMembership(models.Model):
    """
    Links students to classrooms.
    Represents enrollment of a student in a classroom.
    """
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='classroom_memberships',
        limit_choices_to={'is_teacher': False}
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['classroom', 'student']
        ordering = ['-joined_at']
        verbose_name = 'Classroom Membership'
        verbose_name_plural = 'Classroom Memberships'
    
    def __str__(self):
        return f"{self.student.username} in {self.classroom.title}"
    
    def get_absolute_url(self):
        return self.classroom.get_absolute_url()


class ProjectSubmissionManager(models.Manager):
    """Custom manager for ProjectSubmission with permission-aware querysets"""
    
    def for_student(self, student):
        """
        Get all submissions where the student is a collaborator.
        Students can only see their own projects.
        """
        return self.filter(collaborators=student)
    
    def for_teacher(self, teacher):
        """Get all submissions in classrooms owned by the teacher where their status is SUBMITTED"""
        return self.filter(classroom__teacher=teacher, status=ProjectSubmission.Status.SUBMITTED)
    
    def for_classroom(self, classroom, teacher=None):
        """
        Get all submissions in a specific classroom.
        If teacher is provided, only return SUBMITTED status for permission consistency.
        """
        qs = self.filter(classroom=classroom)
        if teacher is not None:
            # Only show submitted projects to teachers
            qs = qs.filter(status=ProjectSubmission.Status.SUBMITTED)
        return qs
    
    def submitted(self):
        """Get only submitted (non-draft) projects"""
        return self.filter(status=ProjectSubmission.Status.SUBMITTED)
    
    def drafts(self):
        """Get only draft projects"""
        return self.filter(status=ProjectSubmission.Status.DRAFT)
    
    def graded(self):
        """Get only graded projects"""
        return self.exclude(grade__isnull=True)
    
    def ungraded(self):
        """Get submitted but ungraded projects"""
        return self.filter(
            status=ProjectSubmission.Status.SUBMITTED,
            grade__isnull=True
        )


class ProjectSubmission(models.Model):
    """
    Represents a student's project submission.
    Only one submission per student per classroom.
    Editable only while status is DRAFT.
    """
    
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SUBMITTED = 'SUBMITTED', 'Submitted'
    
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    title = models.CharField(max_length=200, help_text="Title of your project")
    description = models.TextField(help_text="Describe your project, its features, and implementation details")
    repository_url = models.URLField(
        help_text="GitHub or GitLab repository URL (required)",
        verbose_name="Repository URL"
    )
    deployed_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL where your project is deployed (optional)",
        verbose_name="Deployed URL"
    )
    collaborators = models.ManyToManyField(
        User,
        related_name='project_collaborations',
        help_text="Select team members from this classroom"
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT
    )
    grade = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
        help_text="Grade from 1 to 20"
    )
    teacher_notes = models.TextField(
        blank=True,
        help_text="Feedback and notes from the teacher"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_submissions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    
    objects = ProjectSubmissionManager()
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Project Submission'
        verbose_name_plural = 'Project Submissions'
        # Ensure one submission per student per classroom
        constraints = [
            models.UniqueConstraint(
                fields=['classroom', 'created_by'],
                name='unique_submission_per_student_per_classroom'
            )
        ]
    
    def __str__(self):
        return f"{self.title} - {self.classroom.title}"
    
    def get_absolute_url(self):
        return reverse('submission_detail', kwargs={'pk': self.pk})
    
    @property
    def is_draft(self):
        """Check if submission is still in draft status"""
        return self.status == self.Status.DRAFT
    
    @property
    def is_submitted(self):
        """Check if submission has been submitted"""
        return self.status == self.Status.SUBMITTED
    
    @property
    def is_graded(self):
        """Check if submission has been graded"""
        return self.grade is not None
    
    @property
    def is_editable(self):
        """Submissions are only editable while in DRAFT status"""
        return self.is_draft
    
    def can_user_view(self, user):
        """
        Check if a user can view this submission.
        - Teachers who own the classroom can view
        - Collaborators can view
        """
        if user.is_teacher and self.classroom.teacher == user:
            return True
        return self.collaborators.filter(pk=user.pk).exists()
    
    def can_user_edit(self, user):
        """
        Check if a user can edit this submission.
        - Must be a collaborator
        - Must be in DRAFT status
        """
        if not self.is_editable:
            return False
        return self.collaborators.filter(pk=user.pk).exists()
    
    def submit(self):
        """
        Submit the project.
        Changes status to SUBMITTED and records submission time.
        """
        if self.is_draft:
            self.status = self.Status.SUBMITTED
            self.submitted_at = timezone.now()
            self.save(update_fields=['status', 'submitted_at', 'updated_at'])
            return True
        return False
    
    def assign_grade(self, grade, notes=''):
        """
        Assign a grade to the submission.
        Only valid for submitted projects.
        """
        if self.is_submitted:
            self.grade = grade
            self.teacher_notes = notes
            self.save(update_fields=['grade', 'teacher_notes', 'updated_at'])
            return True
        return False
    
    def get_collaborator_names(self):
        """Get a comma-separated list of collaborator names"""
        return ', '.join([
            c.get_full_name() or c.username 
            for c in self.collaborators.all()
        ])
