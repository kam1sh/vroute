from pathlib import Path

import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, orm

from .logger import verbose

Base = declarative_base()


class AddressRecord(Base):
    __tablename__ = "addresses"
    id = Column(Integer, primary_key=True)
    hostname = Column(String, index=True)
    addrv4 = Column(String)
    expires = Column(DateTime, index=True)
    comment = Column(String)

    def resolve(self):
        raise NotImplementedError()


MEMORY = ":memory:"


class Database:
    def __init__(self, file=MEMORY, debug=False, auto_create=True):
        url = "sqlite:///" + file
        verbose("Using database: <comment>%s</>", url)
        self.engine = sqlalchemy.create_engine(url, echo=debug)
        self.file = Path(file)
        if auto_create and not self.file.exists():
            self.create()

    def create(self):
        verbose("Creating new database schema")
        Base.metadata.create_all(self.engine)

    def new_session(self):
        return orm.Session(self.engine)
