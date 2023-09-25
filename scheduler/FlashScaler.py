import time
from prometheus_api_client import PrometheusConnect
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import asyncio
import pandas as pd
import subprocess

from kubernetes.client import V1HorizontalPodAutoscaler, V1HorizontalPodAutoscalerSpec, V1CrossVersionObjectReference

# Initialize Prometheus client
prometheus_client = PrometheusConnect(url="http://172.169.8.15:31113/", disable_ssl=False) 

# Load the Kubernetes configuration
config.load_kube_config()

# Initialize the Kubernetes API client
kube_client = client.AppsV1Api()
autoscaling_client = client.AutoscalingV1Api()
# Constants
TARGET_RPS = 5  # Requests Per Second for each pod
MAX_QUEUE_TIME = 10  # Maximum Queue Time in Seconds
SCALE_UP_COOLDOWN = 600  # 10minutes
DEFAULT_NUM_REPLICAS = 3  # Default number of replicas for each deployment
MAX_REPLICAS = 30  # Maximum number of replicas for each deployment

# Scale record dictionary
scale_records = {}

async def scale_deployment(deployment_name, namespace, num_replicas):
    # Check current number of replicas
    try:
        current_deployment = kube_client.read_namespaced_deployment(deployment_name, namespace)
        current_replicas = current_deployment.spec.replicas
        if current_replicas == num_replicas:
            # print(f"No need to scale {deployment_name}. Current replicas: {current_replicas}")
            return
    except ApiException as e:
        print(f"Failed to get deployment {deployment_name}: {e}")
        return

    # Scale up a specific deployment
    try:
        # Construct the command
        cmd = ["kubectl", "scale", "deployment", deployment_name, "--replicas", str(num_replicas), "--namespace", namespace]
        
        # Run the command
        subprocess.check_output(cmd)
        print(f"Successfully scaled deployment {deployment_name} to {num_replicas} replicas")
        scale_records[deployment_name] = time.time()
    except subprocess.CalledProcessError as e:
        print(f"Failed to scale deployment {deployment_name}: {e}")


async def flash_scale(namespace):
    # Get all deployments in the namespace
    deployments = kube_client.list_namespaced_deployment(namespace)
    for deployment in deployments.items:
        deployment_name = deployment.metadata.name
        rps_query = f'sum(irate(gateway_function_invocation_started{{function_name="{deployment_name}.{namespace}"}}[1m]))'
        result = prometheus_client.custom_query(query=rps_query)
        request_df = pd.DataFrame()
        for r in result:
            df = pd.DataFrame([r['value']], columns=['time', 'rps'])
            request_df = pd.concat([request_df, df])

        if request_df.empty:
            print(f"Skipping scale-up for {deployment_name} due to no requests")
            print(f"Query: {rps_query}")
            continue

        rps = float(request_df['rps'].sum())
        print(f"RPS for {deployment_name} is {rps}")
        current_scale = kube_client.read_namespaced_deployment_scale(deployment_name, namespace)
        current_replicas=current_scale.spec.replicas
        print(f"current replicas for {deployment_name} is {current_replicas}")
        if rps == 0:
            print(f"Skipping scale-up for {deployment_name} due to zero RPS")
            continue

        # Calculate desired number of replicas based on request rate and max queue time
        desired_replicas = min(int(rps * MAX_QUEUE_TIME / TARGET_RPS), MAX_REPLICAS)
        if desired_replicas == 0:
            desired_replicas = 1

        
        if desired_replicas == current_scale.spec.replicas:
            print(f"Skipping scale-up for {deployment_name} due to already at desired replicas")
            continue

        if desired_replicas < current_scale.spec.replicas:
        # Check if we've scaled this deployment in the last 10 minutes
            last_scale_time = scale_records.get(deployment_name)
            if last_scale_time and time.time() - last_scale_time < SCALE_UP_COOLDOWN:
                # It's been less than 10 minutes since we last scaled this deployment, so skip this cycle
                print(f"Skipping scale-down for {deployment_name} due to cooldown")
                return
        

        print(f"Desired replicas for {deployment_name} functions is {desired_replicas}")
        print("over!")
        # Scale all functions for the same module to the desired number of replicas
        # for d in deployments.items:
        await scale_deployment(deployment_name, namespace, desired_replicas)
        scale_records[deployment_name] = time.time()

async def rps_scale(namespace):
    deployments = kube_client.list_namespaced_deployment(namespace)
    for deployment in deployments.items:
        deployment_name = deployment.metadata.name
        # Get the requests per second for the '-submod-0' function
        rps_query = f'sum(irate(gateway_function_invocation_started{{function_name="{deployment_name}.{namespace}"}}[1m]))'
        result = prometheus_client.custom_query(query=rps_query)
        request_df = pd.DataFrame()
        for r in result:
            df = pd.DataFrame([r['value']], columns=['time', 'rps'])
            request_df = pd.concat([request_df, df])

        if request_df.empty:
            print(f"Skipping scale-up for {deployment_name} due to no requests")
            print(f"Query: {rps_query}")
            continue

        rps = float(request_df['rps'].sum())
        print(f"RPS for {deployment_name} is {rps}")
        if rps == 0:
            print(f"Skipping scale-up for {deployment_name} due to zero RPS")
            continue

        # Calculate desired number of replicas based on request rate and max queue time
        desired_replicas = int(rps * MAX_QUEUE_TIME / TARGET_RPS)
        if desired_replicas == 0:
            desired_replicas = 1

        current_scale = kube_client.read_namespaced_deployment_scale(deployment_name, namespace)
        if desired_replicas == current_scale.spec.replicas:
            print(f"Skipping scale-up for {deployment_name} due to already at desired replicas")
            continue

        if desired_replicas < current_scale.spec.replicas:
        # Check if we've scaled this deployment in the last 10 minutes
            last_scale_time = scale_records.get(deployment_name)
            if last_scale_time and time.time() - last_scale_time < SCALE_UP_COOLDOWN:
                # It's been less than 10 minutes since we last scaled this deployment, so skip this cycle
                print(f"Skipping scale-down for {deployment_name} due to cooldown")
                return
            
        print(f"Desired replicas for {deployment_name} functions is {desired_replicas}")

        # Scale all functions for the same module to the desired number of replicas
        for d in deployments.items:
            await scale_deployment(d.metadata.name, namespace, desired_replicas)
            scale_records[deployment_name] = time.time()
    

async def check_and_scale(namespace):
    # Retrieve all deployments in the namespace
    deployments = kube_client.list_namespaced_deployment(namespace)
    if not deployments.items:
        print(f"No deployments found in namespace {namespace}")
    for deployment in deployments.items:
        deployment_name = deployment.metadata.name
        await scale_deployment(deployment_name, namespace, DEFAULT_NUM_REPLICAS)
    

    await flash_scale(namespace)


    


# Main loop
while True:
    asyncio.run(check_and_scale("flash"))
    time.sleep(30)
