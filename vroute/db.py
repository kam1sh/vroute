from pathlib import Path

import sqlalchemy
from .logger import verbose

from .models import Base, Host, Address  # pylint: disable=unused-import


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
        return sqlalchemy.orm.Session(self.engine)
