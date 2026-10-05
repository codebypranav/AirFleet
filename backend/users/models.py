from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    bio = models.TextField(blank=True, max_length=500)
    home_airport = models.CharField(max_length=4, blank=True)
    # Opt-in: a public pilot shares their profile page, stats and flights by link.
    is_public = models.BooleanField(default=False)
    # Instructing is a capability, not an account type: any pilot who records a flight
    # instructor certificate can be invited as someone's instructor and sign their dual time.
    instructor_certificate_number = models.CharField(max_length=20, blank=True)
    instructor_certificate_expires = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username
