import sys
from datetime import datetime
from typing import Dict
from typing import List

from schema_reader import Table


class DotGenerator:
    def __init__(
        self, tables: Dict[str, Table], db_name: str = "unknown", table_prefix: str = ""
    ):
        self.tables = tables
        self.db_name = db_name
        self.table_prefix = table_prefix
        self.display_names = {
            name: self._get_display_name(name) for name in tables.keys()
        }

    def _get_display_name(self, table_name: str) -> str:
        """Convert full table name to display name"""
        if self.table_prefix and table_name.startswith(self.table_prefix):
            return "..." + table_name[len(self.table_prefix) :]
        return table_name

    def _generate_excluded_tables_note(self, excluded_tables: List[str]) -> List[str]:
        """Generate a note showing excluded tables"""
        if not excluded_tables:
            return []

        # Sort and format table names for display
        excluded = sorted(self._get_display_name(t) for t in excluded_tables)

        dot_output = [
            "note [label=<",
            '<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4">',
            '<TR><TD BGCOLOR="#f0f0f0" HEIGHT="30"><B>Excluded Tables:</B></TD></TR>',
        ]

        for table in excluded:
            dot_output.append(
                f'<TR><TD ALIGN="LEFT" HEIGHT="22">{table}</TD></TR>'
            )  # Added HEIGHT

        dot_output.extend(["</TABLE>", '>, pos="0,0!", shape=none];'])
        return dot_output

    def generate(
        self,
        exclude_tables: List[str] = None,
        show_referenced: bool = False,
        overview_mode: bool = False,
    ) -> str:
        """
        Generate DOT format output from table definitions

        Args:
            exclude_tables: List of tables to exclude
            show_referenced: Whether to show referenced tables (default: False)
            overview_mode: Whether to generate a simplified overview (default: False)
        """
        tables = self._get_filtered_tables(exclude_tables, show_referenced)

        dot_output = [
            "digraph ERD {",
            "rankdir=TB;",
            "graph [splines=ortho, nodesep=1.2, ranksep=1.2];",
            'node [shape=none, fontsize=12, fontname="American Typewriter"];',
            # Add title with box
            'labelloc="t";',
            'label=<<TABLE BORDER="1" CELLBORDER="0" CELLPADDING="10">',
            '<TR><TD BGCOLOR="#e8e8e8">',
            f'<FONT POINT-SIZE="24">{self._generate_title(len(self.tables), len(tables))}</FONT>',
            "</TD></TR>",
            "</TABLE>>;",
        ]

        # Add excluded tables note at the beginning
        if exclude_tables:
            dot_output.extend(self._generate_excluded_tables_note(exclude_tables))

        # Add tables
        for table_name, table in tables.items():
            dot_output.extend(self._generate_table_node(table, overview_mode))

        # Add relationships
        for table_name, table in tables.items():
            dot_output.extend(self._generate_relationships(table))

        dot_output.append("}")
        return "\n".join(dot_output)

    def _generate_title(self, total_tables: int, shown_tables: int) -> str:
        """Generate diagram title with metadata"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        db_label = self.db_name.upper()  # Make database name uppercase
        return f"{db_label}<BR/>{timestamp}<BR/>Total tables: {total_tables} | Shown: {shown_tables}"

    def _get_filtered_tables(
        self, exclude_tables: List[str], show_referenced: bool
    ) -> Dict[str, Table]:
        """Get filtered tables based on exclusion list and reference setting"""
        if not exclude_tables:
            return self.tables

        # Convert exclude_tables to set for faster lookups
        excluded = set(exclude_tables)

        # Get selected tables (those not excluded)
        selected_tables = {k: v for k, v in self.tables.items() if k not in excluded}

        if show_referenced:
            # Get tables referenced by selected tables
            referenced_tables = set()
            for table in selected_tables.values():
                for _, ref_table in table.foreign_keys:
                    ref_table = (
                        ref_table.split(".")[-1] if "." in ref_table else ref_table
                    )
                    referenced_tables.add(ref_table)

            # Add referenced tables to the result
            return {
                k: v
                for k, v in self.tables.items()
                if k not in excluded or k in referenced_tables
            }
        else:
            return selected_tables

    def _generate_table_node(
        self, table: Table, overview_mode: bool = False
    ) -> List[str]:
        """Generate DOT node definition for a table"""
        dot_output = []
        dot_output.append(f"{table.name} [label=<")
        dot_output.append('<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0">')

        if overview_mode:
            # Overview mode: simple square node with fixed size and  yellow background
            dot_output.append(
                f'<TR><TD BGCOLOR="lightyellow" WIDTH="170" HEIGHT="240">'
                f"<B>{self.display_names[table.name]}</B>"
                f"</TD></TR>"
            )
        else:
            # Detailed mode: show all columns and constraints
            # Table header
            dot_output.append(
                f'<TR><TD BGCOLOR="lightblue"><B>{self.display_names[table.name]}</B></TD></TR>'
            )

            # Group constraints by type
            pk_constraints = []
            other_constraints = []
            for constraint in table.constraints:
                if constraint.type == "PRIMARY KEY":
                    pk_constraints = constraint.columns
                else:
                    other_constraints.append(constraint)

            # Columns with inline PK markers
            for column in table.columns:
                col_name = column.name
                if col_name in pk_constraints:
                    col_name = f"{col_name} 🔑"  # Add key emoji for primary keys

                constraints_text = ""
                if column.constraints and "PRIMARY KEY" not in column.constraints:
                    constraints_text = f" ({', '.join(c for c in column.constraints if c != 'PRIMARY KEY')})"

                dot_output.append(
                    f'<TR><TD ALIGN="LEFT" PORT="{column.name}"><B>{col_name}</B>: {column.type}{constraints_text}</TD></TR>'
                )

            # Add remaining constraints
            for constraint in other_constraints:
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
                print("    Referenced table not found", file=sys.stderr)
                continue

            print("    Adding relationship", file=sys.stderr)
            dot_output.append(
                f'{table.name} -> {actual_table} [xlabel="{column_name}"];'
            )
        return dot_output
