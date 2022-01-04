# S3 Support 
Seqr unfortunately was create with a Google Cloud Platform (GCP) and google buckets environment in mind. Other places use the AWS ecosystem and thus will be drawing
data from s3 buckets instead. Support for s3 buckets was implemented by Nick C. in his [seqr bch instance repository](https://github.com/nicklecompteBCH/seqr-bch-installation).
However, this implementation was applied to a very outdated version of seqr. This was recently ported over again in December 2021 to be compatible with newer versions of seqr.
The most important use of S3 bucket support is loading of bam/cram files used by IGV. Detailed below are consideration to make IGV using S3 work.

## nginx server configuration
The server must support sending bytes and also having it in the header. Below is an example configuration file for ngnix
```
server {
  listen 80;
  server_name 0.0.0.0;
  add_header Accept-Ranges bytes;
  underscores_in_headers on;

  location /static/ {
    root /home/ubuntu/seqr;
  }

  location / {
    include proxy_params;
    include mime.types;
    proxy_connect_timeout 300;
    proxy_read_timeout 300;
    proxy_pass http://unix:/home/ubuntu/seqr/seqr.sock;
    proxy_force_ranges on;
    #proxy_buffering off;
    #proxy_buffer_size 128k;
    #proxy_buffers 4 256k;
    #proxy_busy_buffers_size 256k;
    proxy_pass_request_headers on;
  }

  location /reference/ {
    alias /home/ubuntu/reference/;
    autoindex on;
  }

  location /reads {
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_pass https://gnomad.broadinstitute.org/reads;
  }
}
```

## Support to send bytes implemented by the application server

Recognizing and accessing s3 content in `seqr/utils/utils/file_utils.py`
```
import boto3
from urllib.parse import urlparse

def _is_s3_file_path(file_path):
    return file_path.startswith("s3://")


def parse_s3_path(s3path):
    parsed = urlparse(s3path)
    bucket = parsed.netloc
    path = parsed.path[1:]
    object_list = path.split('/')
    filename = object_list[-1]
    return {
        "bucket" : bucket,
        "key" : path,
        "filename" : filename
    }

def file_iter(file_path, byte_range=None):
    if _is_google_bucket_file_path(file_path):
        for line in _google_bucket_file_iter(file_path, byte_range=byte_range):
            yield line
    elif _is_s3_file_path(file_path):
        for line in _s3_file_iter(file_path,byte_range=byte_range):
            yield line
    else:
        with open(file_path) as f:
            if byte_range:
                f.seek(byte_range[0])
                for line in f:
                    if f.tell() < byte_range[1]:
                        yield line
                    else:
                        break
            else:
                for line in f:
                    yield line

def _s3_file_iter(file_path, byte_range = None):
    logger.info("Iterating over s3 path: " + file_path)
    client = boto3.client('s3')
    range_arg = f"bytes={byte_range[0]}-{byte_range[1]}" if byte_range else ''
    logger.info("Byte range for s3: " + range_arg)
    parts = parse_s3_path(file_path)
    t = tempfile.TemporaryFile()
    r = client.get_object(
        Bucket=parts['bucket'],
        Key=parts['key'],
        Range=range_arg,
    )
    for line in r['Body']:
        yield line

```

Sending partial file implemented in `seqr/views/apis/igv_api.py`
```
import boto3
from urllib.parse import urlparse

def _stream_file(request, path):
    # based on https://gist.github.com/dcwatson/cb5d8157a8fa5a4a046e
    content_type = 'application/octet-stream'
    range_header = request.META.get('HTTP_RANGE', None)
    if range_header:
        logger.info("Range header found:" + range_header + " for path " + path)
        range_match = re.compile(r'bytes\s*=\s*(\d+)\s*-\s*(\d*)', re.I).match(range_header)
        first_byte, last_byte = range_match.groups()
        first_byte = int(first_byte) if first_byte else 0
        last_byte = int(last_byte)
        length = last_byte - first_byte + 1
        resp = StreamingHttpResponse(
            file_iter(path, byte_range=(first_byte, last_byte)), status=206, content_type=content_type)
        resp['Content-Length'] = str(length)
        resp['Content-Range'] = 'bytes %s-%s' % (first_byte, last_byte)

    elif path.endswith('.bam') or path.endswith('.cram'):
        logger.info("BAM file without a range_header in request return block 65536")
        default_block_len = 65536

        resp = StreamingHttpResponse(
            file_iter(path, byte_range=(0, default_block_len-1)), status=206, content_type=content_type)
        resp['Content-Length'] = default_block_len
        resp['Content-Range'] = 'bytes 0-%s' % (default_block_len-1)

    else:
        logger.info("Range header not found in following_headers: " + str(list(request.META.items())))
        resp = StreamingHttpResponse(file_iter(path), content_type=content_type)
    resp['Accept-Ranges'] = 'bytes'
    return resp


```
Note this implementation assumes that a request for a bam/cram file without a byte range is incorrect and only sends the first block of data (i.e. 65K bytes). This happens due to Content Security Policies not forwarding the correct headers and IGV is then unaware the server can serve a byte range and requests for the whole bam/cram file.

## Content security policies to get IGV to work
This requires editing the `seqr/settings.py` file. Update the CSS hash if using different version of IGV. If this requires updating this is obvious as IGV does not display correctly in terms of style. You can get the hash from the Developer console as it will be displayed as an error in red.

```
# IGV js injects CSS into the page head so there is no way to set nonce. Therefore, support hashed value of the CSS
IGV_CSS1_HASH = "'sha256-mMr3XKHeuAZnT2THF0+nzpjf/J0GLygO9xHcQduGITY='"
IGV_CSS2_HASH = "'sha256-m7BbAVh3TyZH136+WARZw8eulS+0pHbppq98KGFYbhA='"
IGV_CSS3_HASH = "'sha256-D1ouVPg7bXVEm/f4h9NNmEBwWO5vkjlDOIHPeV3tFPg='"

CSP_STYLE_SRC = ('https://fonts.googleapis.com', "'self'", IGV_CSS1_HASH, IGV_CSS2_HASH,IGV_CSS3_HASH)
CSP_STYLE_SRC_ELEM = ('https://fonts.googleapis.com', "'self'", IGV_CSS1_HASH, IGV_CSS2_HASH,IGV_CSS3_HASH)
```

IGV also requires access to broadinstitute website to update usage counter
```
CSP_CONNECT_SRC = ("'self'", 'https://gtexportal.org', 'https://www.google-analytics.com', 'https://storage.googleapis.com', 'https://s3.amazonaws.com','https://data.broadinstitute.org') # google storage used by IGV
```

