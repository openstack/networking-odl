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

from datetime import timedelta

from oslo_config import cfg
from oslo_log import log as logging

from neutron.db import api as db_api

from networking_odl.common import constants as odl_const
from networking_odl.db import db

LOG = logging.getLogger(__name__)


@db_api.retry_if_session_inactive()
def delete_completed_rows(context):
    """Journal maintenance operation for deleting completed rows."""
    rows_retention = cfg.CONF.ml2_odl.completed_rows_retention
    if rows_retention <= 0:
        return

    LOG.debug("Deleting completed rows")
    with db_api.autonested_transaction(context.session):
        db.delete_rows_by_state_and_time(
            context.session, odl_const.COMPLETED,
            timedelta(seconds=rows_retention))


@db_api.retry_if_session_inactive()
def cleanup_processing_rows(context):
    with db_api.autonested_transaction(context.session):
        row_count = db.reset_processing_rows(
            context.session, cfg.CONF.ml2_odl.processing_timeout)
    if row_count:
        LOG.info("Reset %(num)s orphaned rows back to pending",
                 {"num": row_count})
