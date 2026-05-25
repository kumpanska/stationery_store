from django.db import models

class UserAuth(models.Model):
    login = models.CharField(max_length=50)
    password_hash = models.CharField(max_length=150)
    staff_id = models.IntegerField()

    class Meta:
        db_table = 'user_auth'
        managed = False

class UserRegister(models.Model):
    full_name = models.CharField(max_length=150)
    staff_position = models.CharField(max_length=100)
    store_id = models.IntegerField()

    class Meta:
        db_table = 'staff'
        managed = False

class Store(models.Model):
    id = models.AutoField(primary_key=True)
    store_name = models.CharField(max_length=100)
    address = models.CharField(max_length=100)

    class Meta:
        db_table = 'store'
        managed = False