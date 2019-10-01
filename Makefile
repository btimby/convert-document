all: test

.PHONY: build
build:
	docker build -f Dockerfile -t btimby/preview-server .
#	docker build -f Dockerfile.soffice -t btimby/preview-soffice .
#	docker build -f Dockerfile.preview -t btimby/preview-preview .

Pipfile: Pipfile.lock
	pipenv install --dev
	touch Pipfile

.PHONY: test
test: Pipfile
	pipenv run python3 test.py

.PHONY: test.html
test.html:
	firefox file://${CURDIR}/test.html

.PHONY: run
run: build
	docker-compose -p preview-demo up --scale soffice-server=2

.PHONY: shell
shell:
	docker run -ti btimby/preview-server bash
