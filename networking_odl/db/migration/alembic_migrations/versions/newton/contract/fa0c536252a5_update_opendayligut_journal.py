# Copyright 2016 Isaku Yamahata <isaku.yamahata at gmail.com>
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

"""update opendayligut journal

Revision ID: fa0c536252a5
Revises: 383acb0d38a0
Create Date: 2016-08-05 23:03:46.470595

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = 'fa0c536252a5'
down_revision = '383acb0d38a0'
depends_on = ('3d560427d776', )


def upgrade():
    # Since a new primary key is introduced and alembic doesn't allow to
    # add new primary key, create a new table with new primary key and
    # rename it.
    op.execute("INSERT INTO opendaylightjournal_new "
               "(object_type, object_uuid, operation, data, "
               "state, retry_count, created_at, last_retried) "
               "SELECT object_type, object_uuid, operation, data, "
               "state, retry_count, created_at, last_retried "
               "FROM opendaylightjournal "
               "WHERE state != 'completed' "
               "ORDER BY created_at ASC")
    op.drop_table('opendaylightjournal')
    op.rename_table('opendaylightjournal_new', 'opendaylightjournal')
