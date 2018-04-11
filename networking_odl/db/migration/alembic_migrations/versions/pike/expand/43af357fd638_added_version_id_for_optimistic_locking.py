# Copyright (C) 2017 Red Hat Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

"""Added version_id for optimistic locking

Revision ID: 43af357fd638
Revises: 3d560427d776
Create Date: 2016-03-24 10:14:56.408413

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '43af357fd638'
down_revision = '3d560427d776'
depends_on = ('fa0c536252a5',)


def upgrade():
    op.add_column('opendaylightjournal',
                  sa.Column('version_id', sa.Integer, server_default='0',
                            nullable=False))
