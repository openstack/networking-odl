# Copyright (c) 2017 Red Hat
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

from neutron_lib import worker
from oslo_config import cfg
from oslo_log import log as logging
from oslo_service import loopingcall

from networking_odl.journal import journal


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

    def start(self):
        super(JournalPeriodicProcessor, self).start()
        LOG.debug('JournalPeriodicProcessor starting')
        self._journal.start()
        self._timer = loopingcall.FixedIntervalLoopingCall(self._call_journal)
        self._timer.start(self._interval)

    def stop(self):
        LOG.debug('JournalPeriodicProcessor stopping')
        self._journal.stop()
        if self._timer is not None:
            self._timer.stop()

    def wait(self):
        pass

    def reset(self):
        pass

    def _call_journal(self):
        self._journal.set_sync_event()
