# Copyright (c) 2016 Intel Corporation.
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

import copy


def enforce_policy_format(policy):
    if 'bandwidth_limit_rules' not in policy.keys():
        policy['bandwidth_limit_rules'] = []
    if 'dscp_marking_rules' not in policy.keys():
        policy['dscp_marking_rules'] = []
    return policy


# NOTE(manjeets) keeping common methods for formatting
# qos data in qos_utils for code reuse.
def convert_rules_format(data):
    policy = copy.deepcopy(data)
    policy.pop('tenant_id', None)
    policy.pop('rules', None)
    for rule in data.get('rules', []):
        rule_type = rule['type'] + '_rules'
        rule.pop('type', None)
        rule.pop('qos_policy_id', None)
        rule['tenant_id'] = data['tenant_id']
        policy[rule_type] = [rule]
    return enforce_policy_format(policy)
