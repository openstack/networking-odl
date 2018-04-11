# Copyright 2017 NEC Corp
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

"""create opendaylight_preiodic_task table

Revision ID: 6f7dfb241354
Revises: 0472f56ff2fb
Create Date: 2017-05-24 03:01:00.755796

"""

from alembic import op
import sqlalchemy as sa

from networking_odl.common import constants as odl_const

# revision identifiers, used by Alembic.
revision = '6f7dfb241354'
down_revision = '0472f56ff2fb'


def upgrade():
    periodic_table = op.create_table(
        'opendaylight_periodic_task',
        sa.Column('state', sa.Enum(odl_const.PENDING, odl_const.PROCESSING,
                                   name='state'),
                  nullable=False),
        sa.Column('processing_operation', sa.String(70)),
        sa.Column('task', sa.String(70), primary_key=True),
        sa.Column('lock_updated', sa.TIMESTAMP, nullable=False,
                  server_default=sa.func.now(),
                  onupdate=sa.func.now())
    )
    op.bulk_insert(periodic_table,
                   [{'task': 'maintenance',
                     'state': odl_const.PENDING},
                    {'task': 'hostconfig',
                     'state': odl_const.PENDING}])
