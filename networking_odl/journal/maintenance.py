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
import random
import tenacity

from neutron.db import api as neutron_db_api
from oslo_config import cfg
from oslo_log import log as logging
from oslo_service import loopingcall

from networking_odl._i18n import _LI, _LE
from networking_odl.db import db


LOG = logging.getLogger(__name__)

PRIMES = [1, -1, 2, -2, 3, -3, 5, -5]


class MaintenanceThread(object):
    def __init__(self):
        self.timer = loopingcall.FixedIntervalLoopingCall(self.execute_ops)
        self.maintenance_interval = cfg.CONF.ml2_odl.maintenance_interval
        self.maintenance_ops = []

    def start(self):
        rand_val = random.choice(PRIMES)
        self.timer.start(self.maintenance_interval + rand_val,
                         stop_on_exception=False)

    def cleanup(self):
        # this method is used for unit test to tear down
        self.timer.stop()
        try:
            self.timer.wait()
        except AttributeError:
            # NOTE(yamahata): workaround
            # some tests call this cleanup without calling start
            pass

    def _execute_op(self, operation, session):
        op_details = operation.__name__
        if operation.__doc__:
            op_details += " (%s)" % operation.func_doc

        try:
            LOG.info(_LI("Starting maintenance operation %s."), op_details)
            db.update_maintenance_operation(session, operation=operation)
            operation(session=session)
            LOG.info(_LI("Finished maintenance operation %s."), op_details)
        except Exception:
            LOG.exception(_LE("Failed during maintenance operation %s."),
                          op_details)

    def execute_ops(self):
        LOG.info(_LI("Starting journal maintenance run."))
        session = neutron_db_api.get_session()
        r_obj = tenacity.Retrying(
            wait=tenacity.wait_random(5),
            retry=tenacity.retry_if_result(lambda x: (not x)),
            stop=tenacity.stop_after_attempt(3)
        )

        try:
            r_obj.call(db.lock_maintenance, session)
        except tenacity.RetryError:
            LOG.info(_LI("Maintenance already running, aborting."))
            return

        try:
            for operation in self.maintenance_ops:
                self._execute_op(operation, session)
        finally:
            db.update_maintenance_operation(session, operation=None)
            db.unlock_maintenance(session)
            LOG.info(_LI("Finished journal maintenance run."))

    def register_operation(self, f):
        """Register a function to be run by the maintenance thread.

        :param f: Function to call when the thread runs. The function will
        receive a DB session to use for DB operations.
        """
        self.maintenance_ops.append(f)
