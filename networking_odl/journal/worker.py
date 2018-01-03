# Copyright (c) 2017 Red Hat, Inc.
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

import atexit
import os

from neutron_lib import worker
from oslo_config import cfg
from oslo_log import log as logging
from oslo_service import loopingcall

# TODO(mpeterson): this should go back to the previous block once the problems
# with flake8-import-order are fixed.
from neutron.agent.linux import daemon

from networking_odl._i18n import _
from networking_odl.journal import cleanup
from networking_odl.journal import full_sync
from networking_odl.journal import journal
from networking_odl.journal import periodic_task
from networking_odl.journal import recovery


LOG = logging.getLogger(__name__)


class JournalPeriodicProcessor(worker.BaseWorker):
    """Responsible for running the periodic processing of the journal.

    This is a separate worker as the regular journal thread is called when an
    operation finishes and that run will take care of any and all entries
    that might be present in the journal, including the one relating to that
    operation.

    A periodic run over the journal is thus necessary for cases when journal
    entries in the aforementioned run didn't process correctly due to some
    error (usually a connection problem) and need to be retried.
    """
    def __init__(self):
        super(JournalPeriodicProcessor, self).__init__()
        self._journal = journal.OpenDaylightJournalThread(start_thread=False)
        self._interval = cfg.CONF.ml2_odl.sync_timeout
        self._timer = None
        self._maintenance_task = None
        self._running = None
        self.pidfile = None

    def _create_pidfile(self):
        pidfile = os.path.join(cfg.CONF.state_path,
                               type(self).__name__.lower() + '.pid')
        self.pidfile = daemon.Pidfile(pidfile, 'python')

        # NOTE(mpeterson): We want self._running to be None before the first
        # run so atexit is only registered once and not several times.
        # TODO(mpeterson): Once we drop support for PY2 we need to change
        # the logic to use atexit.unregister at stop.
        if self._running is None:
            atexit.register(self._delete_pidfile)

        self.pidfile.write(os.getpid())

    def _delete_pidfile(self):
        if self.pidfile is not None:
            self.pidfile.unlock()
            os.remove(str(self.pidfile))
            self.pidfile = None

    def start(self):
        if self._running:
            raise RuntimeError(
                _("Thread has to be stopped before started again")
            )

        super(JournalPeriodicProcessor, self).start()
        LOG.debug('JournalPeriodicProcessor starting')
        self._journal.start()
        self._timer = loopingcall.FixedIntervalLoopingCall(self._call_journal)
        self._timer.start(self._interval)
        self._start_maintenance_task()
        self._create_pidfile()
        self._running = True

    def stop(self):
        if not self._running:
            return

        LOG.debug('JournalPeriodicProcessor stopping')
        self._journal.stop()
        self._timer.stop()
        self._maintenance_task.cleanup()
        self._delete_pidfile()
        super(JournalPeriodicProcessor, self).stop()
        self._running = False

    def wait(self):
        pass

    def reset(self):
        if self._maintenance_task is not None:
            self._maintenance_task.execute_ops(forced=True)

    def _call_journal(self):
        self._journal.set_sync_event()

    def _start_maintenance_task(self):
        self._maintenance_task = periodic_task.PeriodicTask(
            'maintenance', cfg.CONF.ml2_odl.maintenance_interval)

        for phase in (
                cleanup.delete_completed_rows,
                cleanup.cleanup_processing_rows,
                full_sync.full_sync,
                recovery.journal_recovery,
        ):
            self._maintenance_task.register_operation(phase)

        self._maintenance_task.execute_ops(forced=True)
        self._maintenance_task.start()
