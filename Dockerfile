FROM ubuntu:18.04

ENV DEBIAN_FRONTEND noninteractive
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

RUN apt-get update \
    && apt-get -y install software-properties-common \
    && add-apt-repository ppa:libreoffice/ppa \
    && apt-get -y update \
    && apt-get -y upgrade \
    && apt-get -y install libreoffice libreoffice-writer ure libreoffice-java-common \
        libreoffice-core libreoffice-common openjdk-8-jre fonts-opensymbol \
        hyphen-fr hyphen-de hyphen-en-us hyphen-it hyphen-ru fonts-dejavu \
        fonts-dejavu-core fonts-dejavu-extra fonts-droid-fallback fonts-dustin \
        fonts-f500 fonts-fanwood fonts-freefont-ttf fonts-liberation fonts-lmodern \
        fonts-lyx fonts-sil-gentium fonts-texgyre fonts-tlwg-purisa python3-pip \
        python3-uno python3-lxml python3-icu curl ghostscript libgs-dev imagemagick \
        libmagickwand-dev ffmpeg python-setuptools circus git \
    && apt-get -y autoremove \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY Pipfile* /app/
COPY circusd.ini /etc/circus/circusd.ini
COPY ImageMagick-6-policy.xml /etc/ImageMagick-6/policy.xml

WORKDIR /app
RUN pip3 install pipenv
RUN pipenv install --system

COPY preview/ /app/preview/
COPY images/ /app/images/
COPY fixtures/ /app/fixtures/

EXPOSE 3000/tcp

# USER nobody:nogroup
CMD ["/usr/bin/circusd", "/etc/circus/circusd.ini"]
