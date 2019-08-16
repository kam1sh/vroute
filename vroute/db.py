from pathlib import Path

import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime

from .console import writeln

Base = declarative_base()


class AddressRecord(Base):
    __tablename__ = "addresses"
    id = Column(Integer, primary_key=True)
    hostname = Column(String, nullable=False, index=True)
    resolved_addr = Column(String)
    expires = Column(DateTime)
    comment = Column(String)


MEMORY = ":memory:"


class Database:
    def __init__(self, file=MEMORY, debug=False, auto_create=True):
        url = "sqlite:///" + file
        self.engine = sqlalchemy.create_engine(url, echo=debug)
        writeln("Using database: %s" % url)
        self.file = Path(file)
        if file != MEMORY and not self.file.exists():
            if not auto_create:
                raise FileNotFoundError(f"File {file} does not exist.")
            else:
                self.create()

    def create(self):
        Base.metadata.create_all(self.engine)
