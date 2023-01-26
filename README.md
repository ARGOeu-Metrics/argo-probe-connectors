# argo-probe-connectors

Probe is inspecting `argo-connectors` component by looking at the `state` files that contain simple `True/False` designating whether configured connector successfully fetched the data from source or not. It is running on the same host where `argo-connectors` component resides and reports back the inspection of service leveraging NRPE Nagios service.

Steps of the probe are:
1) contact the POEM's `/api/v2/internal/public_tenants` to find out the list of configured tenants
2) query local `/etc/argo-connectors/global.conf` to find out where is the root directory with the state files - `InputState.SaveDir`
3) query each individual tenant configuration file to get a list of configured jobs/reports
4) check content of `InputState.SaveDir/<TENANT_NAME>/{topology-ok, downtimes-ok}` and `InputSave.SaveDir/<TENANT_NAME>/<JOB_NAME>/{metricprofile-ok, weights-ok}` state files
