"""allow multiple sites (profiles) per owner

Revision ID: 0017_multi_site_per_owner
Revises: 0016_ranked_fts

Drops the one-profile-per-owner uniqueness so an authenticated user can own
many "sites" (each an AssistantProfile + its single WidgetInstallation). The
1:1 widget_installations.profile_id uniqueness is intentionally preserved
(one widget per website). ``conversations`` need no installation_id column:
``Conversation.profile_id`` already identifies the site 1:1. Revisit that only
if N-installations-per-profile is ever introduced.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0017_multi_site_per_owner"
down_revision: Union[str, None] = "0016_ranked_fts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # In Postgres the unique constraint owns its backing index, so dropping it
    # removes both; recreate a plain (non-unique) index for owner lookups.
    op.drop_constraint(
        "uq_assistant_profiles_owner_user_id", "assistant_profiles", type_="unique"
    )
    op.create_index(
        "ix_assistant_profiles_owner_user_id",
        "assistant_profiles",
        ["owner_user_id"],
        unique=False,
    )


def downgrade() -> None:
    # Note: recreating the unique constraint fails if any owner already has more
    # than one profile. Deduplicate before downgrading.
    op.drop_index("ix_assistant_profiles_owner_user_id", table_name="assistant_profiles")
    op.create_unique_constraint(
        "uq_assistant_profiles_owner_user_id", "assistant_profiles", ["owner_user_id"]
    )
