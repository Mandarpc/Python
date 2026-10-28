from django.db import models
import numpy as np
import pickle

class RegisteredFace(models.Model):
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to='registered_faces/')
    encoding = models.BinaryField()
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-registered_at']
        verbose_name = 'Registered Face'
        verbose_name_plural = 'Registered Faces'

    def __str__(self):
        return f"{self.name} — {self.registered_at.strftime('%d %b %Y, %H:%M')}"

    def get_encoding(self):
        return pickle.loads(bytes(self.encoding))

    def set_encoding(self, encoding_array):
        self.encoding = pickle.dumps(encoding_array)