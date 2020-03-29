FROM btimby/preview-base

EXPOSE 3000/tcp

COPY docker/preview/start /start
COPY docker/preview/ImageMagick-6-policy.xml /etc/ImageMagick-6/policy.xml

ENTRYPOINT ["/tini", "--"]

CMD [ "/start"]
