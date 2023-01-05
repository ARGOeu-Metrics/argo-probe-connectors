#!/usr/bin/env python3

import os
import argparse
import copy
import requests
import re

from datetime import datetime, timedelta
from itertools import groupby, zip_longest
from argo_connectors.config import Global
from multi_tenant_connectors_sensor.NagiosResponse import NagiosResponse
from multi_tenant_connectors_sensor.utils import errmsg_from_excp


def check_file_ok(fname):
    try:
        if os.stat(fname) and os.path.isfile(fname):
            fh = open(fname, 'r')
            if fh.read().strip() == 'True':
                return True
            else:
                return False
        else:
            return False

    except OSError as e:
        raise e


def grouper(path):
    d, f = os.path.split(path)
    f = f.split('-')[0]
    return d, f


def remove_duplicates(s):
    s_list = s.rstrip(" /").split('/')
    s_list = [elem.strip() for elem in s_list]
    s_set = set(s_list)
    no_duplicates = ' / '.join(s_set)
    return no_duplicates


def return_missing_file_n_tenant(list_files, dates, list_root):
    result_with_dates = []
    result_without_dates = []
    for sublist in list_files:
        with_dates = [item for item in sublist if item[-10:] in dates]
        without_dates = [item for item in sublist if item[-10:] not in dates]
        result_with_dates.append(with_dates)
        result_without_dates.append(without_dates)

    result_x = [[item.split("_")[0] for item in sublist]
                for sublist in result_with_dates]
    result_y = [[item.split("_")[0] for item in sublist]
                for sublist in result_without_dates]

    results = []
    for sublist_x, sublist_y in zip(result_x, result_y):
        results.append(set(sublist_y).difference(set(sublist_x)))

    missing = [list(s) for s in results]
    missing_elem_positions = [
        i for i, elem in enumerate(missing) if elem]
    missing_tenant = [list_root[i].split("/")[6]
                      for i in missing_elem_positions]
    missing_files = [elem[0] for elem in missing if len(elem) == 1]

    return missing_tenant, missing_files


def create_dates(files, date_sufix):
    if "downtimes-ok" in files:
        dates = copy.copy(date_sufix)[:-1]
        dates.insert(0, datetime.today().strftime("%Y_%m_%d"))
    else:
        dates = date_sufix

    return dates


def sort_n_copy_files(list_paths):
    sorted_paths = sorted([*set(list_paths)])
    sorted_file = [list(g) for _, g in groupby(sorted_paths, grouper)]
    sorted_file_copy = copy.deepcopy(sorted_file)
    for i, x in enumerate(sorted_file):
        for j, a in enumerate(x):
            rslt = a.split("=")[1]
            sorted_file[i][j] = a.replace(a, rslt)

    return sorted_file_copy, sorted_file, sorted_paths


def extract_tenant_path(path, job_names):
    splt_path = path[0].split("/")
    tenant_name = splt_path[6]
    if splt_path[7] in job_names:
        job = splt_path[7]
    else:
        job = ""
    filename = splt_path[-1].split("-")[0].upper()

    return tenant_name, job, filename


def process_customer_jobs(arguments, root_dir, date_sufix, days_num):
    nagios = NagiosResponse("All connectors are working fine.")
    try:
        get_tenants = requests.get(
            'https://' + arguments.hostname + '/api/v2/internal/public_tenants/').json()

        job_names = list()
        list_paths = list()
        list_files = list()
        list_root = list()
        for tenant in get_tenants:
            for (root, dirs, files) in os.walk(f'{root_dir + "/" + tenant["name"]}', topdown=True):
                list_root.append(root)
                list_files.append(files)

                for dir in dirs:
                    if dir not in job_names and dir != []:
                        job_names.append(dir)

                for file in files:
                    file_path = (root + "/" + file)[:-11]

                    dates = create_dates(file, date_sufix)

                    for sufix in dates:
                        path_name_date = file_path + '_' + sufix
                        file_exists = os.path.exists(path_name_date)
                        if file_exists == True:
                            list_paths.append(
                                path_name_date + "=" + str(check_file_ok(path_name_date)))

        date_list = [(datetime.today() - timedelta(days=x)
                      ).strftime('%Y_%m_%d') for x in range(4)]

        missing_tenant, missing_files = return_missing_file_n_tenant(
            list_files, date_list, list_root)
        sorted_file_copy, sorted_file, sorted_paths = sort_n_copy_files(
            list_paths)

        warning_msg = ""
        critical_msg = ""

        if missing_files != "":
            for i in range(len(missing_tenant)):
                nagios.setCode(nagios.CRITICAL)
                msg = ("CRITICAL - Customer: " + missing_tenant[i] + ", State of a file: " + missing_files[i].upper() +
                       " is missing for last " + str(days_num) + " days!" + " /")
                critical_msg += (msg + " ")

        for path, result in zip_longest(sorted_file_copy, sorted_file):
            tenant_name, job, filename = extract_tenant_path(path, job_names)

            if all(item == "False" for item in result[-(int(days_num)):]):
                nagios.setCode(nagios.CRITICAL)
                if job == "":
                    msg = ("CRITICAL - Customer: " + tenant_name + ", File: " + filename +
                           " not ok for last " + str(days_num) + " days!" + " /")
                else:
                    msg = ("CRITICAL - Customer: " + tenant_name + ", Job: " + job + ", File: " +
                           filename + " not ok for last " + str(days_num) + " days!" + " /")
                critical_msg += (msg + " ")

            elif result[-1] == "False":
                nagios.setCode(nagios.WARNING)
                if job == "":
                    msgs = ("WARNING - Customer: " + tenant_name +
                            ", Filename: " + filename + " /")
                else:
                    msgs = ("WARNING - Customer: " + tenant_name + ", Job: " +
                            job + ", Filename: " + filename + " /")
                warning_msg += (msgs + " ")

        if len(sorted_paths) == 0:
            nagios.setCode(nagios.CRITICAL)
            nagios.writeCriticalMessage("CRITICAL - SaveDir is empty")
        else:
            nagios.writeCriticalMessage(remove_duplicates(critical_msg))
            nagios.writeWarningMessage(remove_duplicates(warning_msg))

    except requests.exceptions.RequestException as e:
        nagios.setCode(nagios.CRITICAL)
        nagios.writeCriticalMessage(
            f"CRITICAL - API cannot connect to https://{arguments.hostname}/api/v2/internal/public_tenants/:{errmsg_from_excp(e)}")

    except ValueError as e:
        nagios.setCode(nagios.CRITICAL)
        nagios.writeCriticalMessage(f"CRITICAL - {errmsg_from_excp(e)}")

    except OSError as e:
        nagios.setCode(nagios.CRITICAL)
        nagios.writeCriticalMessage(f"CRITICAL - {errmsg_from_excp(e)}")

    except Exception as e:
        nagios.setCode(nagios.CRITICAL)
        nagios.writeCriticalMessage(f"CRITICAL - {errmsg_from_excp(e)}")

    print(nagios.getMsg())
    raise SystemExit(nagios.getCode())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-H', dest='hostname',
                        required=True, type=str, help='hostname')

    cmd_options = parser.parse_args()
    global_conf = Global(None)
    options = global_conf.parse()
    root_directory = options['inputstatesavedir']
    days_num = int(options['inputstatedays'])
    todays_date = datetime.today()

    days = []
    for i in range(1, days_num + 1):
        days.append(todays_date + timedelta(days=-i))

    date_sufix = []

    for day in days:
        date_sufix.append(day.strftime("%Y_%m_%d"))

    process_customer_jobs(cmd_options, root_directory, date_sufix, days_num)


if __name__ == "__main__":
    main()
