import os
import sys

from dot_generator import DotGenerator
from schema_reader import SchemaReader


def read_ddl_input(file_path=None):
    """Read DDL input from file or stdin"""
    if file_path and os.path.isfile(file_path):
        with open(file_path, "r") as file:
            return file.read()
    else:
        print("Please enter the DDL statements, followed by an EOF (Ctrl+D on Unix):")
        return sys.stdin.read()


def main():
    try:
        # Try database connection first
        conn_string = os.getenv("DB_CONNECTION")
        if conn_string:
            try:
                tables = SchemaReader.from_database(conn_string)
            except Exception as e:
                print(f"Database connection failed: {e}", file=sys.stderr)
                print("Falling back to DDL file...", file=sys.stderr)
                # Fall back to DDL parsing
                file_path = sys.argv[1] if len(sys.argv) > 1 else None
                ddl = read_ddl_input(file_path)
                tables = SchemaReader.from_ddl(ddl)
        else:
            # No connection string, use DDL
            file_path = sys.argv[1] if len(sys.argv) > 1 else None
            ddl = read_ddl_input(file_path)
            tables = SchemaReader.from_ddl(ddl)

        generator = DotGenerator(tables)
        print(generator.generate())

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
