FROM ubuntu:18.04

ENV DEBIAN_FRONTEND noninteractive
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

COPY docker/debs/ghostscript*.deb /app/
COPY docker/debs/libgs*.deb /app/

RUN apt-get update \
    && apt-get -y update \
    && apt-get -y install /app/libgs9_9.26~dfsg+0-0ubuntu0.18.04.11-threadsafe_amd64.deb \
    /app/libgs9-common_9.26~dfsg+0-0ubuntu0.18.04.11-threadsafe_all.deb \
    /app/libgs-dev_9.26~dfsg+0-0ubuntu0.18.04.11-threadsafe_amd64.deb \
    /app/ghostscript_9.26~dfsg+0-0ubuntu0.18.04.11-threadsafe_amd64.deb \
    && apt-get -y upgrade \
    && apt-get -y install libreoffice libreoffice-writer ure libreoffice-java-common \
        libreoffice-core libreoffice-common openjdk-8-jre fonts-opensymbol \
        hyphen-fr hyphen-de hyphen-en-us hyphen-it hyphen-ru fonts-dejavu \
        fonts-dejavu-core fonts-dejavu-extra fonts-droid-fallback fonts-dustin \
        fonts-f500 fonts-fanwood fonts-freefont-ttf fonts-liberation fonts-lmodern \
        fonts-lyx fonts-sil-gentium fonts-texgyre fonts-tlwg-purisa python3-pip \
        python3-uno python3-lxml python3-icu curl imagemagick  libmagickwand-dev \
        ffmpeg python-setuptools git circus \
    && apt-get -y autoremove \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /app
COPY Pipfile* /app/
COPY aiohttp-4.0.0a0-cp36-cp36m-linux_x86_64.whl /app/
RUN pip3 install pipenv
RUN pipenv install --system

COPY docker/soffice-wrapper /app/
COPY docker/circusd.ini /etc/circus/circusd.ini
COPY docker/ImageMagick-6-policy.xml /etc/ImageMagick-6/policy.xml

COPY preview/ /app/preview/
COPY images/ /app/images/
COPY fixtures/ /app/fixtures/

EXPOSE 3000/tcp

# Configuration, TODO: make args.
ENV PREVIEW_CACHE_CONTROL=5
ENV PREVIEW_FILES=/mnt/files
ENV PREVIEW_LOGLEVEL=WARNING
ENV PREVIEW_HTTP_LOGLEVEL=WARNING
ENV PREVIEW_STORE=/mnt/store
ENV PREVIEW_STORE_MAX_SIZE=10G
ENV PREVIEW_STORE_CLEANUP_INTERVAL=15

# USER nobody:nogroup
CMD ["/usr/bin/circusd", "/etc/circus/circusd.ini"]
