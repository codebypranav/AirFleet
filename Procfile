web: python manage.py wait_for_db && python manage.py migrate && gunicorn AirFleet_api.wsgi:application --bind 0.0.0.0:$PORT --log-level debug
