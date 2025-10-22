# argo-probe-connectors

Probe is inspecting `argo-connectors` component by looking at the `state` files that contain simple `True/False` designating whether configured connector successfully fetched the data from source or not. It is running on the same host where `argo-connectors` component resides and reports back the inspection of service leveraging NRPE Nagios service.

Steps of the probe are:
1) contact the POEM's `/api/v2/internal/public_tenants` to find out the list of configured tenants
2) query local `/etc/argo-connectors/global.conf` to find out where is the root directory with the state files - `InputState.SaveDir`
3) query each individual tenant configuration file to get a list of configured jobs/reports
4) check `True/False` content of `InputState.SaveDir/<TENANT_NAME>/{topology-ok, downtimes-ok, services-ok}` and `InputSave.SaveDir/<TENANT_NAME>/<JOB_NAME>/{weights-ok}` state files

Probe reports `CRITICAL` status if any of running connectors are failing for last three days in a row and `WARNING` if connector fails for previous day.

## Usage

Default arguments:
```
$ /usr/libexec/argo/probes/connectors/connectors-probe -h
usage: connectors-probe [-h] -H HOSTNAME

optional arguments:
  -h, --help   show this help message and exit
  -H HOSTNAME  SuperPOEM hostname
```

Example of probe run with different status messages:
```
./connectors-probe -H poem.devel.argo.grnet.gr
OK - All connectors are working fine
WARNING - Tenant: EGI, Filename: TOPOLOGY not ok for previous day
WARNING - Tenant: EUDAT, Filename: TOPOLOGY not ok for previous day / Tenant: SDC, Filename: DOWNTIMES not ok for previous day
```
