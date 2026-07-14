With SOGo 5, a postfix [public image](https://hub.docker.com/r/catatnight/postfix) made by [catcatnight](https://github.com/catatnight/docker-postfix) was used for dev purposes.

Alas, this image throw an error when pulling it:

```bash
sogo@sogo-dev$ docker pull catatnight/postfix
Using default tag: latest
Error response from daemon: unsupported manifest media type and no default available: application/vnd.docker.distribution.manifest.v1+prettyjws
```

Having no time to properly used or made a new postfix image, the original dockefill was clone ([MIT license](https://github.com/catatnight/docker-postfix/blob/master/LICENSE)) and a local image is build instead.

You can find it in folder [catcatnight](catcatnight/Dockerfile)

For sure, a new image must be made.