![CI status](https://travis-ci.org/btimby/django-proxysql.png "CI Status")

# preview-server

A docker container to produce PNG image previews for common file types. This container is intended to be used as part of a larger application stack.

The container uses monit to execute and monitor a Python async http server as well as `soffice.bin` (via `unoconv`) which is used for office document conversion. The preview service utilizes `libav`, `gslib` and `imagemagick-wand`, `PIL` for other file formats.

The focus of this project is to provide a preview success rate as close as possible to 100%. This is achieved by careful testing and error handling. For example, `soffice.bin` is restarted if it consumes too much memory. A healthcheck ensures `soffice.bin` is available (restarting it if not). Also, the preview service will retry requests to `soffice.bin` in order to recover from conversion errors.

## Usage

You should pull the latest stable image from DockerHub and run it like this:

```bash
$ make small
```

Four flavors are provided:

 - small, just two containers, preview-server and preview-soffice.
 - medium, preview-server, haproxy and 3 preview-soffice replicas.
 - large, two preview-server replicas, haproxy, nginx, prometheus, grafana and 5 preview-soffice replicas.
 - dev, same as large but also enables reloading.

* NOTE that the `dev` and `large` flavors require the url http://preview:3000/ to resolve to 127.0.0.1. Use `/etc/hosts` or local DNS records to achieve this. The other flavors will work with http://localhost:3000/.

Once the service has initialised, files, paths, or urls can be sent to the `/preview/` endpoint, and a PNG preview will be returned. Additional configuration is necessary in order to use paths, see Options below for more information. Optional `width` and `height` arguments can be sent with the request to control the size of the returned preview image.

```bash
$ curl -o out.png -F 'file=@mydoc.doc' http://localhost:3000/preview/
$ curl -o out.png -F 'url=http://somedomain.com/some-pdf' http://localhost:3000/preview/
$ curl -o out-small.png -F 'width=100' -F 'height=50' -F 'file=@mydoc.doc' http://localhost:3000/preview/
```

## Options

A number of features are controlled by environment variables.

`PVS_FILES` - This option informs the preview service where files are located. When enabled, the service can be sent a path rather than POSTing file body or URL. When enabled, the given path should be relative to `PVS_FILES`.

For example, below the file located at `/mnt/files/path/to/file.doc` will be previewed.

```bash
$ docker run -d -p 3000:3000 --tmpfs /tmp \
    -v /mnt/files:/mnt/files -e PVS_FILES=/mnt/files \
    btimby/preview-server

$ curl -o out.png -F 'path=/path/to/file.doc' \
    -F 'width=200' -F 'height=100' http://localhost:3000/preview/
```

`PVS_CACHE_CONTROL` - This option controls the `Cache-Control` header emitted by the service. When omitted, the header supressed. When present, it controls the number of minutes previews should be cached.

`PVS_STORE` - By default generated previews are ephemeral. If you wish to store the previews so that they are not regenerated in future requests, you can do so using ththis option. This option is required by `PVS_X_ACCEL_REDIR`. The value should be the path to a volume you mount for this purpose.

This can be used as a cache mechanism, for example by using tmpfs. Optionally, you can provide a file system (even a shared file system) for long-term storage. When combined with `PVS_FILES`, The file's mtime is compared to the preview's mtime. If the source file is newer, the preview is regenerated. This option has no effect for POSTed or downloaded files.

For example, below the host's `/mnt/store` directory or device will be used to store generated previews. The second call to `curl` will be much faster as it will simply return the preview generated in the first call.

```bash
$ docker run -d -p 3000:3000 --tmpfs /tmp \
    -v /mnt/files:/mnt/files -e PVS_FILES=/mnt/files \
    -v /mnt/store:/mnt/store -e PVS_STORE=/mnt/store \
    btimby/preview-server

$ curl -o out.png -F 'path=/path/to/file.doc' http://localhost:3000/preview/
$ curl -o out.png -F 'path=/path/to/file.doc' http://localhost:3000/preview/
```

`PVS_X_ACCEL_REDIR` - This option offloads file transfers to nginx. It requires that `PVS_STORE` be configured and that the volume be shared with nginx. The value should be the URI of the location in the nginx configuration file.

https://www.nginx.com/resources/wiki/start/topics/examples/xsendfile/

`PVS_DEFAULT_WIDTH` & `PVS_DEFAULT_HEIGHT` - These options provide the default width and height of generated PNG previews. If the caller omits `width` and `height` parameters to the service, these defaults are used.

`PVS_MAX_WIDTH` & `PVS_MAX_HEIGHT` - These options provide the maximum allowable `width` and `height` that a user can request.

`PVS_LOGLEVEL` & `PVS_HTTP_LOGLEVEL` - These options control the log output generated by the preview service. The first applies to the service in general, the second to the `aiohttp`'s access log.

`PVS_METRICS` - Enable prometheus metrics at `/metrics/` endpoint. The large flavor bundles preconfigured prometheus and grafana. Grafana provisioning is used to bundle a prebuild dashboard. Grafana is at: http://localhost:3001 and prometheus is at http://localhost:9090/.

`PVS_RELOAD` - Enable reloading of preview-server when source code changes.

`PROFILE_PATH` - Enable code profiling, runtime stats will be stored here when preview-server stops.

`MAX_FILE_SIZE` - Limit the size (in bytes) of files that can be previewed [default: unlimited].

`MAX_PAGES` - Limit the number of pages included in preview [default: unlimited]. Users can request page ranges or `"all"` however, this limit will be enforced.

`PVS_PORT` - The port that the preview-server binds within the container.

`PVS_UID` - The UID to use for preview-server and preview-soffice. This may be necessary to ensure that they can access volumes.

`PVS_GID` - The GID to use for preview-server and preview-soffice. This may be necessary to ensure that they can access volumes.

`PVS_SOFFICE_ADDR` - Used by preview-server to connect to soffice. Used by soffice for bind.

`PVS_SOFFICE_PORT` - Used by preview-server to connect to soffice. Used by soffice for bind.

`PVS_SOFFICE_TIMEOUT` - Control how long to wait for a response from soffice before retrying.

`PVS_SOFFICE_RETRY` - Control how many times to retry connection to soffice before failing.


## Development

To build, run:

```bash
$ make dev
```

Once the service is initialized, you can test it using:

The stress testing tool `make test`
The interactive test: http://localhost:3000/test/

## License

MIT, see `LICENSE`.
