TAG = btimby/preview-server

all: test

build:
	docker build -t ${TAG} .

test: build
	docker run -ti ${TAG} pytest

shell: build
	docker run -ti ${TAG} sh

run: build
	docker run -p 3000:3000 --tmpfs /tmp -v ${CURDIR}/fixtures:/mnt/files -ti ${TAG}
