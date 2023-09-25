import pandas as pd
from datetime import datetime
import os, sys,subprocess, math
import numpy as np
import logging, time
from cachetools import TTLCache,cached
import asyncio
from collections import defaultdict
# current_path = os.path.dirname(os.path.abspath(__file__))
# os.chdir(current_path)

logging.basicConfig(filename='/home/flash/evaluation/cv_wula.log',level=logging.DEBUG)

namespace="flash"
flashes=["bert-qa-fwm","labse-fwm","resnet-50-fwm",
         "resnet-101-fwm","resnet-152-fwm","shufflenet-fwm","vggnet-11-fwm","bert-fwm"]

url_mapping = {
    "bert-fwm": "http://serverless.siat.ac.cn:31112/function/bert-fwm.flash",
    "bert-qa-fwm": "http://serverless.siat.ac.cn:31112/function/bert-qa-fwm.flash",
    "labse-fwm": "http://serverless.siat.ac.cn:31112/function/labse-fwm.flash",
    "resnet-50-fwm": "http://serverless.siat.ac.cn:31112/function/resnet-50-fwm.flash",
    "resnet-101-fwm": "http://serverless.siat.ac.cn:31112/function/resnet-101-fwm.flash",
    "resnet-152-fwm": "http://serverless.siat.ac.cn:31112/function/resnet-152-fwm.flash",
    "shufflenet-fwm": "http://serverless.siat.ac.cn:31112/function/shufflenet-fwm.flash",
    "vggnet-11-fwm": "http://serverless.siat.ac.cn:31112/function/vggnet-11-fwm.flash"
}
MUs= {
    "bert-fwm": 0.05,
    "bert-qa-fwm": 0.05,
    "labse-fwm": 0.05,
    "resnet-50-fwm": 0.05,
    "resnet-101-fwm": 0.05,
    "resnet-152-fwm": 0.05,
    "shufflenet-fwm":0.05,
    "vggnet-11-fwm": 0.05
}


def generate_gamma_distribution(t: float, mu: float, sigma: float):
    beta = sigma ** 2 / mu
    alpha = mu / beta
    n = int(math.ceil(t / mu))
    s = t * 2
    while s > t * 1.5:
        dist = np.random.gamma(alpha, beta, n)
        for i in range(1, n):
            dist[i] += dist[i-1] 
        s = dist[-1]
    return dist
    
def to_file(distFile: str, dist: list[float]):
    os.makedirs(os.path.dirname(distFile), exist_ok=True)
    with open(distFile, "w+") as f:
        for d in dist:
            f.write(f"{d}\n")


def build_request_distribution(flash:str, scheduler:str, slo:str, start_time:str, mu:float, cv:float):
    sigma = mu * cv
    output_path = f'/home/flash/evaluation/cvd/{flash}/{scheduler}/{start_time}/{cv}'
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    dist = generate_gamma_distribution(900, mu, sigma)
    to_file(os.path.join(output_path, f"{flash}-dist.txt"), dist)
 


def scale_all_deployments_to_one(namespace="flash"):
    cmd = f'kubectl get deployments -n {namespace} -o jsonpath="{{.items[*].metadata.name}}"'
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if stderr:
        logging.info(stderr.decode('utf-8'))
        return
    deployments = stdout.decode('utf-8').strip().split()
    logging.info(deployments)
    for deployment in deployments:
        logging.info(deployment)
        scale_cmd = f'kubectl scale deployment --replicas=1 -n {namespace} {deployment}'
        logging.info(scale_cmd)
        process = subprocess.Popen(scale_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if stderr:
            logging.info(stderr.decode('utf-8'))
        if stdout:
            logging.info(stdout.decode('utf-8'))




async def run_http_request_with_wula(flash:str, scheduler:str, slo:str, start_time:str, mu:float, cv:float,url:str):
    resp_path = f'/home/flash/evaluation/metrics/cvd/{flash}/{scheduler}/{start_time}/{cv}'

    os.makedirs(resp_path, exist_ok=True)
    request_cmd = f'/home/flash/evaluation/workloads/wula -name {flash} -dist {flash} -dir /home/flash/evaluation/cvd/{flash}/{scheduler}/{start_time}/{cv}/ -dest /home/flash/evaluation/metrics/cvd/{flash}/{scheduler}/{start_time}/{cv}/{flash}.csv -url {url} -SLO {slo} '
    logging.info(request_cmd)
    process = await asyncio.create_subprocess_shell(request_cmd)
    await process.wait()
    logging.info("run http")

async def main():
    CVs = [1,2,4,8]
    # CVs = [16]

      # List of model name
    
    # for flash in flashes:
        # model_entry = build_url_list(flash)  # Define model_entry here for each model_name
    for cv in CVs:
        mu = MUs[flash]
        build_request_distribution(flash, scheduler, slo, start_time, mu, cv)
        logging.info("build error")
        tasks = []
        if flash in flashes:  # Check if the model_name has an associated URL
            url = url_mapping[flash]
            tasks.append(run_http_request_with_wula(flash, scheduler, slo, start_time, mu, cv, url))
        logging.info("liyanbo1")
        await asyncio.gather(*tasks)
        logging.info("liyanbo2")
        await asyncio.sleep(10)
    logging.info("jieshu")
            


if __name__ == '__main__':
    start_time = time.time().__int__()
    default_values = ['cv_wula.py', 'bert', 'default', 'default', '10', start_time]

    args = sys.argv

    if len(args) > 1:
        args = sys.argv
    else:
        args = default_values
    if len(args) == 0:
        print("Usage: python3 cv_wula.py  <model_name> <scaling> <scheduler> <slo> <start_time>")
        exit(1)
    flash = args[1]
    scaling = args[2]
    scheduler = args[3]
    slo = args[4]
    start_time = args[5]
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # loop = asyncio.get_event_loop()
    loop.run_until_complete(main())  # <-- Use this instead
    loop.close()  # <-- Stop the event loop
    exit(0)