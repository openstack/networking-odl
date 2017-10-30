# Copyright 2016 Intel Corporation.
# Copyright 2016 Isaku Yamahata <isaku.yamahata at intel com>
#                               <isaku.yamahata at gmail com>
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

import logging

import mock
from pecan import util as p_util

from neutron.db import api as db_api
from neutron.tests.unit.testlib_api import SqlTestCaseLight
from neutron_lib import context
from oslo_config import fixture as config_fixture
from oslo_db import exception as db_exc
from sqlalchemy.orm import exc

from networking_odl.common import constants
from networking_odl.db import models


RETRIABLE_EXCEPTIONS = (db_exc.DBDeadlock, exc.StaleDataError,
                        db_exc.DBConnectionError, db_exc.DBDuplicateEntry,
                        db_exc.RetryRequest)

RETRY_INTERVAL = 0.001
RETRY_MAX = 2


class _InnerException(Exception):
    pass


class ODLBaseDbTestCase(SqlTestCaseLight):

    UPDATE_ROW = [constants.ODL_NETWORK, 'id', constants.ODL_UPDATE,
                  {'test': 'data'}]

    def setUp(self):
        super(ODLBaseDbTestCase, self).setUp()
        self.db_context = context.get_admin_context()
        self.db_session = self.db_context.session
        self.addCleanup(self._db_cleanup)
        self.cfg = self.useFixture(config_fixture.Config())
        self.cfg.config(completed_rows_retention=-1, group='ml2_odl')

    def _db_cleanup(self):
        self.db_session.query(models.OpenDaylightJournal).delete()
        self.db_session.query(models.OpenDaylightPeriodicTask).delete()
        row0 = models.OpenDaylightPeriodicTask(
            task='maintenance', state=constants.PENDING)
        row1 = models.OpenDaylightPeriodicTask(
            task='hostconfig', state=constants.PENDING)
        self.db_session.merge(row0)
        self.db_session.merge(row1)
        self.db_session.flush()

    # NOTE(mpeterson): make retries faster so it doesn't take a lot.
    @mock.patch.multiple(db_api._retry_db_errors,
                         retry_interval=RETRY_INTERVAL,
                         max_retries=RETRY_MAX)
    def _test_db_exceptions_handled(self, method, mock_object,
                                    receives_context, expect_retries):
        # NOTE(mpeterson): this test is very verbose, disabling logging
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        exceptions = RETRIABLE_EXCEPTIONS

        r_method = getattr(method, '__wrapped__', method)
        r_method_args = p_util.getargspec(r_method).args
        args_number = len(r_method_args) - (2 if r_method_args[0] == 'self'
                                            else 1)
        mock_arg = mock.MagicMock(unsafe=True)
        # NOTE(mpeterson): workarounds for py3 compatibility and behavior
        # expected by particular functions
        mock_arg.__name__ = 'mock_arg'
        mock_arg.retry_count = 1
        mock_arg.__ge__.return_value = True
        mock_arg.__gt__.return_value = True
        mock_arg.__le__.return_value = True
        mock_arg.__lt__.return_value = True
        args = (mock_arg,) * args_number

        def _assertRaises(exceptions, method, *args, **kwargs):
            try:
                method(*args, **kwargs)
            except Exception as e:
                if not isinstance(e, exceptions):
                    raise e

                session = args[0].session if receives_context else args[0]

                if session.is_active and isinstance(e, _InnerException):
                    self.assertTrue(getattr(e, '_RETRY_EXCEEDED', False))
                return

            exc_names = (tuple(exc.__name__ for exc in exceptions)
                         if hasattr(exceptions, '__iter__') else
                         exceptions.__name__)

            self.fail('%s did not raise %s' % (method.__name__, exc_names))

        try:
            raise _InnerException
        except _InnerException as e:
            _e = e

        expected_retries = RETRY_MAX if expect_retries else 0
        db_object = self.db_context if receives_context else self.db_session

        for exception in exceptions:
            mock_object.side_effect = exception(_e)

            _assertRaises((exception, _InnerException), method,
                          db_object, *args)
            self.assertEqual(expected_retries, mock_object.call_count - 1)
            mock_object.reset_mock()

    def _test_retry_exceptions(self, method, mock_object, receives_context,
                               assert_begin_transaction=True):
        # NOTE(mpeterson): the reason we test for begining of transactions is
        # that it's not possible to retry without a new transaction or a
        # savepoint.
        with mock.patch.object(self.db_session, 'begin',
                               side_effect=self.db_session.begin) as m:
            self._test_db_exceptions_handled(method, mock_object,
                                             receives_context, True)
            # NOTE(mpeterson): RETRIABLE * 3 when expect_retries=True since
            # it will retry twice as per the test, plus the original call.
            if assert_begin_transaction:
                self.assertEqual(m.call_count,
                                 len(RETRIABLE_EXCEPTIONS) * (RETRY_MAX + 1))

            if receives_context:
                with self.db_session.begin():
                    m.reset_mock()
                    self._test_db_exceptions_handled(method, mock_object,
                                                     receives_context, False)
                    # NOTE(mpeterson): only once when expect_retries=False
                    if assert_begin_transaction:
                        self.assertEqual(m.call_count,
                                         len(RETRIABLE_EXCEPTIONS))
