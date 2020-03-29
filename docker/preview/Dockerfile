FROM btimby/preview-base

EXPOSE 3000/tcp

COPY docker/monit/monitrc.preview /etc/monitrc

ENTRYPOINT ["/tini", "--"]

CMD [ "monit", "-I", "-d", "1", "-c", "/etc/monitrc"]
