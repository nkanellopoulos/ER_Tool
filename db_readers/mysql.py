from typing import List
from typing import Tuple

from .base import DatabaseReader
from .base import DBColumn
from .base import DBConstraint


class MySQLReader(DatabaseReader):
    """Stub implementation - to be completed when MySQL support is needed"""

    def connect(self, connection_string: str) -> None:
        raise NotImplementedError("MySQL support not implemented yet")

    def get_tables(self) -> List[str]:
        raise NotImplementedError("MySQL support not implemented yet")

    def get_columns(self, table_name: str) -> List[DBColumn]:
        raise NotImplementedError("MySQL support not implemented yet")

    def get_constraints(self, table_name: str) -> List[DBConstraint]:
        raise NotImplementedError("MySQL support not implemented yet")

    def get_foreign_keys(self, table_name: str) -> List[Tuple[str, str]]:
        raise NotImplementedError("MySQL support not implemented yet")
