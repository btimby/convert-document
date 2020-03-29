FROM btimby/preview-base

COPY docker/monit/monitrc.soffice /etc/monitrc

ENTRYPOINT ["/tini", "--"]

CMD [ "monit", "-I", "-d", "1", "-c", "/etc/monitrc"]
