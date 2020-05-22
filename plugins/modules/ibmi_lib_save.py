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
module: ibmi_lib_save
short_description: Save one libary on a remote IBMi node
version_added: 1.0
description:
     - The ibmi_lib_save module create an save file on a remote IBMi nodes
     - The save file I(is not) copied to the local host.
     - Only support *SAVF as the save file's format by now.
options:
  lib_name:
    description:
      - The library need to be saved.
    type: str
    required: yes
  savefile_name:
    description:
      - The save file name.
    type: str
    required: yes
  savefile_lib:
    description:
      - The save file library.
    type: str
    required: yes
  format:
    description:
      - The save file's format. Only support *SAVF by now.
    type: str
    default: '*SAVF'
    choices: ["*SAVF"]
  force_save:
    description:
      - If save file already exists or contains data, whether to clear data or not.
    type: bool
    default: False
  target_release:
    description:
      - The release of the operating system on which you intend to restore and use the SAVF.
    type: str
    default: '*CURRENT'
  asp_group:
     description:
       - Specifies the name of the auxiliary storage pool (ASP) group to set for the current thread.
       - The ASP group name is the name of the primary ASP device within the ASP group.
     type: str
     default: ''
  joblog:
    description:
      - If set to C(true), append JOBLOG to stderr/stderr_lines.
    type: bool
    default: False
  parameters:
    description:
      - The parameters that SAVLIB command will take. Other than options above, all other parameters need to be specified here.
        The default values of parameters for SAVLIB will be taken if not specified.
    type: str
    default: ' '

notes:
    - Ansible hosts file need to specify ansible_python_interpreter=/QOpenSys/pkgs/bin/python3(or python2)

author:
    - Peng Zeng Yu (@pengzengyufish)
'''

EXAMPLES = r'''
- name: Force to save test libary to archive.savf in archlib libary
  ibmi_lib_save:
    lib_name: 'test'
    savefile_name: 'archive'
    savefile_lib: 'archlib'
    force_save: true
    target_release: 'V7R2M0'
'''

RETURN = r'''
start:
    description: The save execution start time
    returned: always
    type: str
    sample: '2019-12-02 11:07:53.757435'
end:
    description: The save execution end time
    returned: always
    type: str
    sample: '2019-12-02 11:07:54.064969'
delta:
    description: The save execution delta time
    returned: always
    type: str
    sample: '0:00:00.307534'
stdout:
    description: The save standard output
    returned: always
    type: str
    sample: 'CPC3722: 2 objects saved from library test.'
stderr:
    description: The save standard error
    returned: always
    type: str
    sample: 'CPF5813: File archive in library archlib already exists.\nCPF7302: File archive not created in library archlib.\n'
lib_name:
    description: The library need to be saved.
    returned: always
    type: str
    sample: 'test'
savefile_name:
    description: The save file name.
    returned: always
    type: str
    sample: archive
savefile_lib:
    description: The save file library.
    returned: always
    type: str
    sample: archlib
format:
    description: The save file's format. Only support *SAVF by now.
    returned: always
    type: str
    sample: '*SAVF'
force_save:
    description: If save file already exists or contains data, whether to clear data or not.
    returned: always
    type: bool
    sample: true
target_release:
    description: The release of the operating system on which you intend to restore and use the library.
    returned: always
    type: str
    sample: 'V7R2M0'
command:
    description: The last excuted command.
    returned: always
    type: str
    sample: 'SAVLIB LIB(TEST) DEV(*SAVF) SAVF(TEST/ARCHLIB) TGTRLS(V7R2M0)'
rc:
    description: The save action return code (0 means success, non-zero means failure)
    returned: always
    type: int
    sample: 255
stdout_lines:
    description: The save standard output split in lines
    returned: always
    type: list
    sample: [
        "CPC3722: 2 objects saved from library test."
    ]
stderr_lines:
    description: The save standard error split in lines
    returned: always
    type: list
    sample: [
        "CPF5813: File archive in library archlib already exists.",
        "CPF7302: File archive not created in library archlib."
    ]
'''

import datetime

from ansible.module_utils.basic import AnsibleModule

try:
    from shlex import quote
except ImportError:
    from pipes import quote

HAS_ITOOLKIT = True
HAS_IBM_DB = True

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
        itool.add(iCmd('command', "QSYS/SETASPGRP ASPGRP({asp_group_pattern})".format(asp_group_pattern=asp_group),
                       {'error': 'on'}))
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


def run_command(module, command, joblog, asp_group):
    if joblog or asp_group.strip():
        rc, out, err = itoolkit_run_command(command, asp_group.strip().upper())
    else:
        rc, out, err = module.run_command(['system', command], use_unsafe_shell=False)
    return rc, out, err


def main():
    module = AnsibleModule(
        argument_spec=dict(
            lib_name=dict(type='str', required=True),
            savefile_name=dict(type='str', required=True),
            savefile_lib=dict(type='str', required=True),
            format=dict(type='str', default='*SAVF', choices=['*SAVF']),
            force_save=dict(type='bool', default=False),
            target_release=dict(type='str', default='*CURRENT'),
            joblog=dict(type='bool', default=False),
            asp_group=dict(type='str', default=''),
            parameters=dict(type='str', default=' '),
        ),
        supports_check_mode=True,
    )

    if HAS_ITOOLKIT is False:
        module.fail_json(msg="itoolkit package is required")

    if HAS_IBM_DB is False:
        module.fail_json(msg="ibm_db package is required")

    lib_name = module.params['lib_name']
    savefile_name = module.params['savefile_name']
    savefile_lib = module.params['savefile_lib']
    format = module.params['format']
    force_save = module.params['force_save']
    target_release = module.params['target_release']
    joblog = module.params['joblog']
    asp_group = module.params['asp_group']
    parameters = module.params['parameters']

    startd = datetime.datetime.now()
    # crtsavf
    command = 'QSYS/CRTSAVF FILE(%s/%s)' % (savefile_lib, savefile_name)
    rc, out, err = run_command(module, command, joblog, asp_group)
    if rc == IBMi_COMMAND_RC_SUCCESS:
        # SAVLIB
        command = 'QSYS/SAVLIB LIB(%s) DEV(%s) SAVF(%s/%s) TGTRLS(%s) %s' % (lib_name, format, savefile_lib, savefile_name,
                                                                             target_release, parameters)
        rc, out, err = run_command(module, command, joblog, asp_group)
    else:
        if 'CPF5813' in err:
            if force_save is True:
                # CLRSAVF
                command = 'QSYS/CLRSAVF FILE(%s/%s)' % (savefile_lib, savefile_name)
                rc, out, err = run_command(module, command, joblog, asp_group)
                if rc == IBMi_COMMAND_RC_SUCCESS:
                    command = 'QSYS/SAVLIB LIB(%s) DEV(%s) SAVF(%s/%s) TGTRLS(%s) %s' % (lib_name, format, savefile_lib,
                                                                                         savefile_name, target_release,
                                                                                         parameters)
                    rc, out, err = run_command(module, command, joblog, asp_group)
            else:
                out = 'File %s in library %s already exists. If still need save, please set force_save.' % (savefile_name,
                                                                                                            savefile_lib)

    endd = datetime.datetime.now()
    delta = endd - startd

    result = dict(
        lib_name=lib_name,
        savefile_name=savefile_name,
        savefile_lib=savefile_lib,
        format=format,
        force_save=force_save,
        target_release=target_release,
        command=command,
        joblog=joblog,
        stdout=out,
        stderr=err,
        rc=rc,
        start=str(startd),
        end=str(endd),
        delta=str(delta),
    )

    if rc != IBMi_COMMAND_RC_SUCCESS:
        module.fail_json(msg='non-zero return code', **result)

    module.exit_json(**result)


if __name__ == '__main__':
    main()
