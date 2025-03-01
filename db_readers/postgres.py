import re
from typing import Dict
from typing import List
from typing import Tuple

import psycopg2

from .base import DatabaseReader
from .base import DBColumn
from .base import DBConstraint
from .base import DBTable


class PostgresReader(DatabaseReader):
    def connect(self, connection_string: str) -> None:
        self.conn = psycopg2.connect(connection_string)
        self.cursor = self.conn.cursor()

    def get_tables(self) -> List[str]:
        self.cursor.execute(
            """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """
        )
        return [row[0] for row in self.cursor.fetchall()]

    def get_columns(self, table_name: str) -> List[DBColumn]:
        self.cursor.execute(
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

        columns = []
        for col in self.cursor.fetchall():
            col_name, col_type, nullable, is_primary, ref_table = col
            columns.append(
                DBColumn(
                    name=col_name,
                    type=col_type,
                    is_nullable=nullable == "YES",
                    is_primary=bool(is_primary),
                    references=ref_table,
                )
            )
        return columns

    def get_constraints(self, table_name: str) -> List[DBConstraint]:
        self.cursor.execute(
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
        for constraint_type, columns_array in self.cursor.fetchall():
            constraints.append(
                DBConstraint(
                    type=constraint_type,
                    columns=columns_array,
                    definition=f"{constraint_type}({', '.join(columns_array)})",
                )
            )
        return constraints

    def get_foreign_keys(self, table_name: str) -> List[Tuple[str, str]]:
        self.cursor.execute(
            """
            SELECT 
                kcu.column_name,
                ccu.table_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name
            WHERE tc.table_name = %s
            AND tc.constraint_type = 'FOREIGN KEY'
        """,
            (table_name,),
        )

        return [(col_name, ref_table) for col_name, ref_table in self.cursor.fetchall()]
