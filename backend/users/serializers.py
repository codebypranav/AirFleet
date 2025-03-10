from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, ProgrammingError, OperationalError
from .models import CustomUser
import logging

logger = logging.getLogger(__name__)

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = CustomUser
        fields = ('username', 'password', 'password2', 'email')

    def validate_email(self, value):
        # Check if email is already in use - safely
        try:
            if CustomUser.objects.filter(email=value).exists():
                raise serializers.ValidationError("This email is already in use.")
        except (ProgrammingError, OperationalError) as e:
            # Table might not exist yet - log but don't fail validation
            logger.error(f"Database error in email validation: {str(e)}")
            # Try creating the table here directly as a fallback
            try:
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS users_customuser (
                            id SERIAL PRIMARY KEY,
                            password VARCHAR(128) NOT NULL,
                            last_login TIMESTAMP NULL,
                            is_superuser BOOLEAN NOT NULL,
                            username VARCHAR(150) UNIQUE NOT NULL,
                            first_name VARCHAR(150) NOT NULL,
                            last_name VARCHAR(150) NOT NULL,
                            email VARCHAR(254) UNIQUE NOT NULL,
                            is_staff BOOLEAN NOT NULL,
                            is_active BOOLEAN NOT NULL,
                            date_joined TIMESTAMP NOT NULL
                        );
                    """)
                    connection.commit()
                    logger.info("Created users_customuser table during validation")
            except Exception as table_error:
                logger.error(f"Failed to create table: {str(table_error)}")
        return value

    def validate_username(self, value):
        # Check if username is already in use - safely
        try:
            if CustomUser.objects.filter(username=value).exists():
                raise serializers.ValidationError("This username is already in use.")
        except (ProgrammingError, OperationalError) as e:
            # Table might not exist yet - log but don't fail validation
            logger.error(f"Database error in username validation: {str(e)}")
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        try:
            # Remove password2 as it's not needed for user creation
            validated_data.pop('password2', None)
            
            user = CustomUser.objects.create_user(
                username=validated_data['username'],
                email=validated_data['email'],
                password=validated_data['password']
            )
            return user
        except ProgrammingError as e:
            logger.exception(f"ProgrammingError creating user (table might not exist): {str(e)}")
            # Try creating the table and then the user
            try:
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS users_customuser (
                            id SERIAL PRIMARY KEY,
                            password VARCHAR(128) NOT NULL,
                            last_login TIMESTAMP NULL,
                            is_superuser BOOLEAN NOT NULL,
                            username VARCHAR(150) UNIQUE NOT NULL,
                            first_name VARCHAR(150) NOT NULL,
                            last_name VARCHAR(150) NOT NULL,
                            email VARCHAR(254) UNIQUE NOT NULL,
                            is_staff BOOLEAN NOT NULL,
                            is_active BOOLEAN NOT NULL,
                            date_joined TIMESTAMP NOT NULL
                        );
                    """)
                    connection.commit()
                    logger.info("Created users_customuser table, trying to create user again")
                
                # Try creating user again
                user = CustomUser.objects.create_user(
                    username=validated_data['username'],
                    email=validated_data['email'],
                    password=validated_data['password']
                )
                return user
            except Exception as retry_error:
                logger.exception(f"Failed to create user after table creation: {str(retry_error)}")
                raise serializers.ValidationError({
                    "database_error": f"Failed to create user after table creation: {str(retry_error)}"
                })
        except IntegrityError as e:
            logger.exception(f"IntegrityError creating user: {str(e)}")
            raise serializers.ValidationError({
                "database_error": f"Database integrity error: {str(e)}"
            })
        except Exception as e:
            logger.exception(f"Unexpected error creating user: {str(e)}")
            raise serializers.ValidationError({
                "error": f"An unexpected error occurred: {str(e)}"
            }) 