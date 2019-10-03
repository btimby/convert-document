all: test

.PHONY: build
build:
	docker build -f Dockerfile -t btimby/preview-base .
	docker build -f Dockerfile.soffice -t btimby/preview-soffice .
	docker build -f Dockerfile.preview -t btimby/preview-server .

.PHONY: build-cache
build-cache:
	docker pull btimby/preview-base || true
	docker pull btimby/preview-soffice || true
	docker pull btimby/preview-server || true
	docker build --cache-from btimby/preview-base -f Dockerfile -t btimby/preview-base .
	docker build --cache-from btimby/preview-soffice -f Dockerfile.soffice -t btimby/preview-soffice .
	docker build --cache-from btimby/preview-server -f Dockerfile.preview -t btimby/preview-server .

Pipfile: Pipfile.lock
	pipenv install --dev
	touch Pipfile

.PHONY: start-test-server
test-server:
	docker run -d --rm --name preview-server-test -v ${CURDIR}/docker/monit/monitrc.test:/etc/monitrc btimby/preview-server

.PHONY: test
test: Pipfile
	pipenv run python3 test.py

.PHONY: stop-test-server
stop-test-server:
	docker kill preview-server-test

.PHONY: test.html
test.html:
	firefox file://${CURDIR}/test.html

.PHONY: run
run: build
	docker-compose -f run.yml -p preview-demo up \
		--scale soffice-server=3 --scale preview-server=1

.PHONY: shell
shell:
	docker run -ti btimby/preview-server bash

.PHONY: login
	echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin

.PHONY: tag
tag: login
	docker tag btimby/preview-base btimby/preview-base:latest
	docker tag btimby/preview-server btimby/preview-server:latest
	docker tag btimby/preview-soffice btimby/preview-soffice:latest

.PHONY: tag
tag-travis: tag
	docker tag btimby/preview-base btimby/preview-base:${TRAVIS_COMMIT}
	docker tag btimby/preview-server btimby/preview-server:${TRAVIS_COMMIT}
	docker tag btimby/preview-soffice btimby/preview-soffice:${TRAVIS_COMMIT}

.PHONY: push
push: login
	docker push btimby/preview-base:latest
	docker push btimby/preview-server:latest
	docker push btimby/preview-soffice:latest

.PHONY: push-travis
push-travis: push
	docker push btimby/preview-base:${TRAVIS_COMMIT}
	docker push btimby/preview-server:${TRAVIS_COMMIT}
	docker push btimby/preview-soffice:${TRAVIS_COMMIT}
