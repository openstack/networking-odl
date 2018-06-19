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
from neutron_lib import context as neutron_context
from neutron_lib import fixture as lib_fixtures
from oslo_config import fixture as config_fixture
from oslo_db import exception as db_exc
import sqlalchemy
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
        self.db_context = neutron_context.get_admin_context()
        self.cfg = self.useFixture(config_fixture.Config())
        self.cfg.config(completed_rows_retention=-1, group='ml2_odl')
        self._setup_retry_tracker_table()

    def _setup_retry_tracker_table(self):
        metadata = sqlalchemy.MetaData()
        self.retry_table = sqlalchemy.Table(
            'retry_tracker', metadata,
            sqlalchemy.Column(
                'id', sqlalchemy.Integer,
                autoincrement=True,
                primary_key=True,
            ),
        )
        metadata.create_all(self.engine)
        self.addCleanup(metadata.drop_all, self.engine)

        class RetryTracker(object):
            pass

        sqlalchemy.orm.mapper(RetryTracker, self.retry_table)
        self.retry_tracker = RetryTracker

    def _db_cleanup(self):
        self.db_context.session.query(models.OpenDaylightJournal).delete()
        self.db_context.session.query(models.OpenDaylightPeriodicTask).delete()
        row0 = models.OpenDaylightPeriodicTask(
            task='maintenance', state=constants.PENDING)
        row1 = models.OpenDaylightPeriodicTask(
            task='hostconfig', state=constants.PENDING)
        self.db_context.session.merge(row0)
        self.db_context.session.merge(row1)
        self.db_context.session.flush()

    def _test_db_exceptions_handled(self, method, mock_object, expect_retries):
        # NOTE(mpeterson): make retries faster so it doesn't take a lot.
        retry_fixture = lib_fixtures.DBRetryErrorsFixture(
            max_retries=RETRY_MAX, retry_interval=RETRY_INTERVAL)
        retry_fixture.setUp()
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

        def _assertRaises(exceptions, method, context, *args, **kwargs):
            try:
                method(context, *args, **kwargs)
            except Exception as e:
                if not isinstance(e, exceptions):
                    raise e

                # TODO(mpeterson): For now the check with session.is_active is
                # accepted, but when the enginefacade is the only accepted
                # pattern then it should be changed to check that a session is
                # attached to the context
                session = context.session

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

        # TODO(mpeterson): Make this an int when Py2 is no longer supported
        # and use the `nonlocal` directive
        retry_counter = [0]
        for exception in exceptions:
            def increase_retry_counter_and_except(*args, **kwargs):
                retry_counter[0] += 1
                self.db_context.session.add(self.retry_tracker())
                self.db_context.session.flush()
                raise exception(_e)
            mock_object.side_effect = increase_retry_counter_and_except

            _assertRaises((exception, _InnerException), method,
                          self.db_context, *args)
            self.assertEqual(expected_retries, mock_object.call_count - 1)
            mock_object.reset_mock()

        retry_fixture.cleanUp()
        return retry_counter[0]

    def _assertRetryCount(self, expected_count):
        actual_count = \
            self.db_context.session.query(self.retry_tracker).count()
        self.assertEqual(expected_count, actual_count)

    def _test_retry_exceptions(self, method, mock_object,
                               assert_transaction=True):
        retries = self._test_db_exceptions_handled(method, mock_object,
                                                   True)

        if assert_transaction:
            # It should be 0 as long as the retriable method creates save
            # points or transactions, which is the correct behavior
            self._assertRetryCount(0)
            # RETRIABLE * 3 when expect_retries=True since it will retry
            # twice as per the test, plus the original call.
            self.assertEqual(
                len(RETRIABLE_EXCEPTIONS) * (RETRY_MAX + 1),
                retries
            )

        with db_api.context_manager.writer.using(self.db_context):
            retries = self._test_db_exceptions_handled(
                method, mock_object, False
            )
            if assert_transaction:
                self._assertRetryCount(0)
                # only once per exception when expect_retries=False
                self.assertEqual(len(RETRIABLE_EXCEPTIONS), retries)
