TAG=latest

all: test

.PHONY: build
build:
	docker build -f docker/base/Dockerfile -t btimby/preview-base .
	docker build -f docker/soffice/Dockerfile -t btimby/preview-soffice .
	docker build -f docker/preview/Dockerfile -t btimby/preview-server .


.PHONY: build-cache
build-cache:
	docker pull btimby/preview-base || true
	docker pull btimby/preview-soffice || true
	docker pull btimby/preview-server || true
	docker build --cache-from btimby/preview-base -f docker/base/Dockerfile -t btimby/preview-base .
	docker build --cache-from btimby/preview-soffice -f docker/soffice/Dockerfile -t btimby/preview-soffice .
	docker build --cache-from btimby/preview-server -f docker/preview/Dockerfile -t btimby/preview-server .


Pipfile: Pipfile.lock
	pipenv install --dev
	touch Pipfile


.PHONY: test
test: Pipfile
	pipenv run python3 -m tests


.PHONY: integration
integration: Pipfile
	pipenv run python3 integration.py


.PHONY: small
small: build
	docker-compose -f small.yml -p preview-small up


.PHONY: medium
medium: build
	docker-compose -f medium.yml -p preview-medium up --scale soffice-server=3


.PHONY: large
large: build
	docker-compose -f large.yml -p preview-large up \
		--scale soffice-server=5 --scale preview-server=2

.PHONY: dev
dev: build
	docker-compose -f dev.yml -p preview-dev up --scale soffice-server=3


.PHONY: run
run: small


.PHONY: shell
shell:
	docker run -ti btimby/preview-server bash


.PHONY: login
login:
	echo "${DOCKER_PASSWORD}" | docker login -u "${DOCKER_USERNAME}" --password-stdin


.PHONY: tag
tag:
	docker tag btimby/preview-base btimby/preview-base:${TAG}
	docker tag btimby/preview-server btimby/preview-server:${TAG}
	docker tag btimby/preview-soffice btimby/preview-soffice:${TAG}


.PHONY: push
push: login
	docker push btimby/preview-base:${TAG}
	docker push btimby/preview-server:${TAG}
	docker push btimby/preview-soffice:${TAG}
