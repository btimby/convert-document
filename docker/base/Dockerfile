FROM ubuntu:18.04

ARG SOURCE_COMMIT=unknown
ENV SENTRY_RELEASE="${SOURCE_COMMIT}"

ENV DEBIAN_FRONTEND noninteractive
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

COPY packages/ /app/packages/

RUN apt-get update \
    && apt-get -y update \
    && apt-get -y install \
        /app/packages/libgs9_9.26~dfsg+0-0ubuntu0.18.04.11-threadsafe_amd64.deb \
        /app/packages/libgs9-common_9.26~dfsg+0-0ubuntu0.18.04.11-threadsafe_all.deb \
        /app/packages/libgs-dev_9.26~dfsg+0-0ubuntu0.18.04.11-threadsafe_amd64.deb \
        /app/packages/ghostscript_9.26~dfsg+0-0ubuntu0.18.04.11-threadsafe_amd64.deb \
    && apt-get -y upgrade \
    && apt-get -y install \
        ure libreoffice libreoffice-core libreoffice-java-common libreoffice-common \
        libreoffice-writer libreoffice-impress libreoffice-calc libreoffice-draw \
        openjdk-8-jre fonts-opensymbol hyphen-fr hyphen-de hyphen-en-us \
        hyphen-it hyphen-ru fonts-dejavu fonts-dejavu-core fonts-dejavu-extra \
        fonts-droid-fallback fonts-dustin fonts-f500 fonts-fanwood \
        fonts-freefont-ttf fonts-liberation fonts-lmodern fonts-lyx \
        fonts-sil-gentium fonts-texgyre fonts-tlwg-purisa python3-pip \
        python3-uno python3-lxml python3-icu curl libmagickwand-dev \
        python-setuptools git libavformat-dev libavcodec-dev libavutil-dev \
        libswscale-dev libavfilter-dev libswresample-dev libavdevice-dev inotify-tools \
        inkscape wget \
    && apt-get -y autoremove \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ENV IMAGEMAGICK_VERSION 7.0.10-29
RUN wget https://www.imagemagick.org/download/ImageMagick-${IMAGEMAGICK_VERSION}.tar.xz \
    && tar xJf ImageMagick-${IMAGEMAGICK_VERSION}.tar.xz \
    && cd ImageMagick-${IMAGEMAGICK_VERSION} \
    && ./configure --with-rsvg=yes && make -j4 && make install && ldconfig /usr/local/lib \
    && cd / && rm -rf ImageMagick-*

ENV TINI_VERSION v0.18.0
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /tini
RUN chmod +x /tini

WORKDIR /app
COPY Pipfile* /app/
RUN pip3 install pipenv
RUN pipenv install --system

COPY preview/ /app/preview/
COPY images/ /app/images/
COPY plugins/ /app/plugins/
COPY tests/ /app/tests/
COPY fixtures/ /app/fixtures/
