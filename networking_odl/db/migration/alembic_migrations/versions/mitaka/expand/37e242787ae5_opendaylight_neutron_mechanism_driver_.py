# Copyright (c) 2015 OpenStack Foundation
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

"""Opendaylight Neutron mechanism driver refactor

Revision ID: 37e242787ae5
Revises: 247501328046
Create Date: 2015-10-30 22:09:27.221767

"""
# revision identifiers, used by Alembic.
revision = '37e242787ae5'
down_revision = '247501328046'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'opendaylightjournal',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('object_type', sa.String(36), nullable=False),
        sa.Column('object_uuid', sa.String(36), nullable=False),
        sa.Column('operation', sa.String(36), nullable=False),
        sa.Column('data', sa.PickleType, nullable=True),
        sa.Column('state',
                  sa.Enum('pending', 'processing', 'failed', 'completed'),
                  nullable=False, default='pending'),
        sa.Column('retry_count', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('last_retried', sa.TIMESTAMP, server_default=sa.func.now(),
                  onupdate=sa.func.now())
    )
