# Copyright (c) 2017 OpenStack Foundation
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

import types

from oslo_log import helpers as log_helpers
import six


def _build_func(client_method):
    @log_helpers.log_method_call
    def f(self, *args, **kwargs):
        self.journal.set_sync_event()

    f.__name__ = client_method
    return f


def _unboundmethod(func, cls):
    if six.PY3:
        # python 3.x doesn't have unbound methods
        func.__qualname__ = cls.__qualname__ + '.' + func.__name__  # PEP 3155
        return func

    # python 2.x
    return types.MethodType(func, None, cls)


def _get_method_name(op, resource):
    return op + '_' + resource + '_postcommit'


def _build_method(cls, resource):
    # add methods like the following:
    #
    #    @log_helpers.log_method_call
    #    def <method>_<resource>_postcommit(self, *args, **kwargs):
    #        self.journal.set_sync_event()

    operations = ['create', 'update', 'delete']
    for op in operations:
        client_method = _get_method_name(op, resource)
        if hasattr(cls, client_method) and client_method not in cls.__dict__:
            f = _build_func(client_method)
            unbound = _unboundmethod(f, cls)
            setattr(cls, client_method, unbound)


def _build_methods(cls, *resources):
    for resource in resources:
        _build_method(cls, resource)


def add_postcommit(*args):
    def postcommit(cls):
        _build_methods(cls, *args)
        return cls

    return postcommit
