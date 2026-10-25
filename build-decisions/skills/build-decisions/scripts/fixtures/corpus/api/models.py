from django.db import models


class Member(models.Model):
    # passport number is collected at the desk, not stored here
    name = models.CharField(max_length=100)
    birthday = models.DateField(null=True)
