
import os
import boto3
import filecmp
import time
import threading

import sentry_sdk
from yekta_metrics import PrometheusClient


sentry_sdk.init(
    "https://b61e6399acda4ac7ac7ffbf6deb1f69b@sentry.yektanet.tech/51",
    traces_sample_rate=1.0
)

prom = PrometheusClient()

object_availability = prom.gauge('s3_object_availability', "S3 object availability")
s3_errors = prom.counter('s3_errors', "S3 errors", ("error",))
s3_latency = prom.histogram('s3_latency', "S3 latency", ("method",))

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")


def put_object(bucket, object_name, filename):
    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        endpoint_url=S3_ENDPOINT_URL
    )
    try:
        start_time = time.time()
        s3_client.upload_file(filename, bucket, object_name, ExtraArgs={'ACL': 'public-read', 'ContentType': 'image/jpeg'})
        end_time = time.time()
        s3_latency.observe(end_time - start_time, {'method': 'put'})
    except Exception as e:
        print(e)
        s3_errors.labels(error=str(e)).inc()


def get_object(bucket, object_name, original_filename):
    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        endpoint_url=S3_ENDPOINT_URL
    )
    object_timestamp = object_name.split('.')[0].split('-')[1]
    output_filename = 'output-{}.jpg'.format(object_timestamp)
    try:
        start_time = time.time()
        s3_client.download_file(bucket, object_name, output_filename)
        end_time = time.time()
        s3_latency.observe(end_time - start_time, {'method': 'get'})
    except Exception as e:
        print(e)
        object_availability.set(0)
        s3_errors.labels(error=str(e)).inc()
        return 0
    else:
        if filecmp.cmp(original_filename, output_filename, shallow=False):
            object_availability.set(1)
            os.remove(output_filename)
            return 1
        else:
            s3_errors.labels(error="File comparison failed").inc()
            object_availability.set(0)
            os.remove(output_filename)
            return 2


def delete_object(bucket, object_name):
    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        endpoint_url=S3_ENDPOINT_URL
    )
    try:
        start_time = time.time()
        s3_client.delete_object(Bucket=bucket, Key=object_name)
        end_time = time.time()
        s3_latency.observe(end_time - start_time, {'method': 'delete'})
    except Exception as e:
        print(e)
        s3_errors.labels(error=str(e)).inc()


def check_availability_with_timestamp(bucket, object_name, original_filename):
    put_object(bucket, object_name, original_filename)
    time.sleep(1)
    if get_object(bucket, object_name, original_filename):
        delete_object(bucket, object_name)


if __name__ == "__main__":
    thread_list = []
    bucket_name = os.getenv("BUCKET_NAME")
    while True:
        try:
            easy_timestamp = str(time.time()).split(".")[0]
            x = threading.Thread(target=check_availability_with_timestamp, args=(bucket_name, 'test-{}.jpg'.format(easy_timestamp), 'original.jpg'))
            x.start()
            x.join()
            break
            thread_list.append(x)
            time.sleep(10)
        except Exception as e:
            print(e)
