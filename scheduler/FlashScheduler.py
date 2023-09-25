from kubernetes import client, config
import re
from gpu import GPUMetric
from gpu import CPUMetric
from flask import Flask, request
import json
import ssl, os
import base64
import logging
import pandas as pd
from prometheus_api_client import PrometheusConnect
import time 
prometheus_client = PrometheusConnect(url="http://172.16.101.178:30500/", disable_ssl=False) 

os.chdir(os.path.dirname(os.path.abspath(__file__)))

context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
context.load_cert_chain("mutaingwebhook/cc132/server.crt", "mutaingwebhook/cc132/server.key")

priority_scores = {}
# Load the Kubernetes configuration
config.load_kube_config()
# Initialize the Kubernetes API client
api = client.CoreV1Api()
v1 = client.AppsV1Api()
scheduler_name = "odc_scheduler"
gpu_metric = GPUMetric()
cpu_metric = CPUMetric()
reserved_cpu = 0.3

namespace = "flash"
CPU_QUOTA = 1.15
memory_units = {
    "K": 1024**2,
    "M": 1024**1,
    "G": 1,
}
node_last_deploy={
    'cc173':time.time(),
    'cc178':time.time(),
    'cc184':time.time(),
    'cc185':time.time(),
    'cc187':time.time(),
    'cc191':time.time(),
    'cc221':time.time(),
    'cc222':time.time(),
    'cc223':time.time(),
    'cc227':time.time(),
    'cc228':time.time(),
    'cc233':time.time(),
    'cc242':time.time(),
}

def init_mappings():
    print("initing mappings")
    node_list = api.list_node().items
    server_to_pods = {}
    # server_gpu_map = {}
    for node in node_list:
        node_name = node.metadata.name
        server_to_pods[node_name] = []
    pod_list = api.list_namespaced_pod(namespace=namespace).items
    for pod in pod_list:
        if pod.spec.scheduler_name != scheduler_name:
            continue
        node_name = pod.spec.node_name
        if node_name is None:
            continue
        server_to_pods[node_name].append(pod.metadata.name)
    print(f"server_to_pods:\n{server_to_pods}")
    return server_to_pods


# get real time memory spare
def standar_mem(memory_str):
    memory_match = re.match(r"(\d+)([KMGT]i?)?", memory_str)
    memory_value = int(memory_match.group(1))
    memory_unit = memory_match.group(2).replace("i", "")

    # Convert the memory allocation to bytes using the appropriate multiplier
    if memory_unit:
        memory_multiplier = memory_units.get(memory_unit, 1)
        memory_allocatable = memory_value / memory_multiplier
    else:
        memory_allocatable = memory_value / 1024**3
    return memory_allocatable

instance_map={
    '172.169.8.114:9100': 'cc221',
    '172.169.8.122:9100': 'cc222',
    '172.169.8.47:9100': 'cc223',
    '172.169.8.221:9100': 'cc227',
    '172.169.8.4:9100': 'cc228',
    '172.169.8.104:9100': 'cc233',
    '172.169.8.113:9100': 'cc242'
}
functions=["labse-fwm","bert-qa-fwm","vggnet-11-fwm","bert-fwm","resnet-152-fwm","resnet-101-fwm","resnet-50-fwm","shufflenet-fwm"]
def profile_cpu_best(function_name):
    import pandas as pd
    df = pd.read_csv('/home/flash/motivation/model_cpu_best.csv')
    filtered_df = df[df['model_name'] == function_name]
    best_cpu_num = filtered_df['best_cpu_num'].values[0]
    return best_cpu_num


def schedule(pod):
    # Get function from pod's labels
    function_name = pod["metadata"]["labels"].get("faas_function")
    cpu_require = pod["spec"]["containers"][0]["resources"]["requests"]["cpu"]

    if not function_name:
        return None, None
    # # Get required GPU for the function
    # cpu_require = get_function_cpu_require(function)
    # if not cpu_require:
    #     return None, None
    # Get real-time GPU metrics
    function_node_mapping = {} 
    spare_CM = cpu_metric.get_real_time_spare_CPU(prometheus_client)
    # Ensure that spare_CM is a DataFrame with 'value' column of dtype float64
    spare_CM['value'] = spare_CM['value'].astype(float)
    # spare_CM = spare_CM[spare_CM['value']  > cpu_require]    
    candidates = spare_CM.node_name.unique().tolist()
    print(candidates)

# top_priority = sorted(candidates, key=lambda node: spare_CM[spare_CM['node_name'] == node]['value'].values[0], reverse=True)
    top_priority = sorted([node for node in candidates if node in instance_map], key=lambda node: spare_CM[spare_CM['node_name'] == node]['value'].values[0], reverse=True)
    selected_nodes = [node for node in top_priority if node != '172.169.8.94:9100'][:8]
    print(selected_nodes)
    for i, model in enumerate(functions):
        if i >= len(functions) - 2:
            node_index = i- (len(functions)-len(selected_nodes))
        else:
            node_index = i % len(selected_nodes)
    
        print(node_index) 
        function_node_mapping[model] = selected_nodes[node_index]
    for f in function_node_mapping:
        if function_node_mapping[f] in instance_map:
            function_node_mapping[f] = instance_map[function_node_mapping[f]]
    print(function_node_mapping)
    if function_name in function_node_mapping:
        node_name = function_node_mapping[function_name]
    cpu_cores = profile_cpu_best(function_name)
    return  node_name,cpu_cores
def patch_pod(pod,node_name,cpu_cores):
    # Patch the pod to the selected node and device
    patch_operation = [
        # pod name
        {
            "op": "add",
            "path": "/spec/nodeSelector",
            "value": {"kubernetes.io/hostname": node_name},
        },
        {
            # mount local disk /data/model/openfaas/ to container /data/model/openfaas/
            "op": "add",
            "path": "/spec/containers/0/volumeMounts",
            "value": [{"name": "openfaas-model", "mountPath": "/data/model/openfaas/"}],
        },
        {
            "op": "add",
            "path": "/spec/volumes",
            "value": [
                {
                    "name": "openfaas-model",
                    "hostPath": {"path": "/data/model/openfaas/"},
                }
            ],
        },
        
        {
            "op": "replace",
            "path": "/spec/containers/0/resources/requests/cpu",
            "value": f"{cpu_cores}",
        },
        {
            "op": "replace",
            "path": "/spec/containers/0/resources/limits/cpu",
            "value": f"{cpu_cores}",
        },

    ]
    return base64.b64encode(json.dumps(patch_operation).encode("utf-8"))


def admission_response(uid, message, pod, node_name,cpu_cores):
    if not node_name:
        return {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {"uid": uid, "allowed": False, "status": {"message": message}},
        }
    # Create an admission response
    return {
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "response": {
            "uid": uid,
            "allowed": True,
            "status": {"message": message},
            "patchType": "JSONPatch",
            "patch": patch_pod(pod, node_name,cpu_cores).decode("utf-8"),
        },
    }


app = Flask(__name__)
init_mappings()


@app.route("/mutate", methods=["POST"])
def mutate():
    review = request.json    
    pod = review["request"]["object"]
    node_name,cpu_cores = schedule(pod)
    print(f"select {node_name} {cpu_cores} cpu for pod.")
    if node_name:
        addmission = admission_response(
            review["request"]["uid"], "success", pod, node_name,cpu_cores
        )
        return addmission
    else:
        return admission_response(
            review["request"]["uid"], "fail", pod, node_name,cpu_cores
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9008, ssl_context=context, threaded=False)
