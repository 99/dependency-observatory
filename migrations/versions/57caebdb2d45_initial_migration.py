"""initial migration

Revision ID: 57caebdb2d45
Revises:
Create Date: 2020-05-19 19:16:26.305985

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "57caebdb2d45"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "advisories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "language",
            postgresql.ENUM("node", "rust", "python", name="language_enum"),
            nullable=False,
        ),
        sa.Column("package_name", sa.String(), nullable=True),
        sa.Column("npm_advisory_id", sa.Integer(), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("severity", sa.String(), nullable=True),
        sa.Column("cwe", sa.Integer(), nullable=True),
        sa.Column("cves", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("exploitability", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("vulnerable_versions", sa.String(), nullable=True),
        sa.Column("patched_versions", sa.String(), nullable=True),
        sa.Column(
            "vulnerable_package_version_ids",
            postgresql.ARRAY(sa.Integer()),
            nullable=True,
        ),
        sa.Column("created", sa.DateTime(), nullable=True),
        sa.Column("updated", sa.DateTime(), nullable=True),
        sa.Column(
            "inserted_at",
            sa.DateTime(),
            server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", "language"),
        sa.UniqueConstraint("id"),
    )
    op.create_index(
        "advisories_inserted_idx",
        "advisories",
        ["inserted_at", sa.text("inserted_at DESC")],
        unique=False,
    )
    op.create_index("advisories_language_idx", "advisories", ["language"], unique=False)
    op.create_index(
        "advisories_npm_advisory_id_idx",
        "advisories",
        ["npm_advisory_id"],
        unique=False,
    )
    op.create_index(
        "advisories_pkg_name_idx", "advisories", ["package_name"], unique=False
    )
    op.create_index(
        "advisories_vulnerable_package_version_ids_idx",
        "advisories",
        ["vulnerable_package_version_ids"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_table(
        "npm_registry_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("package_name", sa.String(), nullable=False),
        sa.Column("package_version", sa.String(), nullable=False),
        sa.Column("shasum", sa.String(), nullable=False),
        sa.Column("tarball", sa.String(), nullable=False),
        sa.Column("git_head", sa.String(), nullable=True),
        sa.Column("repository_type", sa.String(), nullable=True),
        sa.Column("repository_url", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("license_type", sa.String(), nullable=True),
        sa.Column("license_url", sa.String(), nullable=True),
        sa.Column("keywords", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("has_shrinkwrap", sa.Boolean(), nullable=True),
        sa.Column("bugs_url", sa.String(), nullable=True),
        sa.Column("bugs_email", sa.String(), nullable=True),
        sa.Column("author_name", sa.String(), nullable=True),
        sa.Column("author_email", sa.String(), nullable=True),
        sa.Column("author_url", sa.String(), nullable=True),
        sa.Column(
            "maintainers", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "contributors", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("publisher_name", sa.String(), nullable=True),
        sa.Column("publisher_email", sa.String(), nullable=True),
        sa.Column("publisher_node_version", sa.String(), nullable=True),
        sa.Column("publisher_npm_version", sa.String(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("package_modified_at", sa.DateTime(), nullable=True),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column(
            "inserted_at",
            sa.DateTime(),
            server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint(
            "id", "package_name", "package_version", "shasum", "tarball"
        ),
    )
    op.create_index(
        "npm_registry_entries_contributors_idx",
        "npm_registry_entries",
        ["contributors"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "npm_registry_entries_inserted_idx",
        "npm_registry_entries",
        ["inserted_at", sa.text("inserted_at DESC")],
        unique=False,
    )
    op.create_index(
        "npm_registry_entries_maintainers_idx",
        "npm_registry_entries",
        ["maintainers"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "npm_registry_entries_unique_idx",
        "npm_registry_entries",
        ["package_name", "package_version", "shasum", "tarball"],
        unique=True,
    )
    op.create_index(
        "npm_registry_entries_updated_idx",
        "npm_registry_entries",
        ["updated_at", sa.text("updated_at DESC")],
        unique=False,
    )
    op.create_table(
        "npmsio_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("package_name", sa.String(), nullable=False),
        sa.Column("package_version", sa.String(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("score", sa.Numeric(), nullable=True),
        sa.Column("quality", sa.Numeric(), nullable=True),
        sa.Column("popularity", sa.Numeric(), nullable=True),
        sa.Column("maintenance", sa.Numeric(), nullable=True),
        sa.Column("branding", sa.Numeric(), nullable=True),
        sa.Column("carefulness", sa.Numeric(), nullable=True),
        sa.Column("health", sa.Numeric(), nullable=True),
        sa.Column("tests", sa.Numeric(), nullable=True),
        sa.Column("community_interest", sa.Integer(), nullable=True),
        sa.Column("dependents_count", sa.Integer(), nullable=True),
        sa.Column("downloads_count", sa.Numeric(), nullable=True),
        sa.Column("downloads_acceleration", sa.Numeric(), nullable=True),
        sa.Column("commits_frequency", sa.Numeric(), nullable=True),
        sa.Column("issues_distribution", sa.Numeric(), nullable=True),
        sa.Column("open_issues", sa.Numeric(), nullable=True),
        sa.Column("releases_frequency", sa.Numeric(), nullable=True),
        sa.Column(
            "inserted_at",
            sa.DateTime(),
            server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", "package_name", "package_version", "analyzed_at"),
    )
    op.create_index(
        "npmsio_scores_analyzed_idx",
        "npmsio_scores",
        ["analyzed_at", sa.text("analyzed_at DESC")],
        unique=False,
    )
    op.create_index(
        "npmsio_scores_inserted_idx",
        "npmsio_scores",
        ["inserted_at", sa.text("inserted_at DESC")],
        unique=False,
    )
    op.create_index(
        "npmsio_scores_unique_idx",
        "npmsio_scores",
        ["package_name", "package_version", "analyzed_at"],
        unique=True,
    )
    op.create_index(
        "npmsio_scores_updated_idx",
        "npmsio_scores",
        ["updated_at", sa.text("updated_at DESC")],
        unique=False,
    )
    op.create_table(
        "package_graphs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("root_package_version_id", sa.Integer(), nullable=False),
        sa.Column("link_ids", postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column(
            "package_manager",
            postgresql.ENUM("npm", "yarn", name="package_manager_enum"),
            nullable=True,
        ),
        sa.Column("package_manager_version", sa.String(), nullable=True),
        sa.Column(
            "inserted_at",
            sa.DateTime(),
            server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", "root_package_version_id"),
    )
    op.create_index(
        "package_graphs_inserted_idx",
        "package_graphs",
        ["inserted_at", sa.text("inserted_at DESC")],
        unique=False,
    )
    op.create_index(
        "package_graphs_link_ids_idx",
        "package_graphs",
        ["link_ids"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "package_graphs_package_manager_idx",
        "package_graphs",
        ["package_manager"],
        unique=False,
    )
    op.create_index(
        "package_graphs_package_manager_version_idx",
        "package_graphs",
        ["package_manager_version"],
        unique=False,
    )
    op.create_index(
        "package_graphs_root_package_id_idx",
        "package_graphs",
        ["root_package_version_id"],
        unique=False,
    )
    op.create_table(
        "package_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("child_package_id", sa.Integer(), nullable=False),
        sa.Column("parent_package_id", sa.Integer(), nullable=False),
        sa.Column(
            "inserted_at",
            sa.DateTime(),
            server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", "child_package_id", "parent_package_id"),
        sa.UniqueConstraint("id"),
    )
    op.create_index(
        "package_links_inserted_idx",
        "package_links",
        ["inserted_at", sa.text("inserted_at DESC")],
        unique=False,
    )
    op.create_index(
        "package_links_unique_idx",
        "package_links",
        ["child_package_id", "parent_package_id"],
        unique=True,
    )
    op.create_table(
        "package_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column(
            "language",
            postgresql.ENUM("node", "rust", "python", name="language_enum"),
            nullable=False,
        ),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("repo_url", sa.String(), nullable=True),
        sa.Column("repo_commit", sa.LargeBinary(), nullable=True),
        sa.Column(
            "inserted_at",
            sa.DateTime(),
            server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", "name", "version", "language"),
    )
    op.create_index(
        "package_versions_inserted_idx",
        "package_versions",
        ["inserted_at", sa.text("inserted_at DESC")],
        unique=False,
    )
    op.create_index(
        "package_versions_unique_idx",
        "package_versions",
        ["name", "version", "language"],
        unique=True,
    )
    op.create_table(
        "reports",
        sa.Column("package", sa.String(length=200), nullable=True),
        sa.Column("version", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=200), nullable=True),
        sa.Column("release_date", sa.DateTime(), nullable=True),
        sa.Column("scoring_date", sa.DateTime(), nullable=True),
        sa.Column("top_score", sa.Integer(), nullable=True),
        sa.Column("npmsio_score", sa.Float(), nullable=True),
        sa.Column("npmsio_scored_package_version", sa.String(), nullable=True),
        sa.Column("directVulnsCritical_score", sa.Integer(), nullable=True),
        sa.Column("directVulnsHigh_score", sa.Integer(), nullable=True),
        sa.Column("directVulnsMedium_score", sa.Integer(), nullable=True),
        sa.Column("directVulnsLow_score", sa.Integer(), nullable=True),
        sa.Column("indirectVulnsCritical_score", sa.Integer(), nullable=True),
        sa.Column("indirectVulnsHigh_score", sa.Integer(), nullable=True),
        sa.Column("indirectVulnsMedium_score", sa.Integer(), nullable=True),
        sa.Column("indirectVulnsLow_score", sa.Integer(), nullable=True),
        sa.Column("authors", sa.Integer(), nullable=True),
        sa.Column("contributors", sa.Integer(), nullable=True),
        sa.Column("immediate_deps", sa.Integer(), nullable=True),
        sa.Column("all_deps", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.String(length=155), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "package_dependencies",
        sa.Column("depends_on_id", sa.Integer(), nullable=False),
        sa.Column("used_by_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["depends_on_id"], ["reports.id"],),
        sa.ForeignKeyConstraint(["used_by_id"], ["reports.id"],),
        sa.PrimaryKeyConstraint("depends_on_id", "used_by_id"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("package_dependencies")
    op.drop_table("reports")
    op.drop_index("package_versions_unique_idx", table_name="package_versions")
    op.drop_index("package_versions_inserted_idx", table_name="package_versions")
    op.drop_table("package_versions")
    op.drop_index("package_links_unique_idx", table_name="package_links")
    op.drop_index("package_links_inserted_idx", table_name="package_links")
    op.drop_table("package_links")
    op.drop_index("package_graphs_root_package_id_idx", table_name="package_graphs")
    op.drop_index(
        "package_graphs_package_manager_version_idx", table_name="package_graphs"
    )
    op.drop_index("package_graphs_package_manager_idx", table_name="package_graphs")
    op.drop_index("package_graphs_link_ids_idx", table_name="package_graphs")
    op.drop_index("package_graphs_inserted_idx", table_name="package_graphs")
    op.drop_table("package_graphs")
    op.drop_index("npmsio_scores_updated_idx", table_name="npmsio_scores")
    op.drop_index("npmsio_scores_unique_idx", table_name="npmsio_scores")
    op.drop_index("npmsio_scores_inserted_idx", table_name="npmsio_scores")
    op.drop_index("npmsio_scores_analyzed_idx", table_name="npmsio_scores")
    op.drop_table("npmsio_scores")
    op.drop_index("npm_registry_entries_updated_idx", table_name="npm_registry_entries")
    op.drop_index("npm_registry_entries_unique_idx", table_name="npm_registry_entries")
    op.drop_index(
        "npm_registry_entries_maintainers_idx", table_name="npm_registry_entries"
    )
    op.drop_index(
        "npm_registry_entries_inserted_idx", table_name="npm_registry_entries"
    )
    op.drop_index(
        "npm_registry_entries_contributors_idx", table_name="npm_registry_entries"
    )
    op.drop_table("npm_registry_entries")
    op.drop_index(
        "advisories_vulnerable_package_version_ids_idx", table_name="advisories"
    )
    op.drop_index("advisories_pkg_name_idx", table_name="advisories")
    op.drop_index("advisories_npm_advisory_id_idx", table_name="advisories")
    op.drop_index("advisories_language_idx", table_name="advisories")
    op.drop_index("advisories_inserted_idx", table_name="advisories")
    op.drop_table("advisories")
    # ### end Alembic commands ###
