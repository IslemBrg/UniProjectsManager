"""
Forms for University Project Submission Platform
Demonstrates: ModelForms, custom validation, dynamic querysets, form widgets
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import User, Classroom, ClassroomMembership, ProjectSubmission


# =============================================================================
# AUTHENTICATION FORMS
# =============================================================================

class CustomUserCreationForm(UserCreationForm):
    """
    Extended user registration form with role selection.
    Students are created by default; teachers require explicit selection.
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email'
        })
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name'
        })
    )
    is_teacher = forms.BooleanField(
        required=False,
        label='Register as Teacher',
        help_text='Check this box if you are a teacher. Leave unchecked for student registration.',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2', 'is_teacher']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Choose a username'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to password fields
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm password'
        })
    
    def clean_email(self):
        """Ensure email is unique"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('A user with this email already exists.')
        return email


class CustomAuthenticationForm(AuthenticationForm):
    """Custom login form with Bootstrap styling"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Username'
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Password'
        })


# =============================================================================
# CLASSROOM FORMS
# =============================================================================

class ClassroomCreateForm(forms.ModelForm):
    """
    Form for teachers to create new classrooms.
    Teacher is set automatically in the view.
    """
    
    class Meta:
        model = Classroom
        fields = ['title', 'description', 'requirements_file']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Web Development Final Project'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Describe the project requirements, objectives, and evaluation criteria...'
            }),
            'requirements_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx'
            }),
        }
        help_texts = {
            'title': 'Give your classroom a descriptive title',
            'description': 'Provide detailed project requirements and expectations',
            'requirements_file': 'Optional: Upload a PDF or Word document with detailed requirements',
        }


class ClassroomUpdateForm(forms.ModelForm):
    """
    Form for teachers to update classroom details.
    Join code cannot be edited directly (use regenerate action instead).
    """
    
    class Meta:
        model = Classroom
        fields = ['title', 'description', 'requirements_file']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'requirements_file': forms.FileInput(attrs={'class': 'form-control'}),
        }


class JoinClassroomForm(forms.Form):
    """
    Form for students to join a classroom using a join code.
    Validates that the code exists and user isn't already a member.
    """
    join_code = forms.CharField(
        max_length=8,
        min_length=8,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg text-center text-uppercase',
            'placeholder': 'Enter 8-character code',
            'style': 'letter-spacing: 0.3em; font-family: monospace;'
        }),
        help_text='Enter the 8-character code provided by your teacher'
    )
    
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.classroom = None
    
    def clean_join_code(self):
        """Validate the join code and check membership"""
        code = self.cleaned_data.get('join_code', '').upper().strip()
        
        # Check if classroom exists
        try:
            self.classroom = Classroom.objects.get(join_code=code)
        except Classroom.DoesNotExist:
            raise ValidationError('Invalid join code. Please check and try again.')
        
        # Check if user is already a member
        if self.user and ClassroomMembership.objects.filter(
            classroom=self.classroom,
            student=self.user
        ).exists():
            raise ValidationError('You are already a member of this classroom.')
        
        # Check if user is the teacher of this classroom
        if self.user and self.classroom.teacher == self.user:
            raise ValidationError('You cannot join your own classroom as a student.')
        
        return code
    
    def save(self):
        """Create the membership after validation"""
        if self.classroom and self.user:
            membership = ClassroomMembership.objects.create(
                classroom=self.classroom,
                student=self.user
            )
            return membership
        return None


# =============================================================================
# PROJECT SUBMISSION FORMS
# =============================================================================

class ProjectSubmissionCreateForm(forms.ModelForm):
    """
    Form for students to create a new project submission.
    Collaborators are limited to students in the same classroom.
    """
    
    class Meta:
        model = ProjectSubmission
        fields = ['title', 'description', 'repository_url', 'deployed_url', 'collaborators']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., E-Commerce Platform'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Describe your project, technologies used, features implemented...'
            }),
            'repository_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://github.com/username/repository'
            }),
            'deployed_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://your-project.herokuapp.com (optional)'
            }),
            'collaborators': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, classroom=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.classroom = classroom
        self.user = user
        
        if classroom:
            # Limit collaborators to students in this classroom
            # Exclude the current user as they'll be added automatically
            student_ids = ClassroomMembership.objects.filter(
                classroom=classroom
            ).values_list('student_id', flat=True)
            
            self.fields['collaborators'].queryset = User.objects.filter(
                id__in=student_ids,
                is_teacher=False
            )
            
            # Make collaborators optional (creator is added automatically)
            self.fields['collaborators'].required = False
    
    def clean_repository_url(self):
        """Validate repository URL format"""
        url = self.cleaned_data.get('repository_url', '')
        valid_hosts = ['github.com', 'gitlab.com', 'bitbucket.org']
        
        if not any(host in url.lower() for host in valid_hosts):
            raise ValidationError(
                'Please provide a valid GitHub, GitLab, or Bitbucket repository URL.'
            )
        return url
    
    def clean(self):
        """Additional validation for the submission"""
        cleaned_data = super().clean()
        
        # Check if user already has a submission in this classroom
        if self.classroom and self.user:
            existing = ProjectSubmission.objects.filter(
                classroom=self.classroom,
                created_by=self.user
            )
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError(
                    'You already have a project submission in this classroom.'
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save the submission with classroom and creator"""
        instance = super().save(commit=False)
        
        if self.classroom:
            instance.classroom = self.classroom
        if self.user:
            instance.created_by = self.user
        
        if commit:
            instance.save()
            # Add the creator as a collaborator
            self.save_m2m()
            if self.user and not instance.collaborators.filter(pk=self.user.pk).exists():
                instance.collaborators.add(self.user)
        
        return instance


class ProjectSubmissionUpdateForm(forms.ModelForm):
    """
    Form for students to update their draft submission.
    Only available while status is DRAFT.
    """
    
    class Meta:
        model = ProjectSubmission
        fields = ['title', 'description', 'repository_url', 'deployed_url', 'collaborators']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
            'repository_url': forms.URLInput(attrs={'class': 'form-control'}),
            'deployed_url': forms.URLInput(attrs={'class': 'form-control'}),
            'collaborators': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.pk:
            classroom = self.instance.classroom
            
            # Limit collaborators to students in this classroom
            student_ids = ClassroomMembership.objects.filter(
                classroom=classroom
            ).values_list('student_id', flat=True)
            
            self.fields['collaborators'].queryset = User.objects.filter(
                id__in=student_ids,
                is_teacher=False
            )
            
            # If submission is not a draft, make all fields read-only
            if not self.instance.is_draft:
                for field in self.fields.values():
                    field.disabled = True
    
    def clean(self):
        """Ensure submission is still editable"""
        if self.instance and not self.instance.is_draft:
            raise ValidationError(
                'This submission has already been submitted and cannot be edited.'
            )
        return super().clean()


class ProjectSubmitForm(forms.Form):
    """
    Confirmation form for submitting a project.
    Once submitted, the project becomes read-only.
    """
    confirm = forms.BooleanField(
        required=True,
        label='I confirm that this submission is final',
        help_text='Once submitted, you will not be able to edit this project.',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


# =============================================================================
# GRADING FORMS (TEACHER ONLY)
# =============================================================================

class GradeSubmissionForm(forms.ModelForm):
    """
    Form for teachers to grade a submission.
    Only available for submitted projects.
    """
    
    class Meta:
        model = ProjectSubmission
        fields = ['grade', 'teacher_notes']
        widgets = {
            'grade': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 20,
                'placeholder': '1-20'
            }),
            'teacher_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Provide feedback for the students...'
            }),
        }
        help_texts = {
            'grade': 'Enter a grade between 1 and 20',
            'teacher_notes': 'Feedback will be visible to all collaborators',
        }
    
    def clean_grade(self):
        """Validate grade is within range"""
        grade = self.cleaned_data.get('grade')
        if grade is not None and (grade < 1 or grade > 20):
            raise ValidationError('Grade must be between 1 and 20.')
        return grade
    
    def clean(self):
        """Ensure submission is submitted before grading"""
        if self.instance and not self.instance.is_submitted:
            raise ValidationError(
                'Cannot grade a draft submission. Wait for the student to submit.'
            )
        return super().clean()


# =============================================================================
# FILTER FORMS
# =============================================================================

class SubmissionFilterForm(forms.Form):
    """
    Filter form for submission lists.
    Supports filtering by status, grade range, classroom, and student.
    """
    STATUS_CHOICES = [
        ('', 'All Statuses'),
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('GRADED', 'Graded'),
    ]

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    grade_min = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=20,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Min',
            'min': 1,
            'max': 20
        })
    )
    grade_max = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=20,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Max',
            'min': 1,
            'max': 20
        })
    )
    classroom = forms.ModelChoiceField(
        queryset=Classroom.objects.none(),
        required=False,
        empty_label='All Classrooms',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    student = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by student name...'
        })
    )
    
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        if user:
            if user.is_teacher:
                # Teachers see their own classrooms
                self.fields['classroom'].queryset = Classroom.objects.for_teacher(user)
                self.fields['status'].choices = [choice for choice in self.fields['status'].choices if choice[0] != 'DRAFT']
            else:
                # Students see classrooms they've joined
                self.fields['classroom'].queryset = Classroom.objects.for_student(user)
    
    def filter_queryset(self, queryset):
        """Apply filters to the queryset"""
        if not self.is_valid():
            return queryset
        
        data = self.cleaned_data
        
        # Filter by status
        status = data.get('status')
        if status == 'GRADED':
            queryset = queryset.exclude(grade__isnull=True)
        elif status:
            queryset = queryset.filter(status=status)
        
        # Filter by grade range
        grade_min = data.get('grade_min')
        grade_max = data.get('grade_max')
        if grade_min is not None:
            queryset = queryset.filter(grade__gte=grade_min)
        if grade_max is not None:
            queryset = queryset.filter(grade__lte=grade_max)
        
        # Filter by classroom
        classroom = data.get('classroom')
        if classroom:
            queryset = queryset.filter(classroom=classroom)
        
        # Filter by student name
        student = data.get('student')
        if student:
            queryset = queryset.filter(
                Q(collaborators__username__icontains=student) |
                Q(collaborators__first_name__icontains=student) |
                Q(collaborators__last_name__icontains=student)
            ).distinct()
        
        return queryset


class ClassroomFilterForm(forms.Form):
    """Filter form for classroom lists"""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search classrooms...'
        })
    )
    
    def filter_queryset(self, queryset):
        """Apply search filter to queryset"""
        if not self.is_valid():
            return queryset
        
        search = self.cleaned_data.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(teacher__first_name__icontains=search) |
                Q(teacher__last_name__icontains=search)
            )
        
        return queryset
