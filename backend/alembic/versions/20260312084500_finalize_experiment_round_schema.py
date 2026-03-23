"""finalize_experiment_round_schema

Revision ID: 20260312084500
Revises: 20260305032434
Create Date: 2026-03-12 08:45:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260312084500"
down_revision: Union[str, Sequence[str], None] = "20260305032434"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'study_rounds'
          ) AND NOT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'experiment_rounds'
          ) THEN
            ALTER TABLE study_rounds RENAME TO experiment_rounds;
          END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'experiment_rounds'
              AND column_name = 'prolific_device_compatibility'
          ) AND NOT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'experiment_rounds'
              AND column_name = 'device_compatibility'
          ) THEN
            ALTER TABLE experiment_rounds
            RENAME COLUMN prolific_device_compatibility TO device_compatibility;
          END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        ALTER TABLE experiment_rounds
        ADD COLUMN IF NOT EXISTS description TEXT,
        ADD COLUMN IF NOT EXISTS estimated_completion_time INTEGER,
        ADD COLUMN IF NOT EXISTS reward INTEGER,
        ADD COLUMN IF NOT EXISTS device_compatibility VARCHAR(256)
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'experiments'
              AND column_name = 'prolific_description'
          ) THEN
            UPDATE experiment_rounds AS rounds
            SET
              description = COALESCE(rounds.description, experiments.prolific_description, ''),
              estimated_completion_time = COALESCE(
                rounds.estimated_completion_time,
                experiments.prolific_estimated_completion_time,
                0
              ),
              reward = COALESCE(rounds.reward, experiments.prolific_reward, 0),
              device_compatibility = COALESCE(
                rounds.device_compatibility,
                experiments.prolific_device_compatibility,
                '["desktop"]'
              )
            FROM experiments
            WHERE experiments.id = rounds.experiment_id;
          END IF;

          UPDATE experiment_rounds
          SET
            description = COALESCE(description, ''),
            estimated_completion_time = COALESCE(estimated_completion_time, 0),
            reward = COALESCE(reward, 0),
            device_compatibility = COALESCE(device_compatibility, '["desktop"]');
        END
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'experiment_rounds'
              AND column_name = 'prolific_completion_url'
          ) THEN
            UPDATE experiments AS experiments
            SET prolific_completion_url = rounds.prolific_completion_url
            FROM (
              SELECT DISTINCT ON (experiment_id)
                experiment_id,
                prolific_completion_url
              FROM experiment_rounds
              WHERE prolific_completion_url IS NOT NULL
              ORDER BY experiment_id, round_number
            ) AS rounds
            WHERE experiments.id = rounds.experiment_id
              AND experiments.prolific_completion_url IS NULL;
          END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        ALTER TABLE experiment_rounds
        ALTER COLUMN description SET NOT NULL,
        ALTER COLUMN estimated_completion_time SET NOT NULL,
        ALTER COLUMN reward SET NOT NULL,
        ALTER COLUMN device_compatibility SET NOT NULL
        """
    )

    op.execute(
        """
        ALTER TABLE experiment_rounds
        DROP COLUMN IF EXISTS is_pilot,
        DROP COLUMN IF EXISTS prolific_completion_code,
        DROP COLUMN IF EXISTS prolific_completion_url,
        DROP COLUMN IF EXISTS prolific_device_compatibility
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'uq_experiment_round_number'
          ) THEN
            ALTER TABLE experiment_rounds
            ADD CONSTRAINT uq_experiment_round_number
            UNIQUE (experiment_id, round_number);
          END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        ALTER TABLE experiments
        DROP COLUMN IF EXISTS prolific_study_id,
        DROP COLUMN IF EXISTS prolific_study_status,
        DROP COLUMN IF EXISTS prolific_description,
        DROP COLUMN IF EXISTS prolific_reward,
        DROP COLUMN IF EXISTS prolific_estimated_completion_time,
        DROP COLUMN IF EXISTS prolific_device_compatibility
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE experiments
        ADD COLUMN IF NOT EXISTS prolific_description TEXT,
        ADD COLUMN IF NOT EXISTS prolific_reward INTEGER,
        ADD COLUMN IF NOT EXISTS prolific_estimated_completion_time INTEGER,
        ADD COLUMN IF NOT EXISTS prolific_device_compatibility VARCHAR(256),
        ADD COLUMN IF NOT EXISTS prolific_study_id VARCHAR(128),
        ADD COLUMN IF NOT EXISTS prolific_study_status VARCHAR(32)
        """
    )

    op.execute(
        """
        ALTER TABLE experiment_rounds
        ADD COLUMN IF NOT EXISTS is_pilot BOOLEAN DEFAULT false NOT NULL
        """
    )

    op.execute(
        """
        ALTER TABLE experiment_rounds
        DROP COLUMN IF EXISTS device_compatibility,
        DROP COLUMN IF EXISTS reward,
        DROP COLUMN IF EXISTS estimated_completion_time,
        DROP COLUMN IF EXISTS description
        """
    )

    op.execute(
        """
        ALTER TABLE experiment_rounds
        DROP CONSTRAINT IF EXISTS uq_experiment_round_number
        """
    )
