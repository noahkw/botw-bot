from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.inspection import inspect

Base = declarative_base()


def __repr__(self):
    attrs = [
        attr
        for attr in inspect(self).attrs.keys()
        if not issubclass(type(getattr(self, attr)), Base)
    ]
    attrs_repr = [f"{attr}={getattr(self, attr)}" for attr in attrs]
    return f"<{type(self).__name__}=({','.join(attrs_repr)})>"


Base.__repr__ = __repr__
