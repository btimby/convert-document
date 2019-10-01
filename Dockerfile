FROM ubuntu:18.04

ENV DEBIAN_FRONTEND noninteractive
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

RUN apt-get update \
    && apt-get -y update \
    && apt-get -y upgrade \
    && apt-get -y install \
        libreoffice libreoffice-writer ure libreoffice-java-common \
        libreoffice-core libreoffice-common openjdk-8-jre fonts-opensymbol \
        hyphen-fr hyphen-de hyphen-en-us hyphen-it hyphen-ru fonts-dejavu \
        fonts-dejavu-core fonts-dejavu-extra fonts-droid-fallback fonts-dustin \
        fonts-f500 fonts-fanwood fonts-freefont-ttf fonts-liberation fonts-lmodern \
        fonts-lyx fonts-sil-gentium fonts-texgyre fonts-tlwg-purisa python3-uno \
        python3-pip \
    && apt-get -y autoremove \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN pip3 install unoconv

RUN groupadd -g 1001 preview
RUN useradd -g 1001 -u 1001 preview

CMD ["/bin/bash"]
