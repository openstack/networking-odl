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

from neutron.db import api as db_api
from neutron_lib import context as neutron_context
from neutron_lib.db import api as lib_db_api
from oslo_log import log as logging
from oslo_service import loopingcall


from networking_odl.db import db


LOG = logging.getLogger(__name__)


class PeriodicTask(object):
    def __init__(self, task, interval):
        self.task = task
        self.phases = []
        self.timer = loopingcall.FixedIntervalLoopingCall(self.execute_ops)
        self.interval = interval

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

    @lib_db_api.retry_if_session_inactive()
    @db_api.context_manager.writer.savepoint
    def _set_operation(self, context, operation):
        db.update_periodic_task(context, task=self.task,
                                operation=operation)

    def _execute_op(self, operation, context):
        op_details = operation.__name__
        if operation.__doc__:
            op_details += " (%s)" % operation.func_doc

        try:
            LOG.info("Starting %s phase of periodic task %s.",
                     op_details, self.task)
            self._set_operation(context, operation)
            operation(context)
            LOG.info("Finished %s phase of %s task.", op_details, self.task)
        except Exception:
            LOG.exception("Failed during periodic task operation %s.",
                          op_details)

    def task_already_executed_recently(self, context):
        return db.was_periodic_task_executed_recently(
            context, self.task, self.interval)

    @lib_db_api.retry_if_session_inactive()
    @db_api.context_manager.writer.savepoint
    def _clear_and_unlock_task(self, context):
        db.update_periodic_task(context, task=self.task,
                                operation=None)
        db.unlock_periodic_task(context, self.task)

    @lib_db_api.retry_if_session_inactive()
    @db_api.context_manager.writer.savepoint
    def _lock_task(self, context):
        return db.lock_periodic_task(context, self.task)

    def execute_ops(self, forced=False):
        LOG.info("Starting %s periodic task.", self.task)
        context = neutron_context.get_admin_context()

        # Lock make sure that periodic task is executed only after
        # specified interval. It makes sure that maintenance tasks
        # are not executed back to back.
        if not forced and self.task_already_executed_recently(context):
            LOG.info("Periodic %s task executed after periodic interval "
                     "Skipping execution.", self.task)
            return

        if not self._lock_task(context):
            LOG.info("Periodic %s task already running task", self.task)
            return

        try:
            for phase in self.phases:
                self._execute_op(phase, context)
        finally:
            self._clear_and_unlock_task(context)

        LOG.info("%s task has been finished", self.task)

    def register_operation(self, phase):
        """Register a function to be run by the periodic task.

        :param phase: Function to call when the thread runs. The function will
        receive a DB session to use for DB operations.
        """
        self.phases.append(phase)
        LOG.info("%s phase has been registered in %s task", phase, self.task)
