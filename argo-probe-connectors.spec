%define dir /usr/libexec/argo/probes/connectors

Name:          argo-probe-connectors
Summary:       Multi-tenant aware probes checking argo-connectors.
Version:       0.1.3
Release:       1%{?dist}
License:       ASL 2.0
Source0:       %{name}-%{version}.tar.gz
BuildRoot:     %{_tmppath}/%{name}-%{version}-%{release}-root
Group:         Network/Monitoring
BuildArch:     noarch
BuildRequires: python3-devel
Requires:      python3-requests

%description
This package includes probe that check argo-connectors component.

%prep
%setup -q

%build
%{py3_build}

%install
%{py3_install "--record=INSTALLED_FILES" }

%clean
rm -rf $RPM_BUILD_ROOT

%files -f INSTALLED_FILES
%defattr(-,root,root,-)
%{python3_sitelib}/argo_probe_connectors
%{dir}


%changelog
* Wed Jan 25 2023 Daniel Vrcic <dvrcic@gmail.com> - 0.1.0-1%{?dist}
- AO-650 Harmonize argo-mon probes
