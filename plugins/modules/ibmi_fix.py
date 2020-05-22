#!/usr/bin/python
# -*- coding: utf-8 -*-

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# Author, Wang Yun <cdlwangy@cn.ibm.com>


from __future__ import absolute_import, division, print_function

__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = r'''
---
module: ibmi_fix
short_description: Install, remove or query an individual fix or a set of fixes on to IBM i system.
version_added: 1.0
description:
     - The C(ibmi_fix) module install fixes to target IBM i system.
     - The installation file of the fixes should be in the format of save file.
     - The fixes are normally known as PTFs for IBM i users.
options:
  save_file_object:
    description:
      - The object name of the save file to be installed.
    type: str
  save_file_lib:
    description:
      - The library name of the save file to be installed.
    type: str
    default: 'QGPL'
  product_id:
    description:
      - Product identifier to which PTFs are applied.
    type: str
  fix_list:
    description:
      - PTF list that will be applied to the IBM i system.
    type: list
    elements: str
    default: ['*ALL']
  fix_omit_list:
    description:
      - The list of PTFs that will be omitted.
      - The key of the dict should be the product ID of the fix that is omitted.
    type: list
    elements: str
    required: false
  delayed_option:
    description:
      - Controls whether the PTF is delayed apply or not
    choices: ['*YES', '*NO']
    type: str
    default: '*NO'
  operation:
    description:
      - The operation for the fix, the options are as follows
      - load_and_apply will load the PTF and apply the PTF
      - load_only will only load the PTF by LODPTF
      - remove_and_delete will remove the PTF and delete the PTF
      - remove_only will only remove the PTF
      - delete_only will only delete the PTF
      - query will return the specific PTF status
    choices: ['load_and_apply', 'apply_only', 'load_only', 'remove', 'query']
    type: str
    default: 'load_and_apply'
  temp_or_perm:
    description:
      - Controls whether the PTF will be permanent applied or temporary applied.
    choices: ['*TEMP', '*PERM']
    type: 'str'
    default: '*TEMP'
notes:
   - Ansible hosts file need to specify ansible_python_interpreter=/QOpenSys/pkgs/bin/python3(or python2)
seealso:
- module: ibmi_fix_imgclg

author:
    - Wang Yun (@airwangyun)
'''

EXAMPLES = r'''
- name: Remove a single PTF
  ibmi_fix:
    product_id: '5770DBM'
    delayed_option: "*NO"
    temp_or_perm: "*PERM"
    operation: 'remove'
    fix_list:
      - "SI72223"
- name: Install a single PTF
  ibmi_fix:
    product_id: '5770DBM'
    save_file_object: 'QSI72223'
    save_file_lib: 'QGPL'
    delayed_option: "*NO"
    temp_or_perm: "*TEMP"
    operation: 'load_and_apply'
    fix_list:
      - "SI72223"
- name: query ptf
  ibmi_fix:
    operation: 'query'
    fix_list:
      - "SI72223"
      - "SI70819"
'''

RETURN = r'''
start:
    description: The task execution start time
    type: str
    sample: '2019-12-02 11:07:53.757435'
    returned: When rc is zero
end:
    description: The task execution end time
    type: str
    sample: '2019-12-02 11:07:54.064969'
    returned: When rc is zero
delta:
    description: The task execution delta time
    type: str
    sample: '0:00:00.307534'
    returned: When rc is zero
stdout:
    description: The task standard output
    type: str
    sample: 'CPC2102: Library TESTLIB created'
    returned: When error occurs.
stderr:
    description: The task standard error
    type: str
    sample: 'CPF2111:Library TESTLIB already exists'
    returned: When error occurs.
rc:
    description: The task return code (0 means success, non-zero means failure)
    type: int
    sample: 255
    returned: always
stdout_lines:
    description: The task standard output split in lines
    type: list
    sample: [
        "CPC2102: Library TESTLIB created."
    ]
    returned: When error occurs.
stderr_lines:
    description: The task standard error split in lines
    type: list
    sample: [
        "CPF2111:Library TESTLIB already exists."
    ]
    returned: When error occurs.
'''

HAS_ITOOLKIT = True
HAS_IBM_DB = True

import datetime
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.ibm.power_ibmi.plugins.module_utils.ibmi import db2i_tools

try:
    from itoolkit import iToolKit
    from itoolkit import iCmd
    from itoolkit import iSqlFree
    from itoolkit import iSqlFetch
    from itoolkit import iSqlQuery
    from itoolkit.transport import DatabaseTransport, DirectTransport
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
IBMi_JOB_STATUS_NOT_EXPECTED = 258


def interpret_return_code(rc):
    if rc == IBMi_COMMAND_RC_SUCCESS:
        return 'Success'
    elif rc == IBMi_COMMAND_RC_ERROR:
        return 'Generic failure'
    elif rc == IBMi_COMMAND_RC_UNEXPECTED:
        return 'Unexpected error'
    elif rc == IBMi_COMMAND_RC_ITOOLKIT_NO_KEY_JOBLOG:
        return "iToolKit result dict does not have key 'joblog'"
    elif rc == IBMi_COMMAND_RC_ITOOLKIT_NO_KEY_ERROR:
        return "iToolKit result dict does not have key 'error'"
    else:
        return "Unknown error"


def itoolkit_run_sql(sql):
    conn = dbi.connect()
    db_itransport = DatabaseTransport(conn)
    itool = iToolKit()

    itool.add(iSqlQuery('query', sql, {'error': 'on'}))
    itool.add(iSqlFetch('fetch'))
    itool.add(iSqlFree('free'))

    itool.call(db_itransport)

    command_output = itool.dict_out('fetch')

    rc = IBMi_COMMAND_RC_UNEXPECTED
    out = ''
    err = ''
    if 'error' in command_output:
        command_error = command_output['error']
        if 'joblog' in command_error:
            rc = IBMi_COMMAND_RC_ERROR
            err = command_error['joblog']
        else:
            # should not be here, must xmlservice has internal error
            rc = IBMi_COMMAND_RC_ITOOLKIT_NO_KEY_JOBLOG
            err = "iToolKit result dict does not have key 'joblog', the output is %s" % command_output
    else:
        rc = IBMi_COMMAND_RC_SUCCESS
        out = command_output['row']

    return rc, out, err


def itoolkit_run_command(connection_id, command):
    # conn = dbi.connect()
    conn = connection_id
    # itransport = iDB2Call(conn)
    itransport = DatabaseTransport(conn)
    itool = iToolKit()
    itool.add(iCmd('command', command, {'error': 'on'}))
    itool.call(itransport)

    rc = IBMi_COMMAND_RC_UNEXPECTED
    out = ''
    err = ''

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
            err = "iToolKit result dict does not have key 'joblog', the output is %s" % command_output
    else:
        # should not be here, must xmlservice has internal error
        rc = IBMi_COMMAND_RC_ITOOLKIT_NO_KEY_ERROR
        err = "iToolKit result dict does not have key 'error', the output is %s" % command_output

    return rc, out, err


def remove_ptf(connection_id, module, product_id, ptf_selected_list, ptf_omit_list, temp_or_perm="*TEMP",
               delayed_option="*NO"):
    cl_rmv_ptf_map = {"LICPGM": product_id, "RMV": temp_or_perm, "SELECT": "", "OMIT": "", "DELAYED": delayed_option}

    if ptf_selected_list is not None:
        ptf_str_to_select = ' '.join(ptf_selected_list)
        cl_rmv_ptf_map["SELECT"] = ptf_str_to_select

    if ptf_omit_list is not None:
        ptf_str_to_omit = ' '.join(ptf_omit_list)
        cl_rmv_ptf_map["OMIT"] = ptf_str_to_omit

    cl_rmv_ptf = "QSYS/RMVPTF"
    for key, value in cl_rmv_ptf_map.items():
        cl_rmv_ptf = cl_rmv_ptf + " " + key + "(" + value + ") "

    module.log("Run CL Command: " + cl_rmv_ptf)

    rc, out, err = itoolkit_run_command(connection_id, cl_rmv_ptf)

    return rc, out, err


def install_ptf(connection_id, module, product_id, ptf_list_to_select, ptf_list_to_omit,
                device, save_file, delayed_option="*NO", temp_or_perm="*TEMP", load_ptf_only=False, apy_ptf_only=False):

    cl_load_ptf_map = {"LICPGM": product_id,
                       "DEV": "*SAVF",
                       "SELECT": "", "OMIT": "",
                       "SAVF": ""}

    cl_apply_ptf_map = {"LICPGM": product_id, "SELECT": "", "OMIT": "",
                        "APY": temp_or_perm, "DELAYED": delayed_option}

    if ptf_list_to_select is not None:
        ptf_str_to_select = ' '.join(ptf_list_to_select)
        cl_load_ptf_map["SELECT"] = ptf_str_to_select
        cl_apply_ptf_map["SELECT"] = ptf_str_to_select

    if ptf_list_to_omit is not None:
        ptf_str_to_omit = ' '.join(ptf_list_to_omit)
        cl_load_ptf_map["OMIT"] = ptf_str_to_omit
        cl_apply_ptf_map["OMIT"] = ptf_str_to_omit

    if device == "*SAVF":
        cl_load_ptf_map["SAVF"] = save_file

    cl_load_ptf = "QSYS/LODPTF"
    for key, value in cl_load_ptf_map.items():
        cl_load_ptf = cl_load_ptf + " " + key + "(" + value + ") "

    cl_apply_ptf = "QSYS/APYPTF"
    for key, value in cl_apply_ptf_map.items():
        cl_apply_ptf = cl_apply_ptf + " " + key + "(" + value + ") "

    if apy_ptf_only:
        pass
    else:
        module.log("Running CL: " + cl_load_ptf)
        rc, out, err = itoolkit_run_command(connection_id, cl_load_ptf)
        if rc > 0:
            return rc, out, err

    if load_ptf_only:
        pass
    else:
        module.log("Running CL: " + cl_apply_ptf)
        rc, out, err = itoolkit_run_command(connection_id, cl_apply_ptf)

    return rc, out, err


def return_fix_information(db_connection, product_id, ptf_list):
    if ptf_list is None:
        return None, "PTF list contains no PTF."

    # get the version and release info
    release_info, err = db2i_tools.get_ibmi_release(db_connection)

    if release_info["version_release"] < 7.3:
        ptf_temp_apply_time_label = "'NOT SUPPORT'"
    else:
        ptf_temp_apply_time_label = "PTF_TEMPORARY_APPLY_TIMESTAMP"

    str_ptf_list = "','".join(ptf_list)
    str_ptf_list = str_ptf_list.upper()
    sql = "SELECT PTF_PRODUCT_ID, PTF_IDENTIFIER, PTF_LOADED_STATUS, PTF_SAVE_FILE, PTF_IPL_ACTION," \
          " PTF_ACTION_PENDING, PTF_ACTION_REQUIRED, PTF_IPL_REQUIRED,  " \
          " PTF_STATUS_TIMESTAMP, PTF_CREATION_TIMESTAMP, " \
          " " + ptf_temp_apply_time_label + " FROM QSYS2.PTF_INFO " \
          " WHERE 1 = 1 "

    if (ptf_list is None) or ([x.upper() for x in ptf_list] == ["*ALL"]):
        where_ptf_list = ""
    else:
        where_ptf_list = " AND UPPER(PTF_IDENTIFIER) IN ('" + str_ptf_list + "')"

    if (product_id is None) or (product_id.upper() == "*ALL"):
        where_product_id = ""
    else:
        where_product_id = " AND UPPER(PTF_PRODUCT_ID) = UPPER('" + product_id + "') "

    sql = sql + where_ptf_list + where_product_id
    out_result_set, err = db2i_tools.ibm_dbi_sql_query(db_connection, sql)

    out = []
    for result in out_result_set:
        result_map = {"PTF_PRODUCT_ID": result[0], "PTF_IDENTIFIER": result[1],
                      "PTF_LOADED_STATUS": result[2], "PTF_SAVE_FILE": result[3],
                      "PTF_IPL_ACTION": result[4], "PTF_ACTION_PENDING": result[5],
                      "PTF_ACTION_REQUIRED": result[6], "PTF_IPL_REQUIRED": result[7],
                      "PTF_STATUS_TIMESTAMP": result[8],
                      "PTF_CREATION_TIMESTAMP": result[9], "PTF_TEMPORARY_APPLY_TIMESTAMP": result[10]
                      }
        out.append(result_map)
    return out, err


def run_a_list_of_commands(module, cmd_key_list, cmd_map):

    for item in cmd_key_list:
        cur_cmd = cmd_map[item]
        args = ['system', cur_cmd]
        module.run_command(args, use_unsafe_shell=False)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            product_id=dict(type='str'),
            fix_list=dict(type='list', elements='str', default=['*ALL']),
            fix_omit_list=dict(type='list', elements='str'),
            save_file_object=dict(type='str'),
            save_file_lib=dict(type='str', default='QGPL'),
            delayed_option=dict(type='str', default='*NO', choices=['*YES', '*NO']),
            temp_or_perm=dict(type='str', default='*TEMP', choices=['*TEMP', '*PERM']),
            operation=dict(type='str', default='load_and_apply', choices=['load_and_apply',
                                                                          'load_only', 'apply_only',
                                                                          'remove',
                                                                          'query']),
        ),
        required_if=[
            ["operation", "apply_only", ["product_id"]],
            ["operation", "remove", ["product_id"]],
            ["operation", "load_and_apply", ["product_id", "save_file_object"]],
            ["operation", "load_only", ["product_id", "save_file_object"]]
        ],
        supports_check_mode=True,
    )

    if HAS_ITOOLKIT is False:
        module.fail_json(msg="itoolkit package is required")

    if HAS_IBM_DB is False:
        module.fail_json(msg="ibm_db package is required")

    product_id = module.params['product_id']
    ptf_list_to_select = module.params['fix_list']
    ptf_list_to_omit = module.params['fix_omit_list']
    save_file_object = module.params['save_file_object']
    save_file_lib = module.params['save_file_lib']
    delayed_option = module.params['delayed_option']
    temp_or_perm = module.params['temp_or_perm']
    operation = module.params['operation']

    if operation in ['load_and_apply', 'load_only', 'remove']:
        if product_id == '*ALL':
            module.fail_json(msg="product_id cannot be *ALL when operation is remove, load_and_apply and load_only.")

    startd = datetime.datetime.now()

    connection_id = None
    try:
        connection_id = dbi.connect()
    except Exception as e_db_connect:
        module.fail_json(msg="Exception when connecting to IBM i Db2. " + str(e_db_connect))

    if operation in ['load_and_apply', 'load_only', 'apply_only']:
        operation_bool_map = {'load_and_apply': [False, False], 'load_only': [True, False], 'apply_only': [False, True]}
        # install single or a list of PTFs

        savf_obj = "" if operation == 'apply_only' else (save_file_lib + "/" + save_file_object)

        rc, out, err = install_ptf(connection_id, module, product_id, ptf_list_to_select,
                                   ptf_list_to_omit, "*SAVF", savf_obj, delayed_option, temp_or_perm,
                                   operation_bool_map[operation][0], operation_bool_map[operation][1])

        # Need to query the status of the PTF

    elif operation in ['remove']:
        rc, out, err = remove_ptf(connection_id, module, product_id, ptf_list_to_select, ptf_list_to_omit,
                                  temp_or_perm=temp_or_perm, delayed_option=delayed_option)
        # Need to query the status of the PTF

    # return the status of the ptf
    if ptf_list_to_select is not None:
        ptf_list, query_err = return_fix_information(connection_id, product_id, ptf_list_to_select)
    else:
        module.fail_json(msg="PTF list contains no PTF.")

    if operation == "query":
        if query_err is not None:
            rc = IBMi_COMMAND_RC_ERROR
            err = query_err
        else:
            rc = IBMi_COMMAND_RC_SUCCESS

    # job_log, get_joblog_err = db2i_tools.get_job_log(connection_id, "*")

    if connection_id is not None:
        try:
            connection_id.close()
        except Exception as e_disconnect:
            module.log("ERROR: Unable to disconnect from the database. " + str(e_disconnect))

    endd = datetime.datetime.now()
    delta = endd - startd

    if rc > 0:
        result_failed = dict(
            start=str(startd),
            end=str(endd),
            delta=str(delta),
            stdout=out,
            stderr=err,
            rc=rc,
            # changed=True,
        )
        module.fail_json(msg='non-zero return code', **result_failed)
    else:
        result_success = dict(
            start=str(startd),
            end=str(endd),
            delta=str(delta),
            ptf_list=ptf_list,
            rc=rc,
            # job_log=job_log,
            # changed=True,
        )
        module.exit_json(**result_success)


if __name__ == '__main__':
    main()
