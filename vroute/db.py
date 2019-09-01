import logging
from pathlib import Path

import sqlalchemy.orm

from .models import Base, Host, Address  # pylint: disable=unused-import


MEMORY = ":memory:"

log = logging.getLogger(__name__)


class Database:
    def __init__(self, file=MEMORY, debug=False, auto_create=True):
        url = "sqlite:///" + file
        log.debug("Using database: <comment>%s</>", url)
        self.engine = sqlalchemy.create_engine(url, echo=debug)
        self.file = Path(file)
        if auto_create and not self.file.exists():
            self.create()

    def create(self):
        log.info("Creating new database schema")
        Base.metadata.create_all(self.engine)

    def new_session(self):
        return sqlalchemy.orm.Session(self.engine)
