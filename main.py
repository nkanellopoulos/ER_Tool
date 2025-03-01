import os
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


# Define tables to exclude
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
        conn_string = os.getenv("DB_CONNECTION")
        if conn_string:
            try:
                print("Attempting database connection...", file=sys.stderr)
                tables = SchemaReader.from_database(conn_string)
                if not tables:
                    raise Exception("No tables found in database")
                print(
                    f"Successfully read {len(tables)} tables from database",
                    file=sys.stderr,
                )
            except Exception as e:
                print(f"Database connection failed: {e}", file=sys.stderr)
                print("Falling back to DDL parsing...", file=sys.stderr)
                file_path = sys.argv[1] if len(sys.argv) > 1 else None
                ddl = read_ddl_input(file_path)
                tables = SchemaReader.from_ddl(ddl)
        else:
            file_path = sys.argv[1] if len(sys.argv) > 1 else None
            ddl = read_ddl_input(file_path)
            tables = SchemaReader.from_ddl(ddl)

        if not tables:
            raise Exception("No tables found in input")

        print(f"Found {len(tables)} tables", file=sys.stderr)
        print(f"Tables: {list(tables.keys())}", file=sys.stderr)

        generator = DotGenerator(tables)
        print(generator.generate(exclude_tables=EXCLUDE_TABLES))  # Re-enable exclusions

    except Exception as e:
        print(f"An error occurred: {str(e)}", file=sys.stderr)
        import traceback

        print(traceback.format_exc(), file=sys.stderr)
        sys.exit(1)  # Exit with error code


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
