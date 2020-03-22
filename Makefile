PKGNAME = $(shell dpkg-parsechangelog -S source)
VERSION = $(shell dpkg-parsechangelog -S version | sed 's/-.*//')
DIST = $(shell dpkg-parsechangelog -S distribution)

all:

release:
	tar --numeric-owner --group 0 --owner 0 -cJh \
	  --xform "s,^,$(PKGNAME)-$(VERSION)/," \
	  -f $(PKGNAME)-$(VERSION).tar.xz \
	  doc include/*.h src/*.c rpack/*.py misc test \
	  README.rst MANIFEST.in LICENSE.md \
	  setup.py requirements*.txt

deb-ci:
	if [ -z "$$CI_COMMIT_TAG" ]; then \
	  DEBFULLNAME="$$GITLAB_USER_NAME" DEBEMAIL="$$GITLAB_USER_EMAIL" \
	   dch -l+git.$$CI_PIPELINE_ID.$$CI_COMMIT_SHORT_SHA "Untagged build" -D unstable; \
	else \
	  if [ "$$CI_COMMIT_TAG" != "$(VERSION)" ] && [ "$$CI_COMMIT_TAG" != "v$(VERSION)" ]; then \
	     echo "debian/changelog has not been updated to the new version!"; \
	     exit 1; \
	  fi; \
	  if [ "$(DIST)" != "stable" ]; then \
	     echo "debian/changelog must use stable for tagged releases (DIST=$$DIST)!"; \
	     exit 1; \
	  fi \
	fi

deb: release
	rm -rf ./$(PKGNAME)-$(VERSION)
	tar -xJf $(PKGNAME)-$(VERSION).tar.xz
	ln -sf $(PKGNAME)-$(VERSION).tar.xz \
	  $(PKGNAME)_$(VERSION).orig.tar.xz
	cp -a debian/ $(PKGNAME)-$(VERSION)/
	(cd $(PKGNAME)-$(VERSION) && DEB_BUILD_OPTIONS=noddebs dpkg-buildpackage -us -uc)

clean:
	-rm -rf $(PKGNAME)[-_]*
	-rm python3-$(PKGNAME)_*.deb

.PHONY: all release deb-ci deb clean