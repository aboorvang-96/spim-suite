from django import forms
from .models import Project, Task

class ProjectForm(forms.ModelForm):
    class Meta:
        model   = Project
        fields  = ['name','client','status','budget','start_date','due_date','description']
        widgets = {
            'start_date':  forms.DateInput(attrs={'type':'date'}),
            'due_date':    forms.DateInput(attrs={'type':'date'}),
            'description': forms.Textarea(attrs={'rows':3}),
        }

class TaskForm(forms.ModelForm):
    class Meta:
        model   = Task
        fields  = ['title','assigned_to','status','priority','due_date','notes']
        widgets = {
            'due_date': forms.DateInput(attrs={'type':'date'}),
            'notes':    forms.Textarea(attrs={'rows':2}),
        }
