from typing import List
from typing import Tuple

import mysql.connector
from mysql.connector import Error as MySQLError

from .base import DatabaseReader
from .base import DBColumn
from .base import DBConstraint


class MySQLReader(DatabaseReader):
    def connect(self, connection_string: str) -> None:
        """Connect to MySQL database using connection string"""
        try:
            # Parse connection string (format: mysql://user:pass@host:port/dbname)
            parts = connection_string.replace("mysql://", "").split("@")
            user_pass = parts[0].split(":")
            host_db = parts[1].split("/")
            host_port = host_db[0].split(":")

            self.connection = mysql.connector.connect(
                user=user_pass[0],
                password=user_pass[1],
                host=host_port[0],
                port=int(host_port[1]) if len(host_port) > 1 else 3306,
                database=host_db[1],
            )
            self.cursor = self.connection.cursor(dictionary=True)
        except MySQLError as e:
            raise ConnectionError(f"Failed to connect to MySQL: {e}")

    def get_tables(self) -> List[str]:
        """Get list of all tables in the database"""
        self.cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        )
        return [row["table_name"] for row in self.cursor.fetchall()]

    def get_columns(self, table_name: str) -> List[DBColumn]:
        """Get column information for a table"""
        self.cursor.execute(
            """
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_key,
                column_type,
                extra
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
            AND table_name = %s
            ORDER BY ordinal_position
        """,
            (table_name,),
        )

        columns = []
        for row in self.cursor.fetchall():
            # Handle column type with precision/scale
            column_type = row["column_type"].lower()

            # Check for primary key
            is_primary = row["column_key"] == "PRI"

            # Create column object
            column = DBColumn(
                name=row["column_name"],
                type=column_type,
                is_nullable=row["is_nullable"] == "YES",
                is_primary=is_primary,
            )
            columns.append(column)

        return columns

    def get_constraints(self, table_name: str) -> List[DBConstraint]:
        """Get constraints for a table"""
        # First get non-PK constraints
        self.cursor.execute(
            """
            SELECT
                tc.constraint_type,
                GROUP_CONCAT(kcu.column_name ORDER BY kcu.ordinal_position) as columns,
                tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = DATABASE()
            AND tc.table_name = %s
            AND tc.constraint_type NOT IN ('FOREIGN KEY', 'PRIMARY KEY')
            GROUP BY tc.constraint_name, tc.constraint_type
        """,
            (table_name,),
        )

        constraints = []

        # Handle regular constraints
        for row in self.cursor.fetchall():
            columns = row["columns"].split(",")
            definition = f"{row['constraint_type']} ({', '.join(columns)})"
            constraint = DBConstraint(
                type=row["constraint_type"], columns=columns, definition=definition
            )
            constraints.append(constraint)

        # Separately handle primary keys to avoid duplicates
        self.cursor.execute(
            """
            SELECT GROUP_CONCAT(column_name ORDER BY ordinal_position) as pk_columns
            FROM information_schema.key_column_usage
            WHERE table_schema = DATABASE()
            AND table_name = %s
            AND constraint_name = 'PRIMARY'
            GROUP BY constraint_name
            """,
            (table_name,),
        )

        pk_row = self.cursor.fetchone()
        if pk_row and pk_row["pk_columns"]:
            pk_columns = pk_row["pk_columns"].split(",")
            constraints.append(
                DBConstraint(
                    type="PRIMARY KEY",
                    columns=pk_columns,
                    definition=f"PRIMARY KEY ({', '.join(pk_columns)})",
                )
            )

        return constraints

    def get_foreign_keys(self, table_name: str) -> List[Tuple[str, str]]:
        """Get foreign key relationships for a table"""
        self.cursor.execute(
            """
            SELECT
                kcu.column_name,
                kcu.referenced_table_name
            FROM information_schema.key_column_usage kcu
            JOIN information_schema.referential_constraints rc
                ON kcu.constraint_name = rc.constraint_name
                AND kcu.table_schema = rc.constraint_schema
            WHERE kcu.table_schema = DATABASE()
            AND kcu.table_name = %s
            AND kcu.referenced_table_name IS NOT NULL
        """,
            (table_name,),
        )

        return [
            (row["column_name"], row["referenced_table_name"])
            for row in self.cursor.fetchall()
        ]

    def __del__(self):
        """Cleanup database connection"""
        if hasattr(self, "cursor"):
            self.cursor.close()
        if hasattr(self, "connection"):
            self.connection.close()
