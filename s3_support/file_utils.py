import os
import subprocess
#from seqr.utils.logging_utils import SeqrLogger
#logger = SeqrLogger(__name__)

import boto3
import logging
from urllib.parse import urlparse
import tempfile

logger = logging.getLogger(__name__)


def _run_command(command, user=None):
    logger.info('==> {}'.format(command), user)
    return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)


def _run_gsutil_command(command, gs_path, gunzip=False, user=None):
    #  Anvil buckets are requester-pays and we bill them to the anvil project
    project_arg = '-u anvil-datastorage ' if gs_path.startswith('gs://fc-secure') else ''
    command = 'gsutil {project_arg}{command} {gs_path}'.format(
        project_arg=project_arg, command=command, gs_path=gs_path,
    )
    if gunzip:
        command += " | gunzip -c -q - "

    return _run_command(command, user=user)


def _is_google_bucket_file_path(file_path):
    return file_path.startswith("gs://")

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


def does_file_exist(file_path):
    if _is_google_bucket_file_path(file_path):
        process = _run_gsutil_command('ls', file_path)
        return process.wait() == 0
    elif _is_s3_file_path(file_path):
        s3_client = boto3.client('s3')
        parts = parse_s3_path(file_path)
        response = s3_client.list_objects(
            Bucket = parts['bucket'],
            Prefix = parts['key']
        )
        return 'Contents' in response and len(response['Contents']) > 0

    return os.path.isfile(file_path)



'''
def does_file_exist(file_path, user=None):
    if _is_google_bucket_file_path(file_path):
        process = _run_gsutil_command('ls', file_path, user=user)
        return process.wait() == 0
    return os.path.isfile(file_path)

'''

'''
def file_iter(file_path, byte_range=None, raw_content=False, user=None):
    if _is_google_bucket_file_path(file_path):
        for line in _google_bucket_file_iter(file_path, byte_range=byte_range, raw_content=raw_content, user=user):
            yield line
    elif byte_range:
        command = 'dd skip={offset} count={size} bs=1 if={file_path}'.format(
            offset=byte_range[0],
            size=byte_range[1]-byte_range[0],
            file_path=file_path,
        )
        process = _run_command(command, user=user)
        for line in process.stdout:
            yield line
    else:
        mode = 'rb' if raw_content else 'r'
        with open(file_path, mode) as f:
            for line in f:
                yield line
'''

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



def _google_bucket_file_iter(gs_path, byte_range=None, raw_content=False, user=None):
    """Iterate over lines in the given file"""
    range_arg = ' -r {}-{}'.format(byte_range[0], byte_range[1]) if byte_range else ''
    process = _run_gsutil_command(
        'cat{}'.format(range_arg), gs_path, gunzip=gs_path.endswith("gz") and not raw_content, user=user)
    for line in process.stdout:
        if not raw_content:
            line = line.decode('utf-8')
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
    #    logger.error("Unable to stream response for s3 path " + file_path)


def mv_file_to_gs(local_path, gs_path, user=None):
    if not _is_google_bucket_file_path(gs_path):
        raise Exception('A Google Storage path is expected.')
    command = 'mv {}'.format(local_path)
    process = _run_gsutil_command(command, gs_path, user=user)
    if process.wait() != 0:
        errors = [line.decode('utf-8').strip() for line in process.stdout]
        raise Exception('Run command failed: ' + ' '.join(errors))
