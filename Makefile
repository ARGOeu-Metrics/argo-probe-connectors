PKGNAME=argo-probe-connectors
SPECFILE=${PKGNAME}.spec
PKGVERSION=$(shell grep -s '^Version:' $(SPECFILE) | sed -e 's/Version: *//')

dist:
	rm -rf dist
	python3 setup.py sdist
	mv dist/${PKGNAME}-${PKGVERSION}.tar.gz .
	rm -rf dist

srpm: dist
	rpmbuild -ts --define='dist .el9' ${PKGNAME}-${PKGVERSION}.tar.gz

rpm: dist
	rpmbuild -ta ${PKGNAME}-${PKGVERSION}.tar.gz

sources: dist

clean:
	rm -rf ${PKGNAME}-${PKGVERSION}.tar.gz
	rm -f MANIFEST
	rm -rf dist

