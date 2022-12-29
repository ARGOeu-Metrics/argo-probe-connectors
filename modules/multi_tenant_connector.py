#!/usr/bin/env python3

import os
import argparse
import copy
import requests
import sys

from datetime import datetime, timedelta
from itertools import groupby, zip_longest
from argo_connectors.config import Global
from multi_tenant_connectors_sensor.NagiosResponse import NagiosResponse


def check_file_ok(fname):
    if os.stat(fname) and os.path.isfile(fname):
        fh = open(fname, 'r')
        if fh.read().strip() == 'True':
            return True
        else:
            return False
    else:
        return False


def grouper(path):
    d, f = os.path.split(path)
    f = f.split('-')[0]
    return d, f

def process_customer_jobs(arguments, root_dir, date_sufix, nagios):
    try:
        get_tenants = requests.get(
            'https://' + arguments.hostname + '/api/v2/internal/public_tenants/').json()

        job_names = list()
        list_paths = list()
        for tenant in get_tenants:

            for (root, dirs, files) in os.walk(f'{root_dir + "/" + tenant["name"]}', topdown=True):
                for dir in dirs:
                    if dir not in job_names and dir != []:
                        job_names.append(dir)

                for file in files:
                    file_path = (root + "/" + file)[:-11]

                    if "downtimes-ok" in file:
                        dates = copy.copy(date_sufix)[:-1]
                        dates.insert(0, datetime.today().strftime("%Y_%m_%d"))
                    else:
                        dates = date_sufix

                    for sufix in dates:
                        path_name_date = file_path + '_' + sufix
                        file_exists = os.path.exists(path_name_date)
                        if file_exists == True:
                            list_paths.append(
                                path_name_date + "=" + str(check_file_ok(path_name_date)))

        path_lst = list()
        if "-f" in sys.argv:
            sorted_paths = sorted([*set(list_paths)])
            for sort_path in sorted_paths:
                if arguments.filename[0] in sort_path:
                    path_lst.append(sort_path)

        sorted_paths = sorted([*set(list_paths)])

        toggler = sorted_paths if path_lst == [] else path_lst

        sorted_file = [list(g) for _, g in groupby(toggler, grouper)]
        sorted_file_copy = copy.deepcopy(sorted_file)
        for i, x in enumerate(sorted_file):
            for j, a in enumerate(x):
                rslt = a.split("=")[1]
                sorted_file[i][j] = a.replace(a, rslt)

        critical_msg = ""
        warning_msg = ""
        for path, result in zip_longest(sorted_file_copy, sorted_file):
            splt_path = path[0].split("/")
            tenant_name = splt_path[5]

            if splt_path[6] in job_names:
                job = splt_path[6]
            else:
                job = ""

            filename = splt_path[-1].split("-")[0].upper()

            if all(item == "False" for item in result[-(len(dates)):]):
                nagios.setCode(nagios.CRITICAL)
                if job == "":
                    msg = ("CRITICAL - Customer: " + tenant_name + ", File: " + filename +
                           " not ok for last " + str(len(dates)) + " days!" + " /")
                else:
                    msg = ("CRITICAL - Customer: " + tenant_name + ", Job: " + job + ", File: " +
                           filename + " not ok for last " + str(len(dates)) + " days!" + " /")
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

        return (critical_msg + warning_msg).rstrip(" /")

    except (requests.exceptions.RequestException, requests.exceptions.HTTPError):
        print(
            f"CRITICAL - API cannot connect to https://{arguments.hostname}/api/v2/internal/public_tenants/")

        raise SystemExit(2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-H', dest='hostname',
                        required=True, type=str, help='hostname')
    parser.add_argument('-f', dest='filename', required=False, type=str, nargs='+',
                        help='file names to monitor. Default: downtimes-ok poem-ok topology-ok weights-ok')
    cmd_options = parser.parse_args()

    global_conf = Global(None)
    options = global_conf.parse()
    root_directory = options['inputstatesavedir'][:-1]
    days_num = int(options['inputstatedays'])
    todays_date = datetime.today()

    days = []
    for i in range(1, days_num + 1):
        days.append(todays_date + timedelta(days=-i))

    date_sufix = []

    for day in days:
        date_sufix.append(day.strftime("%Y_%m_%d"))

    nagios = NagiosResponse("All connectors are working fine.")
    try:
        result = process_customer_jobs(
            arguments=cmd_options, root_dir=root_directory, date_sufix=date_sufix, nagios=nagios)

    except OSError as e:
        nagios.setCode(nagios.CRITICAL)
        if getattr(e, 'filename', False):
            nagios.writeCriticalMessage('{0} {1}'.format(repr(e), e.filename))
        else:
            nagios.writeCriticalMessage(repr(e))
        raise SystemExit(nagios.getCode())

    except Exception as e:
        nagios.setCode(nagios.CRITICAL)
        nagios.writeCriticalMessage(repr(e))
        raise SystemExit(nagios.getCode())

    print(result if len(result) > 0 else nagios.getMsg())
    raise SystemExit(nagios.getCode())


if __name__ == "__main__":
    main()
