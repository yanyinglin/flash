import os, datetime, time
import pandas as pd
import pytz


# current_path = os.path.dirname(os.path.abspath(__file__))
# os.chdir(current_path)
import kubernetes
import uuid
import subprocess, asyncio, requests
from concurrent.futures import ProcessPoolExecutor
from collections import defaultdict


kubernetes.config.load_kube_config()
v1 = kubernetes.client.CoreV1Api()
namespace = "flash"
workload_name_list = ["azure"]
scaling = "default"
# scheduler = "defaultScheduler"
scheduler = "FlashScheduler"
slo = 10
benchmark_version = "1.0.7"
columns = [
    "uuid",
    # "wrkname",
    "model_name",
    "scaling",
    "scheduler",
    "start_time",
    "end_time",
    "slo",
    "collected"
]

flashes=["labse-fwm","bert-qa-fwm","vggnet-11-fwm","bert-fwm","resnet-152-fwm","resnet-101-fwm","resnet-50-fwm","shufflenet-fwm"]
# modelsize
evaluation_record = pd.read_csv("/home/flash/evaluation/metrics/evaluation_record_wrk.csv", names=columns)


def build_url_list(flash):
    url_mapping = {
        "bert-fwm": "http://serverless.siat.ac.cn:31112/function/bert-fwm.flash",
        "bert-qa-fwm": "http://serverless.siat.ac.cn:31112/function/bert-qa-fwm.flash",
        "labse-fwm": "http://serverless.siat.ac.cn:31112/function/labse-fwm.flash",
        "resnet-50-fwm": "http://serverless.siat.ac.cn:31112/function/resnet-50-fwm.flash",
        "resnet-101-fwm": "http://serverless.siat.ac.cn:31112/function/resnet-101-fwm.flash",
        "resnet-152-fwm": "http://serverless.siat.ac.cn:31112/function/resnet-152-fwm.flash",
        "shufflenet-fwm": "http://serverless.siat.ac.cn:31112/function/shufflenet-fwm.flash",
        "shufflenet-fwm": "http://serverless.siat.ac.cn:31112/function/shufflenet-fwm.flash",
        "vggnet-11-fwm": "http://serverless.siat.ac.cn:31112/function/vggnet-11-fwm.flash"
    }
    if flash in url_mapping:
        return url_mapping[flash]
benchmarks_usr_path = "/home/flash/benchmark/flash-with-model"
benchmarks_path = [os.path.join(benchmarks_usr_path, model) for model in flashes]
benchmarks_path = dict(zip(flashes, benchmarks_path))

wrknames = {}
# entry = {}
for flash in flashes:
    wrknames[flash] = build_url_list(flash)
def init_benchmark_status():
    utc_now = datetime.datetime.now(pytz.UTC)
    init_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    benchmark_data = []
    for flash in flashes:
        url = build_url_list(flash)
        benchmark_data.append([flash, init_time, benchmark_version, 0])

    status = pd.DataFrame(benchmark_data, columns=["model", "init_time", "version", "deploy"])
    status.to_csv("/home/flash/benchmark_status_wrk.csv", index=False)
init_benchmark_status()
print("initialing status...")

def deploy_model():
    status= pd.read_csv("/home/flash/benchmark_status_wrk.csv")
    for flash in flashes:
        if check_if_service_ready(flash):
            print(f"{flash} is already deployed")
    # model_path = f"{benchmarks_path[model_name]}/{benchmark}"
    model_path = "/home/flash/benchmark/flash-with-model"
    
    cmd = f"cd {model_path} && bash action_deploy.sh"
    print(f"Execute {cmd}")
    os.system(cmd)
    status.loc[
        (status["model"] == flash)
        # & (benchmark_status["benchmark"] == benchmark)
        & (status["version"] == benchmark_version),
        "deploy",] = 1
    status.to_csv("/home/flash/benchmark_status_wrk.csv", index=True)
def deploy_wrk():
    with ProcessPoolExecutor() as executor:
        # for model in models:
            executor.submit(deploy_model)
def check_if_service_ready(flash):
    url = build_url_list(flash)  # Assuming build_url_list directly returns the URL string
    if url is None:
        print(f"URL not found for {flash}")
        return False
    try:
        r = requests.get(url)
        if r.status_code == 200:
            print(f"Service of {flash} is ready")
            return True
        else:
            print(f"Service of {flash} is not ready, return code: {r.status_code}")
    except:
        return False


async def release_model():
    model_path = "/home/flash/benchmark/flash-with-model"
    
    cmd = f"cd {model_path} && faas-cli delete -f config.yml"
    os.system(cmd)



async def remove_dead_pod(pod_name):
    try:
        pod = v1.read_namespaced_pod(pod_name, namespace)
        if not pod.spec.containers[0].resources.limits.get("nvidia.com/gpu"):
            return
        if (
            not pod.status.container_statuses
            or not pod.status.container_statuses[0].state.running
        ):
            os.system(f"kubectl delete pod {pod.metadata.name} -n {namespace}")
    except:
        pass


async def check_wrk_pod_ready(flash, namespace):
    while True:
        pod_status = {}
        pods = v1.list_namespaced_pod(namespace).items
        for pod in pods:
            if pod.status.container_statuses:
                pod_status[pod.metadata.name] = pod.status.container_statuses[0].ready
            else:
                pod_status[pod.metadata.name] = False

        pod_ready = all(status for status in pod_status.values())

        # delete the pod of status "CrashLoopBackOff"
        if not pod_ready:
            print(f"{datetime.datetime.now()}, pod of {flash} is not yet ready")
            for pod in pod_status:
                if not pod_status[pod]:
                    await remove_dead_pod(pod)
        else:
            print(f"{flash} is ready")
            return pod_ready
        print(f"wait for 45 seconds to check again")
        await asyncio.sleep(45)


async def start_request_to_wrks(flash, scaling, scheduler):
    evaluation_record = pd.read_csv("/home/flash/evaluation/metrics/evaluation_record_wrk.csv", names=columns)
    if (
        len(
            evaluation_record[
                (evaluation_record["model_name"] == flash)
                & (evaluation_record["scaling"] == scaling)
                & (evaluation_record["scheduler"] == scheduler)
            ]
        )
        > 0
    ):
        print(f"{flash} {scaling} {scheduler} has been evaluated")
    start_time = time.time().__int__()
    # print("Usage: python3 round_robbin_wrk.py  <wrkname> <scaling> <scheduler> <slo> <start_time>")
    cmd = f"python3 /home/flash/evaluation/workloads/cv_wula.py {flash} {scaling} {scheduler} {slo} {start_time}"
    print(f"Execute {cmd}")
    # when workload is finished, record the time
    process = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    process.wait()
    stdout, stderr = process.communicate()
    print(stdout.decode())
    end_time = time.time().__int__()
    evaluation_uuid = uuid.uuid4()
    tmp_record = pd.DataFrame(
        [[evaluation_uuid, flash, scaling, scheduler, start_time, end_time, slo, 0]],
        columns=columns,
    )
    evaluation_record = pd.concat([evaluation_record, tmp_record])
    evaluation_record.to_csv(
        "/home/flash/evaluation/metrics/evaluation_record_wrk.csv", index=False, header=False
    )


async def run_wrk_benchmark():

    deploy_wrk()
    for flash in flashes:
        # print(f"{wrkname} is deployed, sleeping to function ready!")
        print(f"checking pod of {flash}")
        await check_wrk_pod_ready(flash, namespace)
        
        # await check_wrk_service_ready(wrkname)
        # print(f"all service of {wrkname} is ready, start benchmark!")
        print(f"sending requests to {flash}")
        await start_request_to_wrks(flash, scaling, scheduler)
    model_path = "/home/flash/benchmark/flash-with-model"
    cmd = f"cd {model_path} && faas-cli delete -f config.yml"
    os.system(cmd)
    await asyncio.sleep(30)
    
if __name__ == "__main__":
    asyncio.run(run_wrk_benchmark())
