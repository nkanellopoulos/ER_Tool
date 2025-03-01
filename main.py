import os
import re
import sys

from dot_generator import DotGenerator
from schema_reader import SchemaReader


def read_ddl_input(file_path=None):
    if file_path and os.path.isfile(file_path):
        with open(file_path, "r") as file:
            return file.read()
    else:
        print("Please enter the DDL statements, followed by an EOF (Ctrl+D on Unix):")
        return sys.stdin.read()


def parse_ddl(ddl):
    tables = {}

    table_pattern = re.compile(
        r'CREATE TABLE\s+(?:\w+\.)?"?(\w+)"?\s*\((.*?)\);\s*', re.IGNORECASE | re.DOTALL
    )
    column_pattern = re.compile(
        r'^\s*"?(?P<name>\w+)"?\s+(?P<type>[a-zA-Z0-9\s\(\)]+)(?P<constraints>(?:[^,]*(?:constraint\s+\w+\s+)?(?:references|unique|primary\s+key|not\s+null)[^,]*|[^,]*)*)(?=,|\s*$)',
        re.IGNORECASE | re.MULTILINE,
    )
    fk_pattern = re.compile(r'\s+REFERENCES\s+(?:\w+\.)?"?(\w+)"?', re.IGNORECASE)
    unique_pattern = re.compile(r"unique\s*\((.*?)\)", re.IGNORECASE)
    multi_col_constraint_pattern = re.compile(
        r'CONSTRAINT\s+"\w+"\s+UNIQUE\s*\((.*?)\)', re.IGNORECASE
    )

    matches = table_pattern.finditer(ddl)
    for match in matches:
        current_table = match.group(1)
        tables[current_table] = {
            "columns": [],
            "foreign_keys": [],
            "table_constraints": [],
        }

        table_def = match.group(2)
        table_constraints = {}
        multi_column_fields = (
            set()
        )  # Track fields that are part of multi-column constraints

        # First pass: collect multi-column constraints
        for constraint_match in multi_col_constraint_pattern.finditer(table_def):
            columns = [
                c.strip().strip('"') for c in constraint_match.group(1).split(",")
            ]
            constraint_text = f"UNIQUE({', '.join(columns)})"
            tables[current_table]["table_constraints"].append(constraint_text)
            # Track these columns as part of multi-column constraint
            multi_column_fields.update(columns)

        # Second pass: process columns
        for col_match in column_pattern.finditer(table_def):
            column_name = col_match.group("name").strip()
            if not column_name or column_name.lower() in (
                "constraint",
                "unique",
                "primary key",
            ):
                continue

            column_type = col_match.group("type").strip()
            constraints = col_match.group("constraints").strip()

            # Build column detail string
            constraints_list = []
            if "NOT NULL" in constraints.upper():
                constraints_list.append("NN")
            if "PRIMARY KEY" in constraints.upper():
                constraints_list.append("PK")
            # Only add UNIQUE if it's a single-column unique constraint
            if (
                "UNIQUE" in constraints.upper()
                and column_name not in multi_column_fields
            ):
                constraints_list.append("UNIQUE")
            if "REFERENCES" in constraints.upper():  # Changed this condition
                constraints_list.append("FK")

            column_detail = f"<b>{column_name}</b>:  {column_type}"
            # Remove unwanted text and clean up the output
            column_detail = (
                column_detail.replace("constraint", "").replace("  ", " ").strip()
            )
            if constraints_list:
                column_detail += f" ({', '.join(constraints_list)})"

            tables[current_table]["columns"].append(column_detail.strip())

            # Handle foreign keys
            if "REFERENCES" in constraints.upper():
                fk_match = fk_pattern.search(constraints)
                if fk_match:
                    fk_ref_table = fk_match.group(1).strip().replace('"', "")
                    tables[current_table]["foreign_keys"].append(
                        (column_name, fk_ref_table)
                    )

    return tables


def generate_dot_diagram(ddl, exclude_tables):
    parsed_tables = parse_ddl(ddl)

    for table in exclude_tables:
        if table in parsed_tables:
            del parsed_tables[table]

    # dot_output = ['digraph ERD {',
    #                 'graph [splines=ortho, nodesep=1.2, ranksep=1.4];']
    # dot_output.append('node [shape=none, fontsize=11, fontname="Helvetica"];')
    dot_output = [
        "digraph ERD {",
        "rankdir=TB;",
        "graph [splines=ortho, nodesep=1.2, ranksep=1.2];",
        'node [shape=none, fontsize=12, fontname="American Typewriter"];',
    ]

    for table, info in parsed_tables.items():
        print(f"Table: {table}", file=sys.stderr)
        dot_output.append(f"{table} [label=<")
        dot_output.append('<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0">')
        shortened_table = table.replace("CyberRange_RESTAPI_", "..._")
        dot_output.append(
            f'<TR><TD BGCOLOR="lightblue"><B>{shortened_table}</B></TD></TR>'
        )

        for column in info["columns"]:
            if column.find("_uniq") > 0:
                # print(f"\n\n\nUniq: f{column}\n\n")
                column = "".join(column.split(" ")[2:])

            dot_output.append(f'<TR><TD ALIGN="LEFT">{column}</TD></TR>')

        # Add table-level constraints at the bottom
        for constraint in info.get("table_constraints", []):
            dot_output.append(
                f'<TR><TD ALIGN="LEFT" BGCOLOR="#f0f0f0"><I>{constraint}</I></TD></TR>'
            )

        dot_output.append("</TABLE>>];")

    for table, info in parsed_tables.items():
        for fk_column, fk_ref_table in info["foreign_keys"]:
            if fk_ref_table in parsed_tables:
                dot_output.append(f'{table} -> {fk_ref_table} [xlabel="{fk_column}"];')
                # dot_output.append(f'{table} -> {fk_ref_table} [xlabel="1:many"];')

    dot_output.append("}")
    return "\n".join(dot_output)


EXCLUDE_TABLES = [
    "CyberRange_RESTAPI_bibliography",
    "CyberRange_RESTAPI_scenario_bibliography",
    "CyberRange_RESTAPI_scenario_cves",
    "CyberRange_RESTAPI_scenario_cwes",
    "CyberRange_RESTAPI_scenario_mitreTactics",
    "CyberRange_RESTAPI_cve",
    "CyberRange_RESTAPI_cwe",
    "CyberRange_RESTAPI_difficulty",
    "CyberRange_RESTAPI_mitretactic",
    "CyberRange_RESTAPI_mitretechnique",
    "CyberRange_RESTAPI_mitretechnique_tactics",
    "CyberRange_RESTAPI_progressioninstance",
    "CyberRange_RESTAPI_progressioninstance_events",
    "CyberRange_RESTAPI_progressioninstance_states",
    "CyberRange_RESTAPI_progressioninstance_transitions",
    "CyberRange_RESTAPI_role",
    "CyberRange_RESTAPI_scenario_role",
    "CyberRange_RESTAPI_scenario_standards",
    "CyberRange_RESTAPI_scenario_trainingType",
    # "CyberRange_RESTAPI_scenariodependencies_dependencies",
    "CyberRange_RESTAPI_skill",
    "CyberRange_RESTAPI_standard",
    "CyberRange_RESTAPI_state",
    "CyberRange_RESTAPI_state_onEnterEvent",
    "CyberRange_RESTAPI_state_onExitEvent",
    "CyberRange_RESTAPI_statemachine",
    "CyberRange_RESTAPI_statemachine_events",
    "CyberRange_RESTAPI_statemachine_states",
    "CyberRange_RESTAPI_statemachine_transitions",
    "CyberRange_RESTAPI_trainingtype",
    "CyberRange_RESTAPI_transition",
    "CyberRange_RESTAPI_usermetadata_createdInstances",
    "CyberRange_RESTAPI_usermetadata_reviews",
    "CyberRange_RESTAPI_usertrainingtime",
    "CyberRange_RESTAPI_assignedscenario_programmeTrainer",
    # "CyberRange_RESTAPI_programme_prerequisiteProgrammes",
    "django_content_type",
    "auth_permission",
    "auth_group",
    "auth_group_permissions",
    "django_migrations",
    "auth_user",
    "auth_user_groups",
    "auth_user_user_permissions",
    "django_admin_log",
    "django_session",
]


def main():
    try:
        # Try database connection first
        conn_string = os.getenv("DB_CONNECTION")
        if conn_string:
            try:
                tables = SchemaReader.from_database(conn_string)
            except Exception as e:
                print(f"Database connection failed: {e}", file=sys.stderr)
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
        print(generator.generate(exclude_tables=EXCLUDE_TABLES))

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()


ddl = """
create table public."CyberRange_RESTAPI_role"
(
    id          uuid         not null primary key,
    name        varchar(255) not null,
    value       varchar(255) not null,
    description text         not null,
    framework   varchar(255) not null
);

alter table public."CyberRange_RESTAPI_role"
    owner to asdf;

create index "CyberRange__id_b05344_idx"
    on public."CyberRange_RESTAPI_role" (id);

create table public."CyberRange_RESTAPI_scenario"
(
    id              uuid         not null primary key,
    name            varchar(255) not null,
    description     text         not null,
    goal            text         not null,
    "successRate"   integer      not null,
    duration        integer      not null,
    "validFrom"     timestamp with time zone,
    "validUntil"    timestamp with time zone,
    status          varchar(50)  not null,
    "isInteractive" boolean      not null,
    "isAssessment"  boolean      not null,
    revision        varchar(255) not null,
    difficulty_id   uuid         not null
        constraint "CyberRange_RESTAPI_s_difficulty_id_bebea7f4_fk_CyberRang"
            references public."CyberRange_RESTAPI_difficulty"
            deferrable initially deferred
);

alter table public."CyberRange_RESTAPI_scenario"
    owner to asdf;

create table public."CyberRange_RESTAPI_assignedscenario"
(
    id          uuid not null primary key,
    "dueDate"   timestamp with time zone,
    scenario_id uuid not null
        constraint "CyberRange_RESTAPI_a_scenario_id_02847723_fk_CyberRang"
            references public."CyberRange_RESTAPI_scenario"
            deferrable initially deferred
);

alter table public."CyberRange_RESTAPI_assignedscenario"
    owner to asdf;

create index "CyberRange__id_f0da9b_idx"
    on public."CyberRange_RESTAPI_assignedscenario" (id);

create index "CyberRange_RESTAPI_assignedscenario_scenario_id_02847723"
    on public."CyberRange_RESTAPI_assignedscenario" (scenario_id);

create table public."CyberRange_RESTAPI_programme"
(
    id                        uuid        not null primary key,
    name                      varchar(50) not null
        unique,
    summary                   text        not null,
    "estimatedCompletionTime" bigint      not null,
    status                    varchar(50) not null,
    "validFrom"               timestamp with time zone,
    "validUntil"              timestamp with time zone,
    assessment_id             uuid
        unique
        constraint "CyberRange_RESTAPI_p_assessment_id_97fb3fe6_fk_CyberRang"
            references public."CyberRange_RESTAPI_scenario"
            deferrable initially deferred,
    difficulty_id             uuid        not null
        constraint "CyberRange_RESTAPI_p_difficulty_id_6a85c60f_fk_CyberRang"
            references public."CyberRange_RESTAPI_difficulty"
            deferrable initially deferred,
    "updatedProgramme_id"     uuid
        unique
        constraint "CyberRange_RESTAPI_p_updatedProgramme_id_ec0169ed_fk_CyberRang"
            references public."CyberRange_RESTAPI_programme"
            deferrable initially deferred
);

alter table public."CyberRange_RESTAPI_programme"
    owner to asdf;

"""
