# Copyright (c) 2015 OpenStack Foundation
# All Rights Reserved.
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

import sqlalchemy as sa

from networking_odl.common import constants as odl_const
from neutron.db import model_base
from neutron.db.models_v2 import HasId


class OpendaylightJournal(model_base.BASEV2, HasId):
    __tablename__ = 'opendaylightjournal'

    object_type = sa.Column(sa.String(36), nullable=False)
    object_uuid = sa.Column(sa.String(36), nullable=False)
    operation = sa.Column(sa.String(36), nullable=False)
    data = sa.Column(sa.PickleType, nullable=True)
    state = sa.Column(sa.Enum(odl_const.PENDING, odl_const.FAILED,
                              odl_const.PROCESSING, odl_const.COMPLETED),
                      nullable=False, default=odl_const.PENDING)
    retry_count = sa.Column(sa.Integer, default=0)
    created_at = sa.Column(sa.DateTime, server_default=sa.func.now())
    last_retried = sa.Column(sa.TIMESTAMP, server_default=sa.func.now(),
                             onupdate=sa.func.now())
