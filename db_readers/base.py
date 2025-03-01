from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple


@dataclass
class DBColumn:
    name: str
    type: str
    is_nullable: bool
    is_primary: bool
    references: Optional[str] = None


@dataclass
class DBConstraint:
    type: str
    columns: List[str]
    definition: str


@dataclass
class DBTable:
    name: str
    columns: List[DBColumn]
    constraints: List[DBConstraint]
    foreign_keys: List[Tuple[str, str]]


class DatabaseReader(ABC):
    @abstractmethod
    def connect(self, connection_string: str) -> None:
        """Establish database connection"""
        pass

    @abstractmethod
    def get_tables(self) -> List[str]:
        """Get list of all tables"""
        pass

    @abstractmethod
    def get_columns(self, table_name: str) -> List[DBColumn]:
        """Get columns for a table"""
        pass

    @abstractmethod
    def get_constraints(self, table_name: str) -> List[DBConstraint]:
        """Get constraints for a table"""
        pass

    @abstractmethod
    def get_foreign_keys(self, table_name: str) -> List[Tuple[str, str]]:
        """Get foreign keys for a table"""
        pass

    def read_schema(self) -> Dict[str, DBTable]:
        """Template method to read entire schema"""
        tables = {}
        for table_name in self.get_tables():
            tables[table_name] = DBTable(
                name=table_name,
                columns=self.get_columns(table_name),
                constraints=self.get_constraints(table_name),
                foreign_keys=self.get_foreign_keys(table_name),
            )
        return tables
