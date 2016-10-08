#
# Copyright (C) 2016 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.
#

from oslo_log import log as logging

from networking_odl._i18n import _LE
from networking_odl.common import client
from networking_odl.common import constants as odl_const
from networking_odl.db import db

_CREATE_OPS = (odl_const.ODL_CREATE, )
_DELETE_OPS = (odl_const.ODL_DELETE, )
_CLIENT = client.OpenDaylightRestClientGlobal()

LOG = logging.getLogger(__name__)


def journal_recovery(session):
    for row in db.get_all_db_rows_by_state(session, odl_const.FAILED):
        try:
            LOG.debug("Attempting recovery of journal entry %s.", row)
            odl_resource = _CLIENT.get_client().get_resource(row.object_type,
                                                             row.object_uuid)
            if odl_resource is not None:
                _handle_existing_resource(session, row)
            else:
                _handle_non_existing_resource(session, row)
        except Exception:
            LOG.exception(
                _LE("Failure while recovering journal entry %s."), row)


def _handle_existing_resource(session, row):
    if row.operation in _CREATE_OPS:
        db.update_db_row_state(session, row, odl_const.COMPLETED)
    elif row.operation in _DELETE_OPS:
        db.update_db_row_state(session, row, odl_const.PENDING)

    # TODO(mkolesni): Handle UPDATE somehow.


def _handle_non_existing_resource(session, row):
    if row.operation in _DELETE_OPS:
        db.update_db_row_state(session, row, odl_const.COMPLETED)

    # TODO(mkolesni): Handle other use cases.
