#!/usr/bin/python
# -*- coding: utf-8 -*-

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# Author, Peng Zeng Yu <pzypeng@cn.ibm.com>


from __future__ import absolute_import, division, print_function

__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = r'''
---
module: ibmi_script_execute
short_description: Execute a cl/sql script file on a remote ibm i node.
version_added: 1.0
description:
     - The ibmi_script_execute module execute a cl/sql script file on a remote ibm i node.
     - Only support cl/sql script file by now.
     - For sql script, use RUNSQLSTM to process
     - For non-cl/sql script, use the script plugin instead.
options:
  src:
    description:
      - Script file path on the remote ibm i node.
      - The path can be absolute or relative.
    type: path
    required: yes
  type:
    description:
      - Specify the script file type.
      - Only support CL or SQL script by now.
    type: str
    required: yes
    choices: ["CL", "SQL"]
  asp_group:
     description:
       - Specifies the name of the auxiliary storage pool (ASP) group to set for the current thread.
       - The ASP group name is the name of the primary ASP device within the ASP group.
     type: str
     default: ''
  severity_level:
     description:
       - When run sql script, specifies whether the processing is successful, based on the severity of the messages generated by the processing of
         the SQL statements.
       - If errors that are greater than the value specified for this parameter occur during processing, no more statements are
         run and the statements are rolled back if they are running under commitmentcontrol.
       - Only works for sql script
     type: int
     default: 10
  parameters:
    description:
      - The parameters that RUNSQLSTM command will take. All other parameters need to be specified here.
      - The default values of parameters for RUNSQLSTM will be taken if not specified.
      - Only works for sql script
    type: str
    default: ' '

notes:
    - Ansible hosts file need to specify ansible_python_interpreter=/QOpenSys/pkgs/bin/python3(or python2)
    - For cl script, the command supports line breaks.
      When a command ends, add ':' at the end of each command or empty the next line.
      Otherwise program will not consider it is the end of a command.

author:
    - Peng Zeng Yu (@pengzengyufish)
'''

EXAMPLES = r'''
- name: Execute test.cl on a remote ibm i node
  ibmi_script_execute:
    src: '/home/test.cl'
    type: 'CL'

- name: Execute testsql.sql on a remote ibm i node
  ibmi_script_execute:
    src: '/home/testsql.sql'
    type: 'SQL'
    severity_level: 40
    parameters: 'DATFMT(*USA)'
'''

RETURN = r'''
delta:
    description: The execution delta time.
    returned: always
    type: str
    sample: '0:00:00.307534'
stdout:
    description: The standard output
    returned: always
    type: str
    sample: 'Successfully execute script file /home/test.cl'
stderr:
    description: The standard error
    returned: always
    type: str
    sample: 'Execute command %s failed.'
rc:
    description: The action return code (0 means success, non-zero means failure)
    returned: always
    type: int
    sample: 255
stdout_lines:
    description: The standard output split in lines
    returned: always
    type: list
    sample: ['Successfully execute script file /home/test.cl']
stderr_lines:
    description: The standard error split in lines
    returned: always
    type: list
    sample: ['Execute command %s failed.']
'''

import os
import datetime

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_bytes, to_native, to_text

HAS_ITOOLKIT = True
HAS_IBM_DB = True

try:
    from shlex import quote
except ImportError:
    from pipes import quote

try:
    from itoolkit import iToolKit
    from itoolkit import iSqlFree
    from itoolkit import iSqlFetch
    from itoolkit import iSqlQuery
    from itoolkit import iCmd
    from itoolkit import iCmd5250
    from itoolkit.transport import DatabaseTransport
    from itoolkit.transport import DirectTransport
except ImportError:
    HAS_ITOOLKIT = False

try:
    import ibm_db_dbi as dbi
except ImportError:
    HAS_IBM_DB = False

IBMi_COMMAND_RC_SUCCESS = 0
IBMi_COMMAND_RC_UNEXPECTED = 999
IBMi_COMMAND_RC_ERROR = 255
IBMi_COMMAND_RC_ITOOLKIT_NO_KEY_JOBLOG = 256
IBMi_COMMAND_RC_ITOOLKIT_NO_KEY_ERROR = 257


def itoolkit_run_command(command, asp_group):
    conn = dbi.connect()
    itransport = DatabaseTransport(conn)
    itool = iToolKit()
    if asp_group != '':
        itransport = DirectTransport()
        itool.add(iCmd('command', "QSYS/SETASPGRP ASPGRP({asp_group_pattern})".format(asp_group_pattern=asp_group), {'error': 'on'}))
    itool.add(iCmd('command', command, {'error': 'on'}))
    itool.call(itransport)

    out = ''
    err = ''

    if asp_group != '' and isinstance(itool.dict_out('command'), list) and len(itool.dict_out('command')) > 1:
        command_output = itool.dict_out('command')[1]
    else:
        command_output = itool.dict_out('command')

    if 'success' in command_output:
        rc = IBMi_COMMAND_RC_SUCCESS
        out = command_output['success']

    elif 'error' in command_output:
        command_error = command_output['error']
        if 'joblog' in command_error:
            rc = IBMi_COMMAND_RC_ERROR
            err = command_error['joblog']
        else:
            # should not be here, must xmlservice has internal error
            rc = IBMi_COMMAND_RC_ITOOLKIT_NO_KEY_JOBLOG
            err = "iToolKit result dict does not have key 'joblog', the output \
                  is %s" % command_output
    else:
        # should not be here, must xmlservice has internal error
        rc = IBMi_COMMAND_RC_ITOOLKIT_NO_KEY_ERROR
        err = "iToolKit result dict does not have key 'error', the output is \
              %s" % command_output

    return rc, out, err


def return_error(module, error, out, result):
    result['stderr'] = error
    result['out'] = out
    result['rc'] = IBMi_COMMAND_RC_ERROR
    module.exit_json(**result)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            src=dict(type='path', required=True),
            asp_group=dict(type='str', default=''),
            severity_level=dict(type='int', default=10),
            type=dict(type='str', required=True, choices=['CL', 'SQL']),
            parameters=dict(type='str', default=' '),
        ),
        supports_check_mode=True,
    )
    result = dict(
        stdout='',
        stderr='',
        rc=0,
        delta='',
    )

    try:
        if HAS_ITOOLKIT is False:
            module.fail_json(stderr="itoolkit package is required")

        if HAS_IBM_DB is False:
            module.fail_json(stderr="ibm_db package is required")

        err = ''
        out = ''
        rc = 0
        cl = False

        src = module.params['src']
        asp_group = module.params['asp_group']
        type = module.params['type']
        severity_level = module.params['severity_level']
        parameters = module.params['parameters']

        startd = datetime.datetime.now()

        src = os.path.realpath(src)
        if not os.path.isfile(src):
            return_error(module, "src %s doesn't exist." % src, '', result)

        f = open(src, "r")
        if not f:
            return_error(module, "Can't open src %s." % src, out, result)

        command = ''
        if type == 'CL':
            for line in f:
                line_command = line.strip()
                if line_command != '':
                    if not line_command.endswith(":"):
                        command = command + line_command + ' '
                    else:
                        if line_command.endswith(":"):
                            command = command + line_command[:-1]
                        else:
                            command = command + line_command
                        rc, out, err = itoolkit_run_command(command, asp_group.strip().upper())
                        if rc != IBMi_COMMAND_RC_SUCCESS:
                            return_error(module, "Execute command %s failed. err: %s" % (command, err), out, result)
                        command = ''
                elif command != '':
                    rc, out, err = itoolkit_run_command(command, asp_group.strip().upper())
                    if rc != IBMi_COMMAND_RC_SUCCESS:
                        return_error(module, "Execute command %s failed. err: %s" % (command, err), out, result)
                    command = ''
            if command != '':
                rc, out, err = itoolkit_run_command(command, asp_group.strip().upper())
                if rc != IBMi_COMMAND_RC_SUCCESS:
                    return_error(module, "Execute command %s failed. err: %s" % (command, err), out, result)
        else:
            command = "QSYS/RUNSQLSTM SRCSTMF('%s') ERRLVL(%s) %s" % (src, severity_level, parameters)
            rc, out, err = itoolkit_run_command(command, asp_group.strip().upper())
            if rc != IBMi_COMMAND_RC_SUCCESS:
                return_error(module, "Execute sql statement file %s failed. err: \n %s" % (command, err), out, result)

        endd = datetime.datetime.now()
        delta = endd - startd

        result['stdout'] = "Successfully execute script file."
        result.update({'rc': rc, 'delta': str(delta)})
        module.exit_json(**result)

    except Exception as e:
        return_error(module, "Unexpected exception happens. error: %s. Use -vvv for more information." % to_text(e), '', result)


if __name__ == '__main__':
    main()
