from django.db import models

class UserAuth(models.Model):
    login = models.CharField(max_length=50)
    password_hash = models.CharField(max_length=150)
    staff_id = models.IntegerField()

    class Meta:
        db_table = 'user_auth'
        managed = False