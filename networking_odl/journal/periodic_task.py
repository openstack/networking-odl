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

from neutron.db import api as neutron_db_api
from oslo_log import log as logging
from oslo_service import loopingcall

from networking_odl.db import db


LOG = logging.getLogger(__name__)


class PeriodicTask(object):
    def __init__(self, interval, task):
        self.timer = loopingcall.FixedIntervalLoopingCall(self.execute_ops)
        self.interval = interval
        self.task = task
        self.phases = []

    def start(self):
        self.timer.start(self.interval, stop_on_exception=False)

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
            LOG.info("Starting %s phase of periodic task %s.",
                     op_details, self.task)
            db.update_periodic_task(session, task=self.task,
                                    operation=operation)
            operation(session=session)
            LOG.info("Finished %s phase of %s task.", op_details, self.task)
        except Exception:
            LOG.exception("Failed during periodic task operation %s.",
                          op_details)

    def execute_ops(self):
        LOG.info("Starting periodic task.")
        session = neutron_db_api.get_writer_session()
        for phase in self.phases:
            try:
                if not db.lock_periodic_task(session, self.task):

                    LOG.info(("Periodic task already running, moving to "
                              " next operation."))
                    continue

                self._execute_op(phase, session)
            finally:
                db.unlock_periodic_task(session, self.task)
                LOG.info(("Finished %s phase of %s periodic task."),
                         phase.__name__, self.task)

    def register_operation(self, f):
        """Register a function to be run by the periodic task.

        :param f: Function to call when the thread runs. The function will
        receive a DB session to use for DB operations.
        """
        self.phases.append(f)
        session = neutron_db_api.get_writer_session()
        db.create_task_if_not_registered(session, self.task)
