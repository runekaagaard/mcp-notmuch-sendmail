SHELL := /bin/bash
.SHELLFLAGS := -ec

.PHONY: publish-test publish-prod package-inspect-test package-inspect-prod package-run-test package-run-prod

VERSION := $(shell date +%Y.%m.%d.%H%M%S)

publish-test:
	rm -rf dist/*
	sed -i "s/version = \"[^\"]*\"/version = \"$(VERSION)\"/" pyproject.toml
	sed -i "s/mcp-notmuch-sendmail==[0-9.]*\"/mcp-notmuch-sendmail==$(VERSION)\"/g" README.md
	uv build
	uv publish --token "$$PYPI_TOKEN_TEST" --publish-url https://test.pypi.org/legacy/
	git checkout README.md pyproject.toml

publish-prod:
	rm -rf dist/*
	echo "$(VERSION)" > VERSION.txt
	sed -i "s/version = \"[^\"]*\"/version = \"$(VERSION)\"/" pyproject.toml
	sed -i "s/mcp-notmuch-sendmail==[0-9.]*\"/mcp-notmuch-sendmail==$(VERSION)\"/g" README.md
	uv build
	uv publish --token "$$PYPI_TOKEN_PROD"
	git commit -am "Published version $(VERSION) to PyPI"
	git push

package-inspect-test:
	rm -rf /tmp/test-mcp-notmuch-sendmail
	uv venv /tmp/test-mcp-notmuch-sendmail --python 3.10
	source /tmp/test-mcp-notmuch-sendmail/bin/activate && uv pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ mcp-notmuch-sendmail
	tree /tmp/test-mcp-notmuch-sendmail/lib/python3.10/site-packages/mcp_notmuch_sendmail
	source /tmp/test-mcp-notmuch-sendmail/bin/activate && which mcp-notmuch-sendmail

package-inspect-prod:
	rm -rf /tmp/test-mcp-notmuch-sendmail
	uv venv /tmp/test-mcp-notmuch-sendmail --python 3.10
	source /tmp/test-mcp-notmuch-sendmail/bin/activate && uv pip install mcp-notmuch-sendmail
	tree /tmp/test-mcp-notmuch-sendmail/lib/python3.10/site-packages/mcp_notmuch_sendmail
	source /tmp/test-mcp-notmuch-sendmail/bin/activate && which mcp-notmuch-sendmail

package-run-test:
	uvx --default-index https://test.pypi.org/simple/ --index https://pypi.org/simple/ --from mcp-notmuch-sendmail mcp-notmuch-sendmail

package-run-prod:
	uvx --from mcp-notmuch-sendmail mcp-notmuch-sendmail
