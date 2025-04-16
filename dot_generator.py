import sys
import time  # Add this import for timing
from datetime import datetime
from typing import Dict
from typing import List
from typing import Set

from schema_reader import Table

# Constants
DEFAULT_FONT = "American Typewriter"  # Use original font


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
        # Set the default to false: don't show excluded tables note
        self.draw_excluded_tables_note = False
        # Dark mode settings
        self.dark_mode = False
        self.highlight_color = "blue"

    def _get_display_name(self, table_name: str) -> str:
        """Convert full table name to display name"""
        # Cache display names for better performance
        if not hasattr(self, "_display_name_cache"):
            self._display_name_cache = {}

        if table_name in self._display_name_cache:
            return self._display_name_cache[table_name]

        result = table_name
        if self.table_prefix and table_name.startswith(self.table_prefix):
            result = "..." + table_name[len(self.table_prefix) :]

        self._display_name_cache[table_name] = result
        return result

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
        matching_tables: Set[str] = None,
        matching_fields: Dict[str, List[str]] = None,
        show_only_filtered: bool = False,  # Add show_only_filtered parameter
        dark_mode: bool = False,  # Add dark mode parameter
    ) -> str:
        """
        Generate DOT format output from table definitions

        Args:
            exclude_tables: List of tables to exclude
            show_referenced: Whether to show referenced tables (default: False)
            overview_mode: Whether to generate a simplified overview (default: False)
            matching_tables: Set of table names that match the filter
            matching_fields: Dictionary mapping table names to lists of field names that match the filter
            show_only_filtered: Whether to show only tables matching the filter
            dark_mode: Whether to use dark mode colors
        """
        # Save dark mode setting
        self.dark_mode = dark_mode

        # Reduced logging to help track real issues
        if exclude_tables is None:
            exclude_tables = []
        if matching_tables is None:
            matching_tables = set()
        if matching_fields is None:
            matching_fields = {}

        # Get filtered tables
        tables = self._get_filtered_tables(exclude_tables, show_referenced)

        # Further filter to only show matching tables if requested
        if show_only_filtered and matching_tables:
            tables = {k: v for k, v in tables.items() if k in matching_tables}

        # Start DOT file with appropriate colors based on mode
        if dark_mode:
            # Dark mode: 50% gray background, but keep arrows black
            dot_output = [
                "digraph ERD {",
                "rankdir=TB;",
                'bgcolor="#b1b1b1";',  # gray background
                "graph [splines=ortho, nodesep=1.2, ranksep=1.2];",
                f'node [shape=none, fontsize=12, fontname="{DEFAULT_FONT}"];',
                f'edge [fontname="{DEFAULT_FONT}"];',  # Keep arrows black in dark mode
            ]
        else:
            # Light mode: default white background, black arrows
            dot_output = [
                "digraph ERD {",
                "rankdir=TB;",
                "graph [splines=ortho, nodesep=1.2, ranksep=1.2];",
                f'node [shape=none, fontsize=12, fontname="{DEFAULT_FONT}"];',
                f'edge [fontname="{DEFAULT_FONT}"];',
            ]

        # Add title with box - darker in dark mode
        if dark_mode:
            dot_output.extend(
                [
                    'labelloc="t";',
                    'label=<<TABLE BORDER="1" CELLBORDER="0" CELLPADDING="10">',
                    '<TR><TD BGCOLOR="#404040">',  # Darker background for title in dark mode
                    f'<FONT POINT-SIZE="24" COLOR="white">{self._generate_title(len(self.tables), len(tables))}</FONT>',
                    "</TD></TR>",
                    "</TABLE>>;",
                ]
            )
        else:
            dot_output.extend(
                [
                    'labelloc="t";',
                    'label=<<TABLE BORDER="1" CELLBORDER="0" CELLPADDING="10">',
                    '<TR><TD BGCOLOR="#e8e8e8">',
                    f'<FONT POINT-SIZE="24">{self._generate_title(len(self.tables), len(tables))}</FONT>',
                    "</TD></TR>",
                    "</TABLE>>;",
                ]
            )

        # Add excluded tables note only if enabled and there are excluded tables
        if self.draw_excluded_tables_note and exclude_tables:
            dot_output.extend(self._generate_excluded_tables_note(exclude_tables))

        # Add filter status note if filtered view is active
        if show_only_filtered and matching_tables:
            dot_output.extend(self._generate_filter_note(len(matching_tables)))

        # Add tables
        for table_name, table in tables.items():
            highlight = table_name in matching_tables
            table_fields = matching_fields.get(table_name, [])
            dot_output.extend(
                self._generate_table_node(table, overview_mode, highlight, table_fields)
            )

        # Add relationships
        for table_name, table in tables.items():
            dot_output.extend(self._generate_relationships(table))

        dot_output.append("}")
        return "\n".join(dot_output)

    def _generate_filter_note(self, matches_count: int) -> List[str]:
        """Generate a note showing filter status"""
        dot_output = [
            "filter_note [label=<",
            '<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4">',
            '<TR><TD BGCOLOR="#fff0f0" HEIGHT="30"><B>Filtered View</B></TD></TR>',
            f'<TR><TD ALIGN="LEFT" HEIGHT="22">Showing {matches_count} matching tables</TD></TR>',
            "</TABLE>",
            '>, pos="0,0!", shape=none];',
        ]
        return dot_output

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
        self,
        table: Table,
        overview_mode: bool = False,
        highlight: bool = False,
        matching_fields: List[str] = None,
    ) -> List[str]:
        """Generate DOT node definition for a table"""
        if matching_fields is None:
            matching_fields = []

        dot_output = []
        # Set the table border color and width based on highlight status
        # Always use black borders (or highlight color for highlighted tables) regardless of dark mode
        border_color = self.highlight_color if highlight else "black"
        border_width = 3 if highlight else 1

        # Determine if the table name should be highlighted based on the highlight flag
        table_name_color = self.highlight_color if highlight else "black"
        table_name_style = ' style="bold"' if highlight else ""

        # Add the node with HTML table label
        dot_output.append(f"{table.name} [label=<")

        # Main table tag with border color for the outer border
        # Set CELLBORDER=0 to disable the default cell borders
        dot_output.append(
            f'<TABLE BORDER="{border_width}" CELLSPACING="0" CELLBORDER="0" COLOR="{border_color}">'
        )

        if overview_mode:
            # Overview mode: simple square node with fixed size and yellow background
            # Keep table backgrounds white in dark mode
            bg_color = "lightyellow"
            dot_output.append(
                f'<TR><TD BGCOLOR="{bg_color}" WIDTH="170" HEIGHT="240">'
                f'<FONT COLOR="{table_name_color}"{table_name_style}><B>{self.display_names[table.name]}</B></FONT>'
                f"</TD></TR>"
            )
        else:
            # Table header with custom border
            dot_output.append(
                f'<TR><TD BGCOLOR="lightblue" BORDER="1" COLOR="black">'
                f'<FONT COLOR="{table_name_color}"{table_name_style}><B>{self.display_names[table.name]}</B></FONT>'
                f"</TD></TR>"
            )

            # Group constraints by type
            pk_constraints = []
            other_constraints = []
            for constraint in table.constraints:
                if constraint.type == "PRIMARY KEY":
                    pk_constraints = constraint.columns
                else:
                    other_constraints.append(constraint)

            # Columns with inline PK markers - always use black borders
            for column in table.columns:
                col_name = column.name
                if col_name in pk_constraints:
                    col_name = f"{col_name} 🔑"  # Add key emoji for primary keys

                constraints_text = ""
                if column.constraints and "PRIMARY KEY" not in column.constraints:
                    constraints_text = f" ({', '.join(c for c in column.constraints if c != 'PRIMARY KEY')})"

                # Highlight matching fields with the highlight color
                font_color = (
                    self.highlight_color if column.name in matching_fields else "black"
                )
                font_style = ' style="bold"' if column.name in matching_fields else ""

                # Explicitly set cell border to black
                dot_output.append(
                    f'<TR><TD ALIGN="LEFT" PORT="{column.name}" BGCOLOR="white" BORDER="1" COLOR="black">'
                    f'<FONT COLOR="{font_color}" FACE="{DEFAULT_FONT}"{font_style}><B>{col_name}</B>: {column.type}{constraints_text}</FONT>'
                    f"</TD></TR>"
                )

            # Add remaining constraints with border - keep light bg and use black borders
            for constraint in other_constraints:
                dot_output.append(
                    f'<TR><TD ALIGN="LEFT" BGCOLOR="#f0f0f0" BORDER="1" COLOR="black"><I>{constraint.definition}</I></TD></TR>'
                )

        dot_output.append("</TABLE>>];")
        return dot_output

    def _generate_relationships(self, table: Table) -> List[str]:
        """Generate DOT edges for table relationships"""
        dot_output = []
        table_names_map = {t.upper(): t for t in self.tables.keys()}

        for column_name, referenced_table in table.foreign_keys:
            ref_table = (
                referenced_table.split(".")[-1]
                if "." in referenced_table
                else referenced_table
            )

            # Try both original case and uppercase
            if ref_table in self.tables:
                actual_table = ref_table
            elif ref_table.upper() in table_names_map:
                actual_table = table_names_map[ref_table.upper()]
            else:
                continue

            # Keep arrows black in both modes for better readability
            dot_output.append(
                f'{table.name} -> {actual_table} [xlabel="{column_name}"];'
            )

        return dot_output
