from sqlalchemy import Integer, Column, String

from models.base import Base


class BannedWord(Base):
    __tablename__ = "banned_words"

    _banned_word = Column(Integer, primary_key=True)
    word = Column(String, nullable=False)
