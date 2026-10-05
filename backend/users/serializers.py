from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from flights import airports
from .models import CustomUser


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = CustomUser
        fields = ('username', 'password', 'password2', 'email')

    def validate_email(self, value):
        if CustomUser.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value

    def validate_username(self, value):
        if CustomUser.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already in use.")
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2', None)
        return CustomUser.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
        )


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = (
            'username', 'email', 'first_name', 'last_name', 'bio', 'home_airport', 'is_public',
            'instructor_certificate_number', 'instructor_certificate_expires', 'date_joined',
        )
        read_only_fields = ('date_joined',)

    def validate_username(self, value):
        if CustomUser.objects.filter(username__iexact=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("This username is already in use.")
        return value

    def validate_email(self, value):
        if CustomUser.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value

    def validate_instructor_certificate_number(self, value):
        return value.strip().upper()

    def validate_home_airport(self, value):
        code = value.strip().upper()
        if code and not airports.get(code):
            raise serializers.ValidationError(f"{code} isn't a known airport code.")
        return code


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError("Your current password is incorrect.")
        return value

    def validate_new_password(self, value):
        validate_password(value, self.context['request'].user)
        return value


class DeleteAccountSerializer(serializers.Serializer):
    """Deleting is permanent, so the pilot types their username, and their password if they have one."""
    confirm = serializers.CharField()
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    def validate_confirm(self, value):
        if value.strip() != self.context['request'].user.username:
            raise serializers.ValidationError("Type your username exactly to confirm.")
        return value

    def validate(self, attrs):
        user = self.context['request'].user
        if user.has_usable_password() and not user.check_password(attrs.get('password', '')):
            raise serializers.ValidationError({'password': "Your password is incorrect."})
        return attrs


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True)
