# Copyright (c) 2016 OpenStack Foundation
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

import abc
import six
import stevedore

from oslo_config import cfg
from oslo_log import log
from oslo_utils import excutils

from networking_odl._i18n import _LI, _LE


LOG = log.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class PortBindingController(object):

    @abc.abstractmethod
    def bind_port(self, port_context):
        """Attempt to bind a port.

        :param context: PortContext instance describing the port

        This method is called outside any transaction to attempt to
        establish a port binding using calling mechanism driver. Bindings
        may be created at each of multiple levels of a hierarchical
        network, and are established from the top level downward. At
        each level, the mechanism driver determines whether it can
        bind to any of the network segments in the
        context.segments_to_bind property, based on the value of the
        context.host property, any relevant port or network
        attributes, and its own knowledge of the network topology. At
        the top level, context.segments_to_bind contains the static
        segments of the port's network. At each lower level of
        binding, it contains static or dynamic segments supplied by
        the driver that bound at the level above. If the driver is
        able to complete the binding of the port to any segment in
        context.segments_to_bind, it must call context.set_binding
        with the binding details. If it can partially bind the port,
        it must call context.continue_binding with the network
        segments to be used to bind at the next lower level.
        If the binding results are committed after bind_port returns,
        they will be seen by all mechanism drivers as
        update_port_precommit and update_port_postcommit calls. But if
        some other thread or process concurrently binds or updates the
        port, these binding results will not be committed, and
        update_port_precommit and update_port_postcommit will not be
        called on the mechanism drivers with these results. Because
        binding results can be discarded rather than committed,
        drivers should avoid making persistent state changes in
        bind_port, or else must ensure that such state changes are
        eventually cleaned up.
        Implementing this method explicitly declares the mechanism
        driver as having the intention to bind ports. This is inspected
        by the QoS service to identify the available QoS rules you
        can use with ports.
        """


class PortBindingManager(PortBindingController):
    # At this point, there is no requirement to have multiple
    # port binding controllers at the same time.
    # Stay with single controller until there is a real requirement

    def __init__(self, name, controller):
        self.name = name
        self.controller = controller

    @classmethod
    def create(
            cls, namespace='networking_odl.ml2.port_binding_controllers',
            name=cfg.CONF.ml2_odl.port_binding_controller):

        ext_mgr = stevedore.named.NamedExtensionManager(
            namespace, [name], invoke_on_load=True)

        assert len(ext_mgr.extensions) == 1, (
            "Wrong port binding controller is specified")

        extension = ext_mgr.extensions[0]
        if isinstance(extension.obj, PortBindingController):
            return cls(extension.name, extension.obj)
        else:
            raise ValueError(
                ("Port binding controller '%(name)s (%(controller)r)' "
                 "doesn't implement PortBindingController interface."),
                {'name': extension.name, 'controller': extension.obj})

    def bind_port(self, port_context):
        controller_details = {'name': self.name, 'controller': self.controller}
        try:
            self.controller.bind_port(port_context)
        except Exception:
            with excutils.save_and_reraise_exception():
                LOG.exception(
                    _LE("Controller '%(name)s (%(controller)r)' had an error "
                        "when binding port."), controller_details)
        else:
            if port_context._new_bound_segment:
                LOG.info(
                    _LI("Controller '%(name)s (%(controller)r)' has bound "
                        "port."), controller_details)
            else:
                LOG.debug(
                    "Controller %(name)s (%(controller)r) hasn't bound "
                    "port.", controller_details)
