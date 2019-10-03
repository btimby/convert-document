all: test

.PHONY: build
build:
	docker build -f Dockerfile -t btimby/preview-server .
	docker build -f Dockerfile.soffice -t btimby/preview-soffice .

.PHONY: build-cache
build-cache:
	docker pull btimby/preview-server || true
	docker pull btimby/preview-soffice || true
	docker build --cache-from btimby/preview-server -f Dockerfile -t btimby/preview-server .
	docker build --cache-from btimby/preview-soffice -f Dockerfile.soffice -t btimby/preview-soffice .

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
	docker-compose -f run.yml -p preview-demo up \
		--scale soffice-server=3 --scale preview-server=1

.PHONY: shell
shell:
	docker run -ti btimby/preview-server bash

.PHONY: login
	echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin

.PHONY: tag
tag: login
	docker tag btimby/preview-server btimby/preview-server:$TRAVIS_COMMIT
	docker tag btimby/preview-soffice btimby/preview-soffice:$TRAVIS_COMMIT

.PHONY: push
push: login
	docker push btimby/preview-server:$TRAVIS_COMMIT
	docker push btimby/preview-server:latest
	docker push btimby/preview-soffice:$TRAVIS_COMMIT
	docker push btimby/preview-soffice:latest
