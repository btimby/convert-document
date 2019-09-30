TAG = btimby/preview-server

all: test

build:
	docker build -t ${TAG} .

shell: build
	docker run -ti ${TAG} sh

run: build
	docker run -p 3000:3000 --rm --name preview-server --tmpfs /tmp --tmpfs /mnt/store -v ${CURDIR}/fixtures:/mnt/files -ti ${TAG}

Pipfile: Pipfile.lock
	pipenv install --dev
	touch Pipfile

.PHONY: test
test: Pipfile
	pipenv run python3 test.py

.PHONY: test.html
test.html:
	firefox file://${CURDIR}/test.html

.PHONY: demo
demo:
	docker-compose -p preview-demo up
