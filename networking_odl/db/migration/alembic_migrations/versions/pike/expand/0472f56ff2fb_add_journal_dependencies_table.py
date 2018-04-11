# Copyright 2017 Red Hat Inc.
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

"""Add journal dependencies table

Revision ID: 0472f56ff2fb
Revises: 43af357fd638
Create Date: 2017-04-02 11:02:01.622548

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0472f56ff2fb'
down_revision = '43af357fd638'


def upgrade():
    op.create_table(
        'opendaylight_journal_deps',
        sa.Column('depends_on', sa.BigInteger(),
                  sa.ForeignKey('opendaylightjournal.seqnum',
                                ondelete='CASCADE'),
                  primary_key=True),
        sa.Column('dependent', sa.BigInteger(),
                  sa.ForeignKey('opendaylightjournal.seqnum',
                                ondelete='CASCADE'),
                  primary_key=True))
