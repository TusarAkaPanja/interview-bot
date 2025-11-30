import uuid
import random
import string
import os
from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from utils.crypto_utils import PasswordCrypto


class Role(models.Model):
    id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'roles'
        ordering = ['name']

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.create_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    email = models.EmailField(unique=True)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members'
    )
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    password = models.CharField(max_length=255)
    salt = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        db_table = 'users'
        ordering = ['-created_at']

    def __str__(self):
        return self.email

    def create_password(self, password):
        if not self.salt:
            self.salt = PasswordCrypto.generate_salt()
        self.password = PasswordCrypto.hash_password(password, self.salt)
        self.save()
        return self.password

    def check_password(self, password):
        return PasswordCrypto.verify_password(password, self.password, self.salt)



class Candidate(models.Model):
    id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='candidates'
    )
    password = models.CharField(max_length=255, null=True, blank=True)
    salt = models.CharField(max_length=255, null=True, blank=True)
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Candidate'
        verbose_name_plural = 'Candidates'
        db_table = 'candidates'
        ordering = ['-created_at']

    def __str__(self):
        return self.email

    @staticmethod
    def generate_random_password():
        # return a 8 character random password with letters and digits
        random_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        print(f'Random password: {random_password}')
        return random_password

    def set_candidate_password(self, password):
        if not password:
            password = self.generate_random_password()
        if not self.salt:
            self.salt = PasswordCrypto.generate_salt()
        self.password = PasswordCrypto.encrypt_password(password, self.salt)
        self.save()
    
    def get_plaintext_password(self):
        """Decrypt and return the plaintext password."""
        if self.password and self.salt:
            try:
                return PasswordCrypto.decrypt_password(self.password, self.salt)
            except Exception as e:
                return None
        return None
    
    def check_password(self, password):
        """Check if the provided password matches the stored password.
        Supports both encrypted (new) and hashed (old) passwords."""
        if not self.password or not self.salt:
            return False
        try:
            decrypted_password = PasswordCrypto.decrypt_password(self.password, self.salt)
            return decrypted_password == password
        except Exception:
            try:
                return PasswordCrypto.verify_password(password, self.password, self.salt)
            except Exception:
                return False