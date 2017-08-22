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

from neutron_lib.db import model_base

from networking_odl.common import constants as odl_const


IdType = sa.BigInteger().with_variant(sa.Integer(), 'sqlite')

journal_dependencies = sa.Table(
    'opendaylight_journal_deps', model_base.BASEV2.metadata,
    sa.Column('depends_on', IdType,
              sa.ForeignKey('opendaylightjournal.seqnum', ondelete='CASCADE'),
              primary_key=True),
    sa.Column('dependent', IdType,
              sa.ForeignKey('opendaylightjournal.seqnum', ondelete='CASCADE'),
              primary_key=True))


class OpenDaylightJournal(model_base.BASEV2):
    __tablename__ = 'opendaylightjournal'

    seqnum = sa.Column(IdType, primary_key=True, autoincrement=True)
    object_type = sa.Column(sa.String(36), nullable=False)
    object_uuid = sa.Column(sa.String(36), nullable=False)
    operation = sa.Column(sa.String(36), nullable=False)
    data = sa.Column(sa.PickleType, nullable=True)
    state = sa.Column(sa.Enum(odl_const.PENDING, odl_const.FAILED,
                              odl_const.PROCESSING, odl_const.COMPLETED),
                      nullable=False, default=odl_const.PENDING)
    retry_count = sa.Column(sa.Integer, default=0)
    last_retried = sa.Column(sa.TIMESTAMP, server_default=sa.func.now(),
                             onupdate=sa.func.now())
    version_id = sa.Column(sa.Integer, server_default='0', nullable=False)
    dependencies = sa.orm.relationship(
        "OpenDaylightJournal", secondary=journal_dependencies,
        primaryjoin=seqnum == journal_dependencies.c.depends_on,
        secondaryjoin=seqnum == journal_dependencies.c.dependent,
        backref="depending_on"
    )

    __mapper_args__ = {
        'version_id_col': version_id
    }


class OpenDaylightPeriodicTask(model_base.BASEV2):
    __tablename__ = 'opendaylight_periodic_task'

    state = sa.Column(sa.Enum(odl_const.PENDING, odl_const.PROCESSING),
                      nullable=False)
    processing_operation = sa.Column(sa.String(70))
    task = sa.Column(sa.String(70), primary_key=True)
    lock_updated = sa.Column(sa.TIMESTAMP, nullable=False,
                             server_default=sa.func.now(),
                             onupdate=sa.func.now())
