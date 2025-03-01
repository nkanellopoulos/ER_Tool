import re
import sys
from dataclasses import dataclass
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

import psycopg2


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
    def from_database(conn_string: str) -> Dict[str, Table]:
        """Read schema from a live PostgreSQL database"""
        tables = {}
        with psycopg2.connect(conn_string) as conn:
            with conn.cursor() as cur:
                # Get all tables
                cur.execute(
                    """
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """
                )
                for (table_name,) in cur.fetchall():
                    print(f"Processing table {table_name}", file=sys.stderr)
                    columns = []
                    foreign_keys = []

                    # Get columns and their properties
                    cur.execute(
                        """
                        SELECT 
                            c.column_name, 
                            c.data_type,
                            c.is_nullable,
                            (SELECT tc.constraint_type 
                             FROM information_schema.table_constraints tc 
                             JOIN information_schema.constraint_column_usage ccu 
                             ON tc.constraint_name = ccu.constraint_name 
                             WHERE tc.table_name = c.table_name 
                             AND ccu.column_name = c.column_name 
                             AND tc.constraint_type = 'PRIMARY KEY') is_primary,
                            (SELECT ccu.table_name
                             FROM information_schema.table_constraints tc
                             JOIN information_schema.key_column_usage kcu
                             ON tc.constraint_name = kcu.constraint_name
                             JOIN information_schema.constraint_column_usage ccu
                             ON ccu.constraint_name = tc.constraint_name
                             WHERE tc.table_name = c.table_name
                             AND kcu.column_name = c.column_name
                             AND tc.constraint_type = 'FOREIGN KEY') referenced_table
                        FROM information_schema.columns c
                        WHERE c.table_name = %s
                        AND c.table_schema = 'public'
                        ORDER BY c.ordinal_position
                    """,
                        (table_name,),
                    )

                    for col in cur.fetchall():
                        col_name, col_type, nullable, is_primary, ref_table = col
                        constraints = []
                        if not nullable == "YES":
                            constraints.append("NN")
                        if is_primary:
                            constraints.append("PK")
                        if ref_table:
                            constraints.append("FK")
                            foreign_keys.append((col_name, ref_table))

                        columns.append(
                            Column(
                                name=col_name,
                                type=col_type,
                                constraints=constraints,
                                is_primary=bool(is_primary),
                                is_foreign=bool(ref_table),
                                references=ref_table,
                            )
                        )

                    # Get multi-column constraints
                    cur.execute(
                        """
                        SELECT 
                            tc.constraint_type,
                            array_agg(kcu.column_name::text)
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                        WHERE tc.table_name = %s
                        AND tc.constraint_type IN ('UNIQUE')
                        GROUP BY tc.constraint_name, tc.constraint_type
                    """,
                        (table_name,),
                    )

                    constraints = []
                    for constraint_type, columns_array in cur.fetchall():
                        constraints.append(
                            TableConstraint(
                                type=constraint_type,
                                columns=columns_array,
                                definition=f"{constraint_type}({', '.join(columns_array)})",
                            )
                        )

                    tables[table_name] = Table(
                        name=table_name,
                        columns=columns,
                        constraints=constraints,
                        foreign_keys=foreign_keys,
                    )

        return tables

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
