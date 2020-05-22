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
module: ibmi_script
short_description: Execute a local cl/sql script file on a remote ibm i node.
version_added: 1.0
description:
     - The ibmi_script plugin transfer a local cl/sql script file to a remote ibm i node and execute.
     - Only support cl/sql script file by now.
     - For sql script, use RUNSQLSTM to process
     - For non-cl/sql script, use the script plugin instead.
options:
  src:
    description:
      - Script file path on control node.
      - The path can be absolute or relative.
    type: str
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
       - When run sql script, specifies whether the processing is successful, based on the severity of the messages generated
         by the processing of the SQL statements.
       - If errors that are greater than the value specified for this parameter occur during processing, no more statements are
         run and the statements are rolled back if they are running under commitment control.
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
  ibmi_script:
    src: '/tmp/test.cl'
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
    sample: 'Successfully execute script file /tmp/test.cl'
stderr:
    description: The standard error
    returned: always
    type: str
    sample: 'Execute command crtlib testlib failed.'
rc:
    description: The action return code (0 means success, non-zero means failure)
    returned: always
    type: int
    sample: 255
stdout_lines:
    description: The standard output split in lines
    returned: always
    type: list
    sample: ['Successfully execute script file /tmp/test.cl']
stderr_lines:
    description: The standard error split in lines
    returned: always
    type: list
    sample: ['Execute command crtlib testlib failed.']
'''
