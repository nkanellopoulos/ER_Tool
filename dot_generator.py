import sys
from typing import Dict
from typing import List

from schema_reader import Column
from schema_reader import Table
from schema_reader import TableConstraint


class DotGenerator:
    def __init__(self, tables: Dict[str, Table]):
        self.tables = tables
        # Add a name mapping dictionary to keep track of original and display names
        self.display_names = {
            name: self._get_display_name(name) for name in tables.keys()
        }

    def _get_display_name(self, table_name: str) -> str:
        """Convert full table name to display name"""
        return table_name.replace("CyberRange_RESTAPI_", "..._")

    def _generate_excluded_tables_note(self, excluded_tables: List[str]) -> List[str]:
        """Generate a note showing excluded tables"""
        if not excluded_tables:
            return []

        # Sort and format table names for display
        excluded = sorted(
            t.replace("CyberRange_RESTAPI_", "..._") for t in excluded_tables
        )

        dot_output = [
            "note [label=<",
            '<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4">',  # Added CELLPADDING
            '<TR><TD BGCOLOR="#f0f0f0" HEIGHT="30"><B>Excluded Tables:</B></TD></TR>',  # Added HEIGHT
        ]

        for table in excluded:
            dot_output.append(
                f'<TR><TD ALIGN="LEFT" HEIGHT="22">{table}</TD></TR>'
            )  # Added HEIGHT

        dot_output.extend(["</TABLE>", '>, pos="0,0!", shape=none];'])
        return dot_output

    def generate(
        self, exclude_tables: List[str] = None, show_referenced: bool = False
    ) -> str:
        """
        Generate DOT format output from table definitions

        Args:
            exclude_tables: List of tables to exclude
            show_referenced: Whether to show referenced tables (default: False)
        """
        if exclude_tables:
            # First, find all referenced tables
            referenced_tables = set()
            for table in self.tables.values():
                for _, ref_table in table.foreign_keys:
                    ref_table = (
                        ref_table.split(".")[-1] if "." in ref_table else ref_table
                    )
                    referenced_tables.add(ref_table)

            # Determine which tables to keep
            if show_referenced:
                # Keep referenced tables
                actual_excludes = [
                    t for t in exclude_tables if t not in referenced_tables
                ]
                tables = {
                    k: v for k, v in self.tables.items() if k not in actual_excludes
                }
            else:
                # Only keep checked tables
                tables = {
                    k: v for k, v in self.tables.items() if k not in exclude_tables
                }

            print(f"Showing {len(tables)} tables", file=sys.stderr)
        else:
            tables = self.tables

        print(f"Generating diagram for {len(tables)} tables", file=sys.stderr)
        print(f"Tables: {list(tables.keys())}", file=sys.stderr)

        dot_output = [
            "digraph ERD {",
            "rankdir=TB;",
            "graph [splines=ortho, nodesep=1.2, ranksep=1.2];",
            'node [shape=none, fontsize=12, fontname="American Typewriter"];',
        ]

        # Add excluded tables note at the beginning
        if exclude_tables:
            dot_output.extend(self._generate_excluded_tables_note(exclude_tables))

        # Add tables
        for table_name, table in tables.items():
            dot_output.extend(self._generate_table_node(table))

        # Add relationships
        for table_name, table in tables.items():
            dot_output.extend(self._generate_relationships(table))

        dot_output.append("}")
        return "\n".join(dot_output)

    def _generate_table_node(self, table: Table) -> List[str]:
        """Generate DOT node definition for a table"""
        dot_output = []
        # Use original name for node ID, display name for label
        dot_output.append(f"{table.name} [label=<")
        dot_output.append('<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0">')

        # Table header with display name
        dot_output.append(
            f'<TR><TD BGCOLOR="lightblue"><B>{self.display_names[table.name]}</B></TD></TR>'
        )

        # Columns
        for column in table.columns:
            constraints_text = (
                f" ({', '.join(column.constraints)})" if column.constraints else ""
            )
            dot_output.append(
                f'<TR><TD ALIGN="LEFT"><b>{column.name}</b>: {column.type}{constraints_text}</TD></TR>'
            )

        # Table-level constraints
        for constraint in table.constraints:
            dot_output.append(
                f'<TR><TD ALIGN="LEFT" BGCOLOR="#f0f0f0"><I>{constraint.definition}</I></TD></TR>'
            )

        dot_output.append("</TABLE>>];")
        return dot_output

    def _generate_relationships(self, table: Table) -> List[str]:
        """Generate DOT edges for table relationships"""
        dot_output = []
        print(f"\nProcessing relationships for {table.name}", file=sys.stderr)
        print(f"Foreign keys: {table.foreign_keys}", file=sys.stderr)

        table_names_map = {t.upper(): t for t in self.tables.keys()}

        for column_name, referenced_table in table.foreign_keys:
            ref_table = (
                referenced_table.split(".")[-1]
                if "." in referenced_table
                else referenced_table
            )
            print(f"  Checking FK {column_name} -> {ref_table}", file=sys.stderr)

            # Try both original case and uppercase
            if ref_table in self.tables:
                actual_table = ref_table
            elif ref_table.upper() in table_names_map:
                actual_table = table_names_map[ref_table.upper()]
            else:
                print(f"    Referenced table not found", file=sys.stderr)
                continue

            print(f"    Adding relationship", file=sys.stderr)
            dot_output.append(
                f'{table.name} -> {actual_table} [xlabel="{column_name}"];'
            )
        return dot_output
