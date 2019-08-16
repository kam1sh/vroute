import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String

Base = declarative_base()


class AddressRecord(Base):
    __tablename__ = "addresses"
    id = Column(Integer, primary_key=True)
    hostname = Column(String, nullable=False, index=True)
    resolved_addr = Column(String)
    comment = Column(String)


class Database:
    def __init__(self):
        self.engine = None

    def load(self, url, debug=False):
        self.engine = sqlalchemy.create_engine(url, echo=debug)

    def create(self):
        Base.metadata.create_all(self.engine)
