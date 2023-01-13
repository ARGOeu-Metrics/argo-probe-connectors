import unittest
import requests
from unittest.mock import patch
from types import SimpleNamespace
import os

from multi_tenant_connectors_sensor.multi_tenant_connector import process_customer_jobs, check_file_ok, NagiosResponse, grouper, return_missing_file_n_tenant, create_dates, sort_n_copy_files, extract_tenant_path

class MockResponse:
    def __init__(self, data, status_code):
        self.data = data
        self.status_code = status_code

    def json(self):
        return self.data

    def raise_for_status(self):
        if self.status_code != 200:
            raise requests.exceptions.RequestException("Error has occured")


def pass_web_api(*args, **kwargs):
    return MockResponse(
        data=mock_tenants,
        status_code=200
    )


def fail_web_api(*args, **kwargs):
    return MockResponse(
        data="mock_tenants",
        status_code=401
    )


mock_tenants = [
    {
        "name": "mock_name_1",
        "schema_name": "mock_1",
        "domain_url": "mock.domain.1",
        "created_on": "2022-09-24",
        "nr_metrics": 111,
        "nr_probes": 11
    },
    {
        "name": "mock_name_2",
        "schema_name": "mock_2",
        "domain_url": "mock.domain.2",
        "created_on": "2022-09-24",
        "nr_metrics": 222,
        "nr_probes": 22
    },
]


class ArgoProbeConnector(unittest.TestCase):
    def setUp(self):
        arguments = {"hostname": "mock_hostname", "filename": "mock_filename"}
        self.arguments = SimpleNamespace(**arguments)

        self.root_dir = "/etc/mock_path/"
        self.date_sufix = '[2011-11-23]'
        self.days_num = "3"

        with open("test_file.txt", "w") as f:
            f.write("True")

    def tearDown(self):
        NagiosResponse._msgBagCritical = []
        os.remove("test_file.txt")

    @patch("builtins.print")
    @patch("multi_tenant_connectors_sensor.multi_tenant_connector.extract_tenant_path")
    @patch("multi_tenant_connectors_sensor.multi_tenant_connector.sort_n_copy_files")
    @patch("multi_tenant_connectors_sensor.multi_tenant_connector.return_missing_file_n_tenant")
    @patch("multi_tenant_connectors_sensor.multi_tenant_connector.requests.get")
    def test_all_passed(self, mock_requests, mock_return_missing_file_n_tenant, mock_sort_n_copy_files, mock_extract_tenant_path, mock_print):
        mock_requests.side_effect = pass_web_api
        mock_return_missing_file_n_tenant.return_value = "foo_tenant", ""
        mock_sort_n_copy_files.return_value = [["/var/lib/mock-connectors/states//mock_tenant/services-ok_2023_01_02=True"]], [
            "True", "True", "True", "True", "True"], ["foo_sorted_path"]
        mock_extract_tenant_path.return_value = ["foo_tenant_1", "foo_tenant_2"], [
            "foo_job_1", "foo_job_2"], ["foo_file_1", "foo_file_2"]

        with self.assertRaises(SystemExit) as e:
            process_customer_jobs(
                self.arguments, self.root_dir, self.date_sufix, self.days_num)

        mock_print.assert_called_once_with(
            'OK - All connectors are working fine.')

        self.assertEqual(e.exception.code, 0)

    @patch("builtins.print")
    @patch("multi_tenant_connectors_sensor.multi_tenant_connector.return_missing_file_n_tenant")
    @patch("multi_tenant_connectors_sensor.multi_tenant_connector.requests.get")
    def test_state_dir_missing(self, mock_requests, mock_return_missing_file_n_tenant, mock_print):
        mock_requests.side_effect = pass_web_api
        mock_return_missing_file_n_tenant.return_value = "foo_tenant", ""

        with self.assertRaises(SystemExit) as e:
            process_customer_jobs(
                self.arguments, self.root_dir, self.date_sufix, self.days_num)

        mock_print.assert_called_once_with(
            'CRITICAL - SaveDir is empty')

        self.assertEqual(e.exception.code, 2)

    @patch("builtins.print")
    @patch("multi_tenant_connectors_sensor.multi_tenant_connector.requests.Response")
    @patch("multi_tenant_connectors_sensor.multi_tenant_connector.requests.get")
    def test_raise_request_exception(self, mock_requests_get, mock_requests_resp, mock_print):
        mock_requests_get.return_value = mock_requests_resp
        mock_requests_resp.json.side_effect = requests.exceptions.HTTPError

        with self.assertRaises(SystemExit) as e:
            process_customer_jobs(
                self.arguments, self.root_dir, self.date_sufix, self.days_num)

        mock_print.assert_called_once_with(
            'CRITICAL - API cannot connect to https://mock_hostname/api/v2/internal/public_tenants/:None')

        self.assertEqual(e.exception.code, 2)

    @patch("builtins.print")
    @patch("multi_tenant_connectors_sensor.multi_tenant_connector.requests.Response")
    @patch("multi_tenant_connectors_sensor.multi_tenant_connector.requests.get")
    def test_raise_valueerror(self, mock_requests_get, mock_requests_resp, mock_print):
        mock_requests_get.return_value = mock_requests_resp
        mock_requests_resp.json.side_effect = ValueError(
            "ValueError has occured")

        with self.assertRaises(SystemExit) as e:
            process_customer_jobs(
                self.arguments, self.root_dir, self.date_sufix, self.days_num)

        mock_print.assert_called_once_with(
            'CRITICAL - [Errno 2] No such file or directory ValueError has occured ')

        self.assertEqual(e.exception.code, 2)

    @patch("multi_tenant_connectors_sensor.multi_tenant_connector.os.stat")
    @patch("multi_tenant_connectors_sensor.multi_tenant_connector.os.path.isfile")
    def test_check_file_os_error(self, mock_isfile, mock_stat):
        mock_stat.side_effect = OSError(
            "[Errno 2] No such file or directory")
        mock_isfile.return_value = False

        with self.assertRaises(OSError):
            check_file_ok("test_file.txt")

    def test_file_exist_has_true(self):
        with open("test_file.txt", "w") as f:
            f.write("True")

        self.assertEqual(check_file_ok("test_file.txt"), True)

    def test_file_exist_has_false(self):
        with open("test_file.txt", "w") as f:
            f.write("foo")

        self.assertEqual(check_file_ok("test_file.txt"), False)

    @patch("builtins.print")
    @patch("multi_tenant_connectors_sensor.multi_tenant_connector.os.walk")
    @patch("multi_tenant_connectors_sensor.multi_tenant_connector.requests.get")
    def test_process_customer_job_os_error(self, mock_requests, mock_walk, mock_print):
        mock_requests.side_effect = pass_web_api
        mock_walk.side_effect = FileNotFoundError(
            "[Errno 2] No such file or directory")

        with self.assertRaises(SystemExit) as e:
            process_customer_jobs(
                self.arguments, self.root_dir, self.date_sufix, self.days_num)

        mock_print.assert_called_once_with(
            'CRITICAL - [Errno 2] No such file or directory ')

        self.assertEqual(e.exception.code, 2)

    @patch("builtins.print")
    @patch("multi_tenant_connectors_sensor.multi_tenant_connector.requests.Response")
    @patch("multi_tenant_connectors_sensor.multi_tenant_connector.requests.get")
    def test_raise_main_exception(self, mock_requests_get, mock_requests_resp, mock_print):
        mock_requests_get.return_value = mock_requests_resp
        mock_requests_resp.json.side_effect = Exception

        with self.assertRaises(SystemExit) as e:
            process_customer_jobs(
                self.arguments, self.root_dir, self.date_sufix, self.days_num)

        mock_print.assert_called_once_with('CRITICAL - None')

        self.assertEqual(e.exception.code, 2)

    def test_grouper(self):
        self.assertEqual(grouper("/path/to/directory/filename-ok.txt"),
                         ("/path/to/directory", "filename"))


if __name__ == "__main__":
    unittest.main()
