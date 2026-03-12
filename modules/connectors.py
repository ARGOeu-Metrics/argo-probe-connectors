import os
import argparse
import copy
import requests
import itertools

from datetime import datetime, timedelta
from itertools import groupby, zip_longest
from argo_connectors.config.glob import Global
from argo_probe_connectors.NagiosResponse import NagiosResponse
from argo_probe_connectors.utils import errmsg_from_excp


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


def extract_tenant_name(jobdir, root_directory):
    rel_jobdir = jobdir.split(root_directory)[1]
    if '/' in rel_jobdir:
        rel_jobdir = rel_jobdir.split('/')

    for name in rel_jobdir:
        if name:
            return name

    return 'UNKNOWN'


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


def return_missing_file_n_tenant(list_files, dates, list_root, root_directory):
    result_in_dates_sublists = list()
    result_in_dates = list()
    result_out_dates = list()
    for sublist in list_files:
        in_dates = sorted([item for item in sublist if item[-10:] in dates])
        in_dates_sublst = [list(group) for key, group in itertools.groupby(
            in_dates, key=lambda s: s.split("_")[0])]
        out_dates = [item for item in sublist if item[-10:] not in dates]
        result_in_dates.append(in_dates)
        result_out_dates.append(out_dates)
        result_in_dates_sublists.append(in_dates_sublst)

    today = datetime.today().strftime("%Y_%m_%d")
    list_missing_today = list()
    for lst in result_in_dates_sublists:
        miss_today = [[] if any(today in w for w in sub_l) else [
            sub_l[0].partition('_')[0]] for sub_l in lst]
        miss_today = [i for i in miss_today if 'downtimes-ok' in i]
        list_missing_today.append(miss_today)
    miss_today_position = [i for i, sublist1 in enumerate(list_missing_today) if any(
        ['downtimes-ok' in sublist2 for sublist2 in sublist1])]
    missing_today_tenant = [extract_tenant_name(list_root[i], root_directory) for i in miss_today_position]
    missing_today_files = [
        x for sublist1 in list_missing_today for sublist2 in sublist1 for x in sublist2 if x != []]

    ystday_date = (datetime.today() - timedelta(days=1)).strftime("%Y_%m_%d")
    list_missing_yestday = list()
    for lst in result_in_dates_sublists:
        miss_ystday = [[] if any(ystday_date in w for w in sub_l) else [
            sub_l[0].partition('_')[0]] for sub_l in lst]
        list_missing_yestday.append(miss_ystday)

    missing_ystday_positions = [i for i, l1 in enumerate(
        list_missing_yestday) for j, l2 in enumerate(l1) for k, item in enumerate(l2) if item != []]
    missing_ystday_tenant = [extract_tenant_name(list_root[i], root_directory)
                             for i in missing_ystday_positions]
    missing_ystday_files = [
        x for sublist1 in list_missing_yestday for sublist2 in sublist1 for x in sublist2 if x != []]

    result_x = [[item.split("_")[0] for item in sublist]
                for sublist in result_in_dates]
    result_y = [[item.split("_")[0] for item in sublist]
                for sublist in result_out_dates]
    results = list()
    for sublist_x, sublist_y in zip(result_x, result_y):
        results.append(set(sublist_y).difference(set(sublist_x)))
    missing = [list(s) for s in results]
    missing_elem_positions = [i for i, elem in enumerate(missing) if elem]
    missing_tenant = [extract_tenant_name(list_root[i], root_directory)
                      for i in missing_elem_positions]
    missing_files = [elem for elem in missing if len(elem) > 0]

    return missing_tenant, missing_files, missing_ystday_tenant, missing_ystday_files, missing_today_tenant, missing_today_files


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

    return sorted_file_copy, sorted_file


def extract_tenant_path(root_dir, path, job_names):
    path_no_root = [item.replace(root_dir, '') for item in path]
    splt_path = path_no_root[0].split("/")
    tenant_name = splt_path[1]
    if splt_path[2] in job_names:
        job = splt_path[2]
    else:
        job = ""
    filename = splt_path[-1].split("-")[0].upper()

    return tenant_name, job, filename


downtime_state = 'downtimes-ok'
topology_state = 'topology-ok'
servtype_state = 'services-ok'
weights_state = 'weights-ok'


def normalize_tenant_name(tenant_name):
    return tenant_name.strip().upper()


def normalize_connector_name(connector_name):
    return connector_name.strip().lower()


def parse_noconnector_rules(noconnector_items, valid_connectors):
    parsed_rules = dict()
    if not noconnector_items:
        return parsed_rules

    normalized_valid = {normalize_connector_name(conn) for conn in valid_connectors}
    for item in noconnector_items:
        if "=" not in item:
            raise ValueError(
                f"Invalid value '{item}' for -n. Expected format TENANT=connector")

        tenant_name, connector_name = item.split("=", 1)
        tenant_name = normalize_tenant_name(tenant_name)
        connector_name = normalize_connector_name(connector_name)

        if not tenant_name:
            raise ValueError(
                f"Invalid value '{item}' for -n. Tenant cannot be empty")
        if not connector_name:
            raise ValueError(
                f"Invalid value '{item}' for -n. Connector cannot be empty")
        if connector_name not in normalized_valid:
            raise ValueError(
                f"Invalid connector '{connector_name}' for -n. Allowed connectors: {', '.join(sorted(normalized_valid))}")

        parsed_rules.setdefault(tenant_name, set()).add(connector_name)

    return parsed_rules


def connector_is_skipped(skip_map, tenant_name, connector_name):
    tenant_key = normalize_tenant_name(tenant_name)
    connector_key = normalize_connector_name(connector_name)
    return connector_key in skip_map.get(tenant_key, set())


def process_customer_jobs(arguments, root_dir, date_sufix, days_num, root_directory):
    nagios = NagiosResponse("All connectors are working fine.")

    file_names = [downtime_state, topology_state, weights_state, servtype_state]
    noconnector_map = parse_noconnector_rules(arguments.noconnector, file_names)

    try:
        get_tenants = requests.get(
            'https://' + arguments.hostname + '/api/v2/internal/public_tenants/').json()

        job_names = list()
        list_paths = list()
        list_files = list()
        list_root = list()


        for tenant in get_tenants:
            tenant_name = tenant["name"]
            if (arguments.skip is not None \
                and tenant_name in arguments.skip):
                continue

            tenant_file_names = [name for name in file_names if not connector_is_skipped(
                noconnector_map, tenant_name, name)]

            for (root, dirs, files) in os.walk(f'{root_dir + "/" + tenant_name}', topdown=True):
                files_filtered = [item for item in files if any(
                    item.startswith(file_name) for file_name in tenant_file_names)]

                list_files.append(files_filtered)
                list_root.append(root)

                for dir in dirs:
                    if dir not in job_names and dir != []:
                        job_names.append(dir)

                for file in files:
                    file_no_date = file.split("_")[0]
                    if file_no_date in tenant_file_names:
                        file_path = (root + "/" + file_no_date)

                        dates = create_dates(file, date_sufix)

                        for sufix in dates:
                            path_name_date = file_path + '_' + sufix
                            file_exists = os.path.exists(path_name_date)
                            if file_exists == True:
                                list_paths.append(
                                    path_name_date + "=" + str(check_file_ok(path_name_date)))

        date_list = [(datetime.today() - timedelta(days=x)
                      ).strftime('%Y_%m_%d') for x in range(4)]

        missing_tenant, missing_files, missing_ystday_tenant, missing_ystday_files, missing_today_tenant, missing_today_files = return_missing_file_n_tenant(
            list_files, date_list, list_root, root_directory)
        sorted_file_copy, sorted_file = sort_n_copy_files(list_paths)

        warning_msg = ""
        critical_msg = ""

        if missing_files != "":
            for idx, sublist in enumerate(missing_files):
                for elem in sublist:
                    if connector_is_skipped(noconnector_map, missing_tenant[idx], elem):
                        continue
                    nagios.setCode(nagios.CRITICAL)
                    msg = ("Tenant: " + missing_tenant[idx] + ", State of a file: " + elem.upper() +
                           " is missing for last " + str(days_num) + " days!" + " /")
                    critical_msg += (msg + " ")

        if missing_ystday_files != "":
            for i in range(len(missing_ystday_tenant)):
                if connector_is_skipped(noconnector_map, missing_ystday_tenant[i], missing_ystday_files[i]):
                    continue
                nagios.setCode(nagios.CRITICAL)
                msg = ("Tenant: " + missing_ystday_tenant[i] + ", State of a file: " + missing_ystday_files[i].upper() +
                       " is missing for last day!" + " /")
                critical_msg += (msg + " ")

        if missing_today_files != "":
            for i in range(len(missing_today_tenant)):
                if connector_is_skipped(noconnector_map, missing_today_tenant[i], missing_today_files[i]):
                    continue
                nagios.setCode(nagios.CRITICAL)
                msg = ("Tenant: " + missing_today_tenant[i] + ", State of a file: " + missing_today_files[i].upper() +
                       " is missing for today!" + " /")
                critical_msg += (msg + " ")

        for path, result in zip_longest(sorted_file_copy, sorted_file):
            tenant_name, job, filename = extract_tenant_path(
                root_dir, path, job_names)
            if connector_is_skipped(noconnector_map, tenant_name, filename):
                continue

            if all(item == "False" for item in result[-(int(days_num)):]):

                nagios.setCode(nagios.CRITICAL)
                if job == "":
                    msg = ("Tenant: " + tenant_name + ", File: " + filename +
                           " not ok for last " + str(days_num) + " days!" + " /")
                else:
                    msg = ("Tenant: " + tenant_name + ", Job: " + job + ", File: " +
                           filename + " not ok for last " + str(days_num) + " days!" + " /")
                critical_msg += (msg + " ")

            elif result[-1] == "False":
                nagios.setCode(nagios.WARNING)
                if job == "":
                    msgs = ("Tenant: " + tenant_name +
                            ", Filename: " + filename + " not ok for previous day /")
                else:
                    msgs = ("Tenant: " + tenant_name + ", Job: " +
                            job + ", Filename: " + filename + " not ok for previous day /")
                warning_msg += (msgs + " ")

        if len(list_root) == 0:
            nagios.setCode(nagios.CRITICAL)
            nagios.writeCriticalMessage("SaveDir is empty")
        else:
            nagios.writeCriticalMessage(critical_msg[:-2])
            nagios.writeWarningMessage(warning_msg[:-2])

    except requests.exceptions.RequestException as e:
        nagios.setCode(nagios.CRITICAL)
        nagios.writeCriticalMessage(
            f"API cannot connect to https://{arguments.hostname}/api/v2/internal/public_tenants/:{errmsg_from_excp(e)}")

    except ValueError as e:
        nagios.setCode(nagios.CRITICAL)
        nagios.writeCriticalMessage(f"{errmsg_from_excp(e)}")

    except OSError as e:
        nagios.setCode(nagios.CRITICAL)
        nagios.writeCriticalMessage(f"{errmsg_from_excp(e)}")

    except Exception as e:
        nagios.setCode(nagios.CRITICAL)
        nagios.writeCriticalMessage(f"{errmsg_from_excp(e)}")

    print(nagios.getMsg())
    raise SystemExit(nagios.getCode())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-H', dest='hostname',
                        required=True, type=str, help='SuperPOEM hostname')
    parser.add_argument('-s', dest='skip',
                        required=False, type=str, nargs='+', help='skip tenant')
    parser.add_argument('-n', dest='noconnector',
                        required=False, type=str, action='append', help='skip connector state for a tenant (TENANT=connector)')

    cmd_options = parser.parse_args()

    globopts = Global('connectors-probe')
    root_directory = globopts.options()['inputstatesavedir']
    days_num = int(Global.options()['inputstatedays'])
    todays_date = datetime.today()

    days = []
    for i in range(1, days_num + 1):
        days.append(todays_date + timedelta(days=-i))

    date_sufix = []
    for day in days:
        date_sufix.append(day.strftime("%Y_%m_%d"))

    process_customer_jobs(cmd_options, root_directory, date_sufix, days_num, root_directory)


if __name__ == "__main__":
    main()
