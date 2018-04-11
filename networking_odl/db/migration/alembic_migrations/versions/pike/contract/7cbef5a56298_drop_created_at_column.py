# Copyright 2017, NEC Corp.
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

"""Drop created_at column

Revision ID: 7cbef5a56298
Revises: eccd865b7d3a
Create Date: 2017-08-16 05:49:53.964988

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = '7cbef5a56298'
down_revision = 'eccd865b7d3a'


def upgrade():
    op.drop_column('opendaylightjournal', 'created_at')
