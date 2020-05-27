from mongoengine import *
from ...core.db_model.structure import Product


class GenerateLogs(Document):
    date = DateTimeField()
    result = StringField()


class DistributeLogs(Document):
    date = DateTimeField()
    result = StringField()
    structure = ReferenceField(Product, default=None)