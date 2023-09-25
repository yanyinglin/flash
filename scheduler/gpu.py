import pandas as pd
class GPUMetric:
    def __init__(self):
        self.columns = ['node_name', 'device_uuid', 'memory_spare','memory_allocating']
        self.Gspare_GPU = pd.DataFrame(columns=self.columns)


    # @cached(cache=TTLCache(maxsize=100, ttl=3))
    def get_real_time_spare_GM(self,prometheus):
        query = 'DCGM_FI_DEV_FB_FREE'
        result = prometheus.custom_query(query)
        print(result)
        spare_GM = pd.DataFrame(columns=self.columns)
        for r in result:
            node_name = r['metric']['kubernetes_node']
            device_uuid = r['metric']['UUID']
            memory_spare = int(r['value'][1])/1024
            device_metric  = pd.DataFrame({'node_name': [node_name], 'device_uuid': [device_uuid], 'memory_spare': [memory_spare]})
            spare_GM = pd.concat([spare_GM, device_metric])
        self.Gspare_GPU = spare_GM
        
    def get_spare_GM_ratio(self, prometheus):
        query = 'DCGM_FI_DEV_MEM_COPY_UTIL'
        result = prometheus.custom_query(query)
        spare_GM_ratio = pd.DataFrame()
        for r in result:
            node_name = r['metric']['kubernetes_node']
            device_uuid = r['metric']['UUID']
            metric = 'memory_spare'
            memory_spare = int(r['value'][1])/1024
            device_metric  = pd.DataFrame({'node_name': [node_name], 'device_uuid': [device_uuid], 'value': [memory_spare], 'metric': [metric]})
            spare_GM_ratio = pd.concat([spare_GM_ratio, device_metric])
        return spare_GM_ratio.reset_index(drop=True)
    
    def get_real_time_GPU_util(self, prometheus):
        query = 'DCGM_FI_DEV_DEC_UTIL'
        result = prometheus.custom_query(query)
        GPU_util = pd.DataFrame()
        for r in result:
            node_name = r['metric']['kubernetes_node']
            device_uuid = r['metric']['UUID']
            metric = 'gpu_util'
            value = int(r['value'][1])
            device_metric  = pd.DataFrame({'node_name': [node_name], 'device_uuid': [device_uuid], 'metric': [metric], 'value': [value]})
            GPU_util = pd.concat([GPU_util, device_metric])
        return GPU_util.reset_index(drop=True)
    
    def allocate_GM(self, node_name, device_uuid, memory_allocating):
        self.Gspare_GPU.loc[(self.Gspare_GPU.node_name == node_name) & (self.Gspare_GPU.device_uuid == device_uuid), 'memory_spare'] -= memory_allocating
        self.Gspare_GPU.loc[(self.Gspare_GPU.node_name == node_name) & (self.Gspare_GPU.device_uuid == device_uuid), 'memory_allocating'] += memory_allocating


    def hard_get_gpu(self,prometheus):
        self.get_real_time_spare_GM(prometheus)
        return self.Gspare_GPU
     
    

class CPUMetric:
    def __init__(self):
        pass
    def get_real_time_spare_CPU(self,prometheus):
        query = 'instance:node_cpu_utilisation:rate5m'
        result = prometheus.custom_query(query)
        spare_CPU = pd.DataFrame()
        for r in result:
            node_name = r['metric']['instance']
            cpu_spare = 100 - float(r['value'][1])
            node_metric  = pd.DataFrame({'node_name': [node_name], 'value': [cpu_spare], 'metric': ['cpu_spare']})
            spare_CPU = pd.concat([spare_CPU, node_metric])
        
        return spare_CPU.reset_index(drop=True)

    def get_cpu_util(self,prometheus):
        query = 'instance:node_cpu_utilisation:rate5m'
        result = prometheus.custom_query(query)
        spare_CPU = pd.DataFrame()
        for r in result:
            node_name = r['metric']['instance']
            cpu_util = float(r['value'][1])
            node_metric  = pd.DataFrame({'node_name': [node_name], 'value': [cpu_util], 'metric': ['cpu_util']})
            spare_CPU = pd.concat([spare_CPU, node_metric])
        return spare_CPU.reset_index(drop=True)

    def get_cpu_mem_ratio(self,prometheus):
        query = 'instance:node_memory_utilisation:ratio'
        result = prometheus.custom_query(query)
        spare_CPU = pd.DataFrame()
        for r in result:
            node_name = r['metric']['instance']
            mem_util = float(r['value'][1])
            node_metric  = pd.DataFrame({'node_name': [node_name], 'value': [mem_util], 'metric': ['mem_util']})
            spare_CPU = pd.concat([spare_CPU, node_metric])
        return spare_CPU.reset_index(drop=True)


    def get_real_time_spare_mem(self, prometheus):
        query = 'instance:node_memory_utilisation:ratio'
        result = prometheus.custom_query(query)
        spare_mem = pd.DataFrame()
        for r in result:
            node_name = r['metric']['instance']
            mem_spare = 100 - float(r['value'][1])
            node_metric  = pd.DataFrame({'node_name': [node_name], 'value': [mem_spare], 'metric': ['mem_spare']})
            spare_mem = pd.concat([spare_mem, node_metric])
        
        return spare_mem.reset_index(drop=True)
    
    def get_pod_numbers(self,prometheus):
        query = 'count(kube_pod_info)'
        result = prometheus.custom_query(query)
        # pod_numbers = pd.DataFrame()
        return int(result[0]['value'][1])
    
    def get_node_numbers(self,prometheus):
        query = 'count(kube_node_info)'
        result = prometheus.custom_query(query)
        # node_numbers = pd.DataFrame()

        return int(result[0]['value'][1])
    
# from prometheus_api_client import PrometheusConnect
# prometheus_client = PrometheusConnect(url="http://172.169.8.57:30500/", disable_ssl=False) 
# cpum=CPUMetric()
# spare_CM = cpum.get_real_time_spare_CPU(prometheus_client)
# print(spare_CM)