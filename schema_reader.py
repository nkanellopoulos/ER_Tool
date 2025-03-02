import re
import sys
from dataclasses import dataclass
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from db_readers.base import DatabaseReader
from db_readers.mysql import MySQLReader
from db_readers.postgres import PostgresReader


@dataclass
class Column:
    name: str
    type: str
    constraints: List[str]
    is_primary: bool
    is_foreign: bool
    references: Optional[str] = None


@dataclass
class TableConstraint:
    type: str  # UNIQUE, CHECK, etc.
    columns: List[str]
    definition: str


@dataclass
class Table:
    name: str
    columns: List[Column]
    constraints: List[TableConstraint]
    foreign_keys: List[Tuple[str, str]]  # [(column_name, referenced_table), ...]


class SchemaReader:
    @staticmethod
    def get_reader(connection_string: str) -> DatabaseReader:
        """Factory method to get appropriate database reader"""
        if connection_string.startswith("postgresql://"):
            return PostgresReader()
        elif connection_string.startswith("mysql://"):
            return MySQLReader()
        else:
            raise ValueError("Unsupported database type")

    @staticmethod
    def from_database(conn_string: str) -> Dict[str, Table]:
        reader = SchemaReader.get_reader(conn_string)
        reader.connect(conn_string)
        db_tables = reader.read_schema()

        # Convert from DB models to our internal models
        return {
            name: Table(
                name=name,
                columns=[
                    Column(
                        name=c.name,
                        type=c.type,
                        constraints=SchemaReader._get_constraints(c),
                        is_primary=c.is_primary,
                        is_foreign=bool(c.references),
                        references=c.references,
                    )
                    for c in table.columns
                ],
                constraints=[
                    TableConstraint(
                        type=c.type, columns=c.columns, definition=c.definition
                    )
                    for c in table.constraints
                ],
                foreign_keys=table.foreign_keys,
            )
            for name, table in db_tables.items()
        }

    @staticmethod
    def _get_constraints(col: Column) -> List[str]:
        """Convert DB column properties to constraint list"""
        constraints = []
        if not col.is_nullable:
            constraints.append("NN")
        if col.is_primary:
            constraints.append("PK")
        if col.references:
            constraints.append("FK")
        return constraints

    @staticmethod
    def from_ddl(ddl: str) -> Dict[str, Table]:
        """Read schema from DDL string"""
        tables = {}

        print(f"Processing DDL of length: {len(ddl)}", file=sys.stderr)

        table_pattern = re.compile(
            r'CREATE TABLE\s+(?:\w+\.)?"?(\w+)"?\s*\((.*?)\);\s*',
            re.IGNORECASE | re.DOTALL,
        )
        column_pattern = re.compile(
            r'^\s*"?(?P<name>\w+)"?\s+(?P<type>[a-zA-Z0-9\s\(\)]+)(?P<constraints>(?:[^,]*(?:constraint\s+\w+\s+)?(?:references|unique|primary\s+key|not\s+null)[^,]*|[^,]*)*)(?=,|\s*$)',
            re.IGNORECASE | re.MULTILINE,
        )
        fk_pattern = re.compile(
            r'\s+REFERENCES\s+(?:(?P<schema>\w+)\.)?"?(?P<table>\w+)"?', re.IGNORECASE
        )
        multi_col_constraint_pattern = re.compile(
            r'CONSTRAINT\s+"\w+"\s+UNIQUE\s*\((.*?)\)', re.IGNORECASE
        )

        matches = table_pattern.finditer(ddl)
        for match in matches:
            table_name = match.group(1)
            table_def = match.group(2)
            print(f"\nProcessing table: {table_name}", file=sys.stderr)
            columns = []
            constraints = []
            foreign_keys = []
            multi_column_fields = set()

            # First pass: collect multi-column constraints
            for constraint_match in multi_col_constraint_pattern.finditer(table_def):
                columns_list = [
                    c.strip().strip('"') for c in constraint_match.group(1).split(",")
                ]
                constraints.append(
                    TableConstraint(
                        type="UNIQUE",
                        columns=columns_list,
                        definition=f"UNIQUE({', '.join(columns_list)})",
                    )
                )
                multi_column_fields.update(columns_list)

            # Second pass: process columns
            for col_match in column_pattern.finditer(table_def):
                name = col_match.group("name").strip()
                if not name or name.lower() in ("constraint", "unique", "primary key"):
                    continue

                col_type = col_match.group("type").strip()
                col_constraints = col_match.group("constraints").strip().upper()

                constraints_list = []
                is_primary = "PRIMARY KEY" in col_constraints
                is_foreign = "REFERENCES" in col_constraints

                if "NOT NULL" in col_constraints:
                    constraints_list.append("NN")
                if is_primary:
                    constraints_list.append("PK")
                if "UNIQUE" in col_constraints and name not in multi_column_fields:
                    constraints_list.append("UNIQUE")

                referenced_table = None
                if is_foreign:
                    fk_match = fk_pattern.search(col_constraints)
                    if fk_match:
                        schema = fk_match.group("schema") or "public"
                        table = fk_match.group("table").strip().replace('"', "")
                        # Store without schema prefix and in original case
                        referenced_table = table
                        foreign_keys.append((name, referenced_table))
                        print(
                            f"  Found FK: {name} -> {referenced_table}", file=sys.stderr
                        )
                        constraints_list.append("FK")

                columns.append(
                    Column(
                        name=name,
                        type=col_type,
                        constraints=constraints_list,
                        is_primary=is_primary,
                        is_foreign=is_foreign,
                        references=referenced_table,
                    )
                )

            tables[table_name] = Table(
                name=table_name,
                columns=columns,
                constraints=constraints,
                foreign_keys=foreign_keys,
            )
            print(f"  Found {len(foreign_keys)} foreign keys", file=sys.stderr)
            print(f"  Foreign keys: {foreign_keys}", file=sys.stderr)

        print(f"\nProcessed {len(tables)} tables", file=sys.stderr)
        return tables
