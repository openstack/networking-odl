# Copyright 2016 Red Hat Inc.
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

"""Add journal maintenance table

Revision ID: 703dbf02afde
Revises: 37e242787ae5
Create Date: 2016-04-12 10:49:31.802663

"""

from alembic import op
from oslo_utils import uuidutils
import sqlalchemy as sa

from networking_odl.common import constants as odl_const

# revision identifiers, used by Alembic.
revision = '703dbf02afde'
down_revision = '37e242787ae5'


def upgrade():
    maint_table = op.create_table(
        'opendaylight_maintenance',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('state', sa.Enum(odl_const.PENDING, odl_const.PROCESSING,
                                   name='state'),
                  nullable=False),
        sa.Column('processing_operation', sa.String(70)),
        sa.Column('lock_updated', sa.TIMESTAMP, nullable=False,
                  server_default=sa.func.now(),
                  onupdate=sa.func.now())
    )

    # Insert the only row here that is used to synchronize the lock between
    # different Neutron processes.
    op.bulk_insert(maint_table,
                   [{'id': uuidutils.generate_uuid(),
                     'state': odl_const.PENDING}])
